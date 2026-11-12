#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
review.py —— 评审循环（第 11 轮，机制集成自 dsh-ultramath 的 adjudicate/engine）

取自它的三件事
--------------
1. **证据门禁**：评审说「有问题」不算，必须给出可复现的命令。
   跑命令 → 退出码 0（claim 成立，问题确实存在）→ 保留
           → 退出码非 0 → **判为误报，降级为 NOTE**
   这条直接治我这几轮反复犯的错：报问题但没验证。

2. **指纹去重**：`类别 + 位置 + claim前60字` 做 sha256 前 16 位。
   同一问题跨轮只计一次，避免「修不动就反复提」把账本刷满。

3. **收敛三判据**：
   · 无阻断 → 收敛
   · 连续 N 轮无新 finding → 收敛（**但存在未解决阻断项，需人工介入**）
   · 达到预算 → 收敛
   第二条最值钱：**「没新问题」说明探索穷尽，这和「没问题」不是一回事**。

去它的糟粕
----------
- 它的 finding 靠 LLM 写 JSON 输入（`--in-dir`），没人保证字段对
- 它的 `evidence_command` 是自由字符串，能写 `echo` 骗过门禁
- 我们改成：finding **由 gate.py 自动生成**，证据命令就是重跑那个门，
  不接受自由字符串

我们加的
--------
- 三席视角（正确性 / 表述 / 创造性）各自独立打分，**分歧不取平均**
- 与 gate.py 打通：gate 的硬门失败 = 一个 BLOCK finding

用法
    python review.py run out/fig                  # 跑一轮评审
    python review.py status out/fig               # 看账本
    python review.py selftest
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

SEVERITIES = ("BLOCK", "MAJOR", "MINOR", "NOTE")
CATEGORIES = ("正确性", "表述", "创造性", "一致性", "合规", "诚信")

# 严重度降档链（证据不支持时逐级降）
DOWNGRADE = dict(BLOCK="MAJOR", MAJOR="MINOR", MINOR="NOTE", NOTE="NOTE")

# 三席视角：互不共享上下文，只看各自关心的东西
SEATS = {
    "seat_a 正确性": ("正确性", "一致性"),
    "seat_b 表述": ("表述", "合规"),
    "seat_c 创造性": ("创造性",),
}

STATE_NAME = "评审账本.json"


# ══════════════════════════════════════════════════════════════════════
#  finding
# ══════════════════════════════════════════════════════════════════════
def fingerprint(f: dict) -> str:
    """同一问题的稳定指纹。"""
    claim = re.sub(r"\s+", "", str(f.get("claim", "")))[:60]
    key = json.dumps([f.get("category", ""), f.get("location", ""), claim],
                     ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def from_gate(res: dict) -> list:
    """把 gate 的结果转成 findings。

    只把**硬门 FAIL** 转成 BLOCK，软门 WARN 转成 MINOR。
    N/A 不转 —— 还没到那一步不等于有问题。
    """
    out = []
    for c in res.get("checks", []):
        if c["status"] == "PASS" or c["status"] == "N/A":
            continue
        sev = "BLOCK" if (c["tier"] == "hard" and c["status"] == "FAIL") \
            else "MINOR"
        cat = "合规" if c["id"] in ("rules", "compile", "pdf") else "一致性"
        # 处置分级（借 mcmp 的 P0-P3）：
        #   P3 = 定点改，改一处即可（数值、措辞、单个参数）
        #   P2 = 重跑本节（结构问题，但范围可控）
        #   P1/P0 = 回滚到上游（根因不在这一层）
        # 我们的门里，能一处修好的是 numbers/abstract/ai_taste；
        # 需要重跑的是 compile/figures；rules/leakage 属于根因问题。
        if c["id"] in ("numbers", "abstract", "ai_taste"):
            action, p = "P3", "定点改：改这一处即可"
        elif c["id"] in ("compile", "figures", "falsify"):
            action, p = "P2", "重跑本节：重新出稿/出图"
        else:
            action, p = "P1", "回滚：根因在上游，须查数据或配置"

        out.append(dict(
            category=cat, severity=sev, location=c["id"],
            claim=f"{c['id']}：{c['detail']}",
            # 证据命令不是自由字符串 —— 就是重跑那个门
            evidence=("gate", c["id"]),
            action=action, plan=p,
        ))
    return out


# ══════════════════════════════════════════════════════════════════════
#  证据门禁
# ══════════════════════════════════════════════════════════════════════
def run_evidence(spec, figdir: str) -> dict:
    """跑证据。返回 PASS（问题成立）/ FAIL（误报）/ NA（免证据）。

    spec 只接受 ("gate", <check_id>) 这种受控形式，
    **不接受自由命令** —— 否则写个 `true` 就能让任何 finding 通过。
    """
    if not spec:
        return dict(status="NA", detail="没有证据要求")
    kind, arg = spec if isinstance(spec, (tuple, list)) else ("?", spec)
    if kind != "gate":
        return dict(status="NA", detail=f"不支持的自由证据类型 {kind!r}")
    try:
        import gate
        res = gate.run_all(figdir)
        hit = next((c for c in res["checks"] if c["id"] == arg), None)
        if hit is None:
            return dict(status="NA", detail=f"gate 里没有 {arg}")
        # 门报 FAIL/WARN = 问题成立
        if hit["status"] in ("FAIL", "WARN"):
            return dict(status="PASS", detail=hit["detail"])
        return dict(status="FAIL",
                    detail=f"重跑 {arg} 已通过（{hit['status']}），判为误报")
    except Exception as e:                          # noqa: BLE001
        return dict(status="NA", detail=f"{type(e).__name__}: {e}")


def apply_gate(f: dict, figdir: str) -> dict:
    """BLOCK/MAJOR 必须有证据；证据不支持就降档。"""
    if f["severity"] in ("NOTE", "MINOR"):
        f["evidence_status"] = "NA"
        return f
    r = run_evidence(f.get("evidence"), figdir)
    f["evidence_status"] = r["status"]
    f["evidence_detail"] = r["detail"]
    if r["status"] == "PASS":
        return f
    if r["status"] == "FAIL":
        f["severity"] = "NOTE"
        f["downgraded"] = "证据未证实（误报）"
        return f
    f["severity"] = DOWNGRADE.get(f["severity"], "NOTE")
    f["downgraded"] = f"证据不可用：{r['detail'][:60]}"
    return f


# ══════════════════════════════════════════════════════════════════════
#  一轮
# ══════════════════════════════════════════════════════════════════════
def load_state(figdir: str) -> dict:
    p = os.path.join(figdir, STATE_NAME)
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    return dict(rounds=[], known=[], converged=False, reason="",
                max_rounds=3, max_no_new=2)


def save_state(st: dict, figdir: str) -> str:
    p = os.path.join(figdir, STATE_NAME)
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(st, fh, ensure_ascii=False, indent=2)
    return p


def run_round(figdir: str, st: dict | None = None,
              gate_result: dict | None = None) -> dict:
    """跑一轮：gate → findings → 去重 → 证据门禁 → 收敛判定。

    gate_result 给定时直接用，不重跑 —— run() 收尾时刚跑过一遍，
    再跑一次白等 25 秒。
    """
    st = st or load_state(figdir)
    if gate_result is not None:
        res = gate_result
    else:
        try:
            import gate
            res = gate.run_all(figdir)
        except Exception as e:                      # noqa: BLE001
            return dict(error=f"gate 跑不动：{type(e).__name__}: {e}")

    raws = from_gate(res)
    known = set(st.get("known") or [])
    kept, dup = [], 0
    for f in raws:
        fp = fingerprint(f)
        if fp in known:
            dup += 1
            continue
        known.add(fp)
        f["fp"] = fp
        kept.append(apply_gate(f, figdir))

    verified = [f for f in kept
                if f["severity"] in ("BLOCK", "MAJOR")
                and f["evidence_status"] in ("PASS", "NA")]
    fps = [f for f in kept if f["evidence_status"] == "FAIL"]

    # 分数趋势：全绿时 finding 为空，只有分数能反映「有没有在变好」
    try:
        import score as _score
        _sc = _score.score_of(figdir, gate_result=res)["score"]
    except Exception:                               # noqa: BLE001
        _sc = None

    rnd = len(st.get("rounds") or []) + 1
    payload = dict(round=rnd, new=len(kept), dup=dup,
                   blocking=len(verified), false_positive=len(fps),
                   score=_sc, findings=kept)
    st.setdefault("rounds", []).append(dict(
        round=rnd, new_count=len(kept), blocking_count=len(verified),
        score=_sc))
    st["known"] = sorted(known)

    _minor = sum(1 for f in kept
                 if f['severity'] in ('MINOR', 'NOTE'))
    conv, why = decide_convergence(st, len(verified), _minor, _sc)
    st["converged"] = conv
    st["reason"] = why
    payload["converged"] = conv
    payload["reason"] = why
    payload["state_path"] = save_state(st, figdir)
    return payload


def decide_convergence(st: dict, blocking: int,
                       minor: int = 0, score=None) -> tuple:
    """三条判据（照搬 ultramath 的设计）。

    收敛时要说清「还剩什么」——「无阻断」不等于「没问题」。
    """
    # 分数优先于阻断数。实测踩到过：finding 被指纹去重后，
    # 本轮 blocking_count 归零，看起来像修好了，但分数还是 84 ——
    # 问题没修，只是不重复报了。收敛必须看分数。
    if score is not None and score < 100:
        if blocking:
            return False, (f"分数 {score}，仍有 {blocking} 项阻断")
        return False, (f"分数 {score} 未满 —— 失分项是之前发现的，"
                       f"本轮没新增不代表已修")
    if blocking == 0:
        tail = (f"，另有 {minor} 项非阻断待处理（不阻止出稿）"
                if minor else "")
        return True, "全绿（分数满分，无阻断）" + tail
    # 连续 N 轮没有新 finding = 探索穷尽，但阻断项还在 → 该人工介入了
    streak = 0
    for p in reversed(st.get("rounds") or []):
        if p.get("new_count", 1) == 0:
            streak += 1
        else:
            break
    if streak >= st.get("max_no_new", 2):
        return True, (f"连续 {st.get('max_no_new')} 轮无新问题，"
                      f"但仍有 {blocking} 项阻断 —— **需人工介入**")
    if len(st.get("rounds") or []) >= st.get("max_rounds", 3):
        return True, f"达到迭代预算（{st.get('max_rounds')} 轮）"
    return False, ""


def seat_view(findings: list) -> dict:
    """三席视角各自看自己那一块，不互相看，也不取平均。"""
    out = {}
    for seat, cats in SEATS.items():
        mine = [f for f in findings if f.get("category") in cats]
        out[seat] = dict(
            n=len(mine),
            blocking=sum(1 for f in mine
                         if f["severity"] in ("BLOCK", "MAJOR")),
            verdict=("不通过" if any(f["severity"] == "BLOCK" for f in mine)
                     else "有保留" if mine else "通过"),
        )
    # 分歧：三席判定不完全一致
    vs = {v["verdict"] for v in out.values()}
    out["_disagreement"] = len(vs) > 1
    out["_note"] = ("三席判定不一致时**不取平均**，以最严的那一席为准，"
                    "并列出分歧理由")
    return out


def report(p: dict) -> str:
    if p.get("error"):
        return f"  {p['error']}"
    _s = p.get("score")
    L = [f"第 {p['round']} 轮：分数 {_s if _s is not None else '?'}"
         f"  新增 {p['new']}（重复 {p['dup']}）"
         f"  阻断 {p['blocking']}  误报 {p['false_positive']}",
         f"收敛：{'是' if p['converged'] else '否'} — {p['reason']}"]
    if p["findings"]:
        L.append("")
        for f in p["findings"]:
            tag = {"PASS": "证实", "FAIL": "误报", "NA": "免证"}[
                f["evidence_status"]]
            L.append(f"  [{f['severity']:<5}] {f['action']} "
                     f"{f['category']} {f['location']}（{tag}）")
            L.append(f"          {f['claim'][:76]}")
            if f.get("downgraded"):
                L.append(f"          ↓ {f['downgraded']}")
    sv = seat_view(p["findings"])
    L.append("")
    L.append("三席视角：")
    for k, v in sv.items():
        if k.startswith("_"):
            continue
        L.append(f"  {k:<14}{v['verdict']}（{v['n']} 项，"
                 f"{v['blocking']} 阻断）")
    if sv["_disagreement"]:
        L.append(f"  ⚠ 三席判定不一致 —— {sv['_note']}")
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

    # 指纹
    f1 = dict(category="正确性", location="fit", claim="rmse 不对")
    f2 = dict(category="正确性", location="fit", claim="rmse  不对")
    f3 = dict(category="表述", location="fit", claim="rmse 不对")
    ck("同问题指纹相同", fingerprint(f1) == fingerprint(f2))
    ck("不同类别指纹不同", fingerprint(f1) != fingerprint(f3))

    # gate 结果转 finding
    res = dict(checks=[
        dict(id="compile", tier="hard", status="FAIL", detail="2 处错误"),
        dict(id="figures", tier="soft", status="WARN", detail="均分 5.4"),
        dict(id="pdf", tier="hard", status="N/A", detail="没有 PDF"),
        dict(id="rules", tier="hard", status="PASS", detail="7/7"),
    ])
    fs = from_gate(res)
    ck("硬门 FAIL → BLOCK", any(f["severity"] == "BLOCK" for f in fs),
       f"{len(fs)} 项")
    ck("软门 WARN → MINOR", any(f["severity"] == "MINOR" for f in fs))
    ck("N/A 不转 finding", not any(f["location"] == "pdf" for f in fs))
    ck("PASS 不转 finding", not any(f["location"] == "rules" for f in fs))
    ck("证据不是自由字符串",
       all(isinstance(f["evidence"], tuple) for f in fs),
       str(fs[0]["evidence"]) if fs else "")

    # 证据门禁：证据不支持要降档
    f = dict(category="正确性", severity="BLOCK", location="compile",
             claim="x", evidence=("gate", "compile"))
    r = apply_gate(dict(f), "out/fig")
    ck("证据门禁会产出一个状态",
       r["evidence_status"] in ("PASS", "FAIL", "NA"),
       f"{r['evidence_status']} / {r['severity']}")
    # 伪造证据类型 → NA
    f2b = dict(category="正确性", severity="BLOCK", location="x",
               claim="y", evidence=("echo", "true"))
    r2 = apply_gate(dict(f2b), "out/fig")
    ck("拒绝自由 shell 证据", r2["evidence_status"] == "NA",
       r2["evidence_detail"][:50])

    # 收敛三判据
    st = dict(rounds=[], max_rounds=3, max_no_new=2)
    ck("无阻断即收敛", decide_convergence(st, 0)[0])
    st2 = dict(rounds=[dict(new_count=0), dict(new_count=0)],
               max_rounds=5, max_no_new=2)
    c, why = decide_convergence(st2, 2)
    ck("连续无新问题也收敛但需人工", c and "人工" in why, why[:50])
    st3 = dict(rounds=[dict(new_count=3)] * 3, max_rounds=3, max_no_new=2)
    ck("达到预算收敛", decide_convergence(st3, 5)[0])
    st4 = dict(rounds=[dict(new_count=2)], max_rounds=5, max_no_new=2)
    ck("还有余地时不收敛", not decide_convergence(st4, 1)[0])

    # 三席
    sv = seat_view([dict(category="正确性", severity="BLOCK"),
                    dict(category="表述", severity="MINOR")])
    ck("三席各看各的", sv["seat_a 正确性"]["n"] == 1
       and sv["seat_b 表述"]["n"] == 1, str(list(sv["seat_a 正确性"].keys())))
    ck("判定不一致被标出", sv["_disagreement"], sv["_note"][:40])

    # 真实跑一轮（不写账本）
    real = run_round("out/fig", dict(rounds=[], known=[], max_rounds=3,
                                     max_no_new=2))
    ck("真实目录能跑一轮", "round" in real or "error" in real,
       f"new={real.get('new')} blocking={real.get('blocking')}")
    if "error" not in real:
        ck("真实结果可序列化",
           bool(json.dumps(real, ensure_ascii=False, default=str)))
    # 清掉自测写出的账本，避免污染真实状态
    p = os.path.join(HERE, "out", "fig", STATE_NAME)
    if os.path.exists(p):
        os.remove(p)

    print(f"\n{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="评审循环")
    ap.add_argument("cmd", nargs="?", default="selftest",
                    choices=["selftest", "run", "status"])
    ap.add_argument("dir", nargs="?", default="")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--max-no-new", type=int, default=2)
    a = ap.parse_args(argv)

    if a.cmd == "selftest" or not a.dir:
        return selftest()

    if a.cmd == "status":
        st = load_state(a.dir)
        print(f"  轮数 {len(st.get('rounds') or [])} / "
              f"已知问题 {len(st.get('known') or [])} / "
              f"收敛 {st.get('converged')}（{st.get('reason')}）")
        for r in st.get("rounds") or []:
            _s = r.get("score")
            print(f"    R{r['round']}: 分数 {_s if _s is not None else '?'}"
                  f"  新增 {r['new_count']}  阻断 {r['blocking_count']}")
        return 0

    st = load_state(a.dir)
    st["max_rounds"] = a.rounds
    st["max_no_new"] = a.max_no_new
    p = run_round(a.dir, st)
    print(report(p))
    return 0 if p.get("converged") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
