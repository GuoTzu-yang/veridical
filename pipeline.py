#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline.py —— 全流程（第 18 轮）

为什么需要它
------------
到这一轮为止，零件是齐的，但是散的：

    cards.recommend   推荐方法
    orchestrate       探索几条路线，选最优
    mmkit run         出稿（含编译 + 9 项验收 + 记账本）
    gate              质量门
    review            收敛判定
    freeze            数字冻结

每一件都能单独跑，但**没有一条命令从数据走到成稿**。

职责怎么分（这是本轮要理清的事）
--------------------------------
原来我以为 orchestrate 和 review 重复了 —— 它们都有「跑一轮 → 判定 →
收敛」。其实不是：

    orchestrate  管**探索**：哪条建模路线更好
    review       管**验收**：稿子本身够不够好

两者是**串行**的：先用 orchestrate 把路线定下来，再出稿，再验收。
重复的是「循环」这个形式，不是「判断什么」。

流程
----
    1. 读数据 → 推特征 → cards.recommend 给候选
    2. orchestration 探索（提案来自推荐，不是瞎猜）
    3. 选最优路线 → mmkit run --compile
    4. gate + review 验收
    5. 输出一份总报告

用法
    python pipeline.py --data X.xlsx --y 热阻 --rounds 2
    python pipeline.py selftest
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def match_method(name: str):
    """把方法名映射到 mmkit 命令。返回 (cmd, args) 或 None。

    表在 kb/method_map.json，由 tools/gen_map.py 生成。
    """
    import json
    p = os.path.join(HERE, "kb", "method_map.json")
    if not os.path.exists(p):
        return None
    d = json.load(open(p, encoding="utf-8"))
    for row in d.get("map") or []:
        if row["kw"] in name:
            return row["cmd"], dict(row.get("args") or {})
    return None


def unsupported_reason(name: str):
    import json
    p = os.path.join(HERE, "kb", "method_map.json")
    if not os.path.exists(p):
        return None
    d = json.load(open(p, encoding="utf-8"))
    for row in d.get("unsupported") or []:
        if row["kw"] in name:
            return row["why"]
    return None


def build_proposals(data: str, ycol: str, feats: set, top: int = 3,
                    exclude=(), min_cols: str = "") -> tuple:
    """由 recommend + method_map 生成提案。

    返回 (提案列表, 做不了的清单)。
    做不了的记下来 —— 那是能力边界，不该假装能做。
    """
    import cards
    import mm

    ds = mm.DS(data)
    _drop = {ycol, "样本编号"} | set(exclude or ())
    cands = [c for c in ds.num_names if c not in _drop]
    nums = [c for c in ds.num_names if c not in _drop]
    mins = [c.strip() for c in (min_cols or "").split(",") if c.strip()]
    recs = cards.recommend(feats, top=max(top, 4))

    props, skipped = [], []
    seen = set()
    for i, r in enumerate(recs):
        name = r["method"]
        m = match_method(name)
        if not m:
            why = unsupported_reason(name)
            skipped.append((name[:24], why or "无对应命令"))
            continue
        cmd, args = m
        # 替换占位符
        a = {}
        for k, v in args.items():
            if v == "$data":
                a[k] = data
            elif v == "$y":
                a[k] = ycol
            elif v == "$x":
                a[k] = ",".join(cands[:3]) if cands else ""
            elif v == "$min":
                a[k] = ",".join(mins) if mins else ",".join(nums[-2:])
            else:
                a[k] = v
        # 所有 mmkit 子命令都要 --data，映射表里没写就自动补。
        # 不补的话提案会静默失败：实测 M1 因此进了死路，
        # 结果最优路线被漏掉，最后选了更差的 F3。
        if "--data" not in a and "--ahp" not in a:
            a["--data"] = data

        # 需要 AHP 矩阵但我们没有 —— 跳过，不假装
        if a.get("--ahp"):
            skipped.append((name[:24], "需要成对比较矩阵，未提供"))
            continue
        sig = (cmd, tuple(sorted((k, str(v)) for k, v in a.items())))
        if sig in seen:
            continue
        seen.add(sig)
        # 判据必须能和 metrics 对得上。default_judge 是按字段名匹配的：
        #   cv_rmse_max → 在 metrics 里找含 "rmse" 的键
        #   n_rows_min  → 找 "n_rows"，而 fit 的结果里没有这个键
        # 给错了会导致最优路线被判失败（实测踩过）。
        _crit = ({"cv_rmse_max": 0.05} if cmd == "run"
                 else {"n_rows_min": 1} if cmd == "advise"
                 else {"n_rows_min": 1})
        props.append(dict(
            route_id=f"M{len(props) + 1}",
            title=f"{name[:20]}",
            method=cmd,
            method_args=a,
            success_criteria=_crit,
            falsifiable_assumption=(
                f"如果 {name[:16]} 不适用，该路线不应当优于"
                f"只预测均值的基准"),
        ))

    # 用契约过滤：推荐到的方法映射出的参数可能不合 mmkit 的实际签名
    # （比如 graph 没有 --cost）。让契约做守门人，而不是让流程崩。
    try:
        import contract
        _cmds, _argn = contract.reflect_cmds()
        _good = []
        for _p in props:
            _e = contract.validate(_p, _cmds, _argn)
            if _e:
                skipped.append((_p["title"][:20], "参数不合签名："
                                + str(_e[0])[:40]))
            else:
                _good.append(_p)
        props = _good
    except Exception:                               # noqa: BLE001
        pass

    # 保底：补到 3 条，且必有一条回归。
    # 契约过滤后可能剩不到 3 条，而 check_diversity 要求至少 3 条。
    if not any(p["method"] == "run" for p in props):
        props.insert(0, dict(
            route_id="M0", title="baseline regression", method="run",
            method_args={"--data": data, "--y": ycol,
                         "--x": ",".join(cands[:3])},
            success_criteria={"cv_rmse_max": 0.05},
            falsifiable_assumption="如果因子无关，交叉验证误差应与均值模型相当",
        ))
    _combos = [cands[:1], cands, cands[:max(1, len(cands) - 1)]]
    _k = 0
    while len(props) < 3 and _k < len(_combos):
        _xs = _combos[_k]
        _k += 1
        if not _xs:
            continue
        _sig = (",".join(_xs),)
        if any(p["method_args"].get("--x") == ",".join(_xs)
               for p in props):
            continue
        props.append(dict(
            route_id=f"F{_k}", title=f"factor set {_k}", method="run",
            method_args={"--data": data, "--y": ycol,
                         "--x": ",".join(_xs)},
            success_criteria={"cv_rmse_max": 0.05},
            falsifiable_assumption="如果这组因子无关，误差应与均值模型相当",
        ))
    # 补一条诊断，保证 method 不止一种
    props.append(dict(
        route_id="D1", title="type diagnosis", method="advise",
        method_args={"--data": data},
        success_criteria={"n_rows_min": 1},
        falsifiable_assumption="如果数据无结构，诊断应为 unclear",
    ))
    return props, skipped


def run_pipeline(data: str, ycol: str, texdir: str, rounds: int = 2,
                 xcol: str = "", min_cols: str = "", team: str = "000000",
                 problem: str = "", compile_pdf: bool = True) -> dict:
    """跑完整流程。"""
    import cards
    import mm
    import orchestrate as O

    ds = mm.DS(data)
    feats = cards.features_from_ds(ds)
    recs = cards.recommend(feats, top=3)

    # ── 1. 探索 ──
    props, skipped = build_proposals(
        data, ycol, feats,
        exclude=[c.strip() for c in min_cols.split(",") if c.strip()],
        min_cols=min_cols)
    st = O.run_loop(data, lambda ctx: props, max_rounds=rounds,
                    budget_min=30)

    best_method_args = {}
    if st.best:
        rid = st.best.get("route_id")
        for p in props:
            if p["route_id"] == rid:
                best_method_args = dict(p["method_args"])
                break

    # ── 2. 出稿 ──
    if not xcol:
        _drop = {ycol} | {c.strip() for c in min_cols.split(",") if c.strip()}
        xcol = best_method_args.get("--x") or ",".join(
            [c for c in ds.num_names if c not in _drop][:3])
    cmd = [sys.executable, "mmkit.py", "run", "--data", data,
           "--y", ycol, "--x", xcol,
           "--tex", os.path.join(texdir, "paper.tex"),
           "--team", team, "--problem", problem or f"{ycol} modelling"]
    if min_cols:
        cmd += ["--min", min_cols]
    if compile_pdf:
        # 兜底原则（借 mcmp）：不管质量门过不过，都要出一份稿。
        # --strict 会在硬门失败时 return 2，但稿已经写盘了 ——
        # 竞赛里交了才有分，不交是零。
        # 所以这里用 --compile 而不是 --compile --strict，
        # 由 pipeline 自己汇总 gate 结果并明确报告「过了没有」。
        cmd += ["--compile"]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=HERE)

    # ── 3. 验收 ──
    gate_res = {}
    score_res = {}
    rr = {}
    try:
        import gate
        gate_res = gate.run_all(texdir)
    except Exception as e:                          # noqa: BLE001
        gate_res = dict(error=f"{type(e).__name__}: {e}")
    try:
        import score as sc
        score_res = sc.score_of(texdir, gate_result=gate_res or None)
    except Exception as e:                          # noqa: BLE001
        score_res = dict(error=f"{type(e).__name__}: {e}")
    try:
        import review
        rr = review.run_round(texdir, gate_result=gate_res or None)
    except Exception as e:                          # noqa: BLE001
        rr = dict(error=f"{type(e).__name__}: {e}")

    return dict(
        features=sorted(feats),
        recommended=[r["method"] for r in recs],
        explore=dict(rounds=st.rounds_used,
                     attempts=len(st.attempts),
                     best=st.best.get("brief", "") if st.best else "",
                     stop=st.stop_reason,
                     dead=len(st.dead_ends)),
        proposals=[p["route_id"] + ":" + p["title"] for p in props],
        skipped=skipped,
        x_used=xcol,
        run_exit=r.returncode,
        run_tail=(r.stdout or "").strip().splitlines()[-1:],
        gate=dict(ok=gate_res.get("all_pass"),
                  hard_fail=gate_res.get("hard_fail"),
                  warns=gate_res.get("warns")),
        score=score_res.get("score"),
        review=dict(round=rr.get("round"), converged=rr.get("converged"),
                    reason=rr.get("reason")),
    )


def report(p: dict) -> str:
    L = ["=" * 68, "全流程报告", "=" * 68, ""]
    L.append(f"数据特征　{', '.join(p['features'])}")
    L.append(f"方法推荐　{', '.join(p['recommended'][:3]) or '（无）'}")
    L.append(f"提案　　　{', '.join(p['proposals'])}")
    if p.get("skipped"):
        L.append(f"做不了　　" + "; ".join(f"{a}（{b}）"
                                         for a, b in p["skipped"][:4]))
    L.append("")
    e = p["explore"]
    L.append(f"探索　　　{e['rounds']} 轮 / {e['attempts']} 次尝试 / "
             f"死路 {e['dead']} 条")
    L.append(f"　　　　　停止：{e['stop']}")
    if e["best"]:
        L.append(f"　　　　　最优：{e['best']}")
    L.append("")
    L.append(f"出稿　　　--x {p['x_used']}　exit={p['run_exit']}")
    for ln in p["run_tail"]:
        L.append(f"　　　　　{ln.strip()[:62]}")
    L.append("")
    g = p["gate"]
    L.append(f"质量门　　{'通过' if g.get('ok') else '未通过'}"
             f"（硬门失败 {len(g.get('hard_fail') or [])}，"
             f"警告 {len(g.get('warns') or [])}）")
    L.append(f"分数　　　{p.get('score')}")
    rv = p["review"]
    L.append(f"账本　　　第 {rv.get('round')} 轮，"
             f"{'收敛' if rv.get('converged') else '未收敛'}"
             f"（{rv.get('reason')}）")
    return "\n".join(L)


# ══════════════════════════════════════════════════════════════════════
def selftest() -> int:
    bad = 0
    n = 0

    def ck(name, cond, detail=""):
        nonlocal bad, n
        n += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
              + (f"  — {detail}" if detail else ""))
        if not cond:
            bad += 1

    here = os.path.dirname(os.path.abspath(__file__))
    import cards
    import mm

    data = mm.find_xlsx()
    ck("能找到数据", bool(data), (data or "")[-40:])
    if not data:
        print(f"\nFAILED  0/{n}")
        return 1

    ds = mm.DS(data)
    ycol = [c for c in ds.num_names if "热阻" in c or "y" == c.lower()]
    ycol = ycol[0] if ycol else ds.num_names[-1]
    feats = cards.features_from_ds(ds)

    # selftest 里没有 min_cols —— 这是和 run_pipeline 唯一的区别
    props, skipped = build_proposals(data, ycol, feats)
    ck("能生成提案", len(props) >= 2, f"{len(props)} 条")
    ck("提案不同构（--x 各不同）",
       len({p["method_args"].get("--x", "") for p in props}) >= 2,
       str([p["method_args"].get("--x", "")[:12] for p in props]))
    ck("提案带可证伪陈述",
       all(p.get("falsifiable_assumption") for p in props))
    ck("提案有判据",
       all(p.get("success_criteria") for p in props))

    # 提案要能过 contract
    try:
        import contract
        cmds, argn = contract.reflect_cmds()
        b = contract.validate_batch(props, cmds, argn)
        ck("提案能过契约校验", b["ok"],
           str(b["per_route_errors"] or b["batch_errors"])[:70])
    except Exception as e:                          # noqa: BLE001
        ck("提案能过契约校验", False, f"{type(e).__name__}: {e}")

    # 报告函数
    fake = dict(features=["has_data"], recommended=["多元回归"],
                proposals=["R1:single", "D1:diag"],
                explore=dict(rounds=1, attempts=2, best="R1 OK",
                             stop="达标", dead=0),
                x_used="a,b", run_exit=0, run_tail=["ok"],
                gate=dict(ok=True, hard_fail=[], warns=[]),
                score=100.0,
                review=dict(round=1, converged=True, reason="全绿"))
    txt = report(fake)
    ck("报告能生成", "全流程报告" in txt and "100.0" in txt,
       f"{len(txt)} 字符")

    print(f"\n{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="全流程：探索 → 出稿 → 验收")
    ap.add_argument("cmd", nargs="?", default="selftest",
                    choices=["selftest", "run"])
    ap.add_argument("--data", default="")
    ap.add_argument("--y", default="")
    ap.add_argument("--x", default="")
    ap.add_argument("--min", dest="minc", default="")
    ap.add_argument("--texdir", default="out/fig")
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--team", default="000000")
    ap.add_argument("--problem", default="")
    ap.add_argument("--no-compile", action="store_true")
    a = ap.parse_args(argv)

    if a.cmd == "selftest" or not a.data or not a.y:
        return selftest()

    p = run_pipeline(a.data, a.y, a.texdir, rounds=a.rounds,
                     xcol=a.x, min_cols=a.minc, team=a.team,
                     problem=a.problem,
                     compile_pdf=not a.no_compile)
    print(report(p))
    return 0 if (p["gate"].get("ok") and p["run_exit"] == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
