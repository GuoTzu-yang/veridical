#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
freeze.py —— 数字冻结与传播检测（第 10 轮，协议集成自 dsh-ultramath）

它的协议（在 ultramath-engineer 的 agent 预设里，只有文字没有代码）
-------------------------------------------------------------------
A. 数字冻结：每个关键数值记「值 + 单位 + 来源」三元组，来源必须可追溯
   （CSV 单元格 / 脚本输出行 / 公式编号），**论文每个数字必须能在冻结表
   找到出处**。
B. 传播检测：每次改代码/方法/结果后，grep 论文与推导，找可能 stale 的
   旧数值引用。禁止「改完代码忘改论文数字」。
C. 与独立验算衔接：验算以冻结表为对照基准，分歧 >30% FAIL /
   10-30% SUSPECT / <10% 一致。

为什么我们需要它
----------------
我们踩过一次：`baseline_rmse` 在 `mm.fit → rep["fit"] → ctx → paper`
三层 dict 重构里丢了，论文那一节整段没写出来，而**所有检查都是绿的**
——因为没人核对「该有的数在不在」。

`verify.py` 做的是「tex 里的数有没有出处」，是**单向**的。
冻结表多了两件事：
    1. 反向核对：插件算出来的关键数，论文里有没有用上
    2. 传播检测：数值变了，论文里的旧引用要能被找出来

用法
    python freeze.py write --data X.xlsx --y 热阻 --x 宽度 --out 冻结数字.json
    python freeze.py check out/fig/paper.tex --frozen 冻结数字.json
    python freeze.py stale --frozen 冻结数字.json --old 旧冻结数字.json
    python freeze.py selftest
"""

from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# 哪些 key 算「关键数值」——不是所有浮点都值得冻结
# 问题 4/5 的关键量在 rep.q4.robust.worst_regret 这种 depth-3 位置，
# 原来只靠 depth<=2 收集，于是 0.283 / 0.391 / 8.1% 全部漏冻，
# 论文里就成了「找不到出处」。这里把它们的键名显式加进来。
KEY_HINTS = ("rmse", "r2", "bp", "front", "coverage", "cond", "aic",
             "mean", "std", "min", "max", "beta", "coef", "p_value",
             "cv", "gain", "delta", "score", "weight",
             "regret", "drift", "oob", "pct", "share", "worst",
             "n_weights", "n_pred", "n_hit", "idx", "shift",
             "rel", "top_share", "drift_abs_mean", "drift_p95",
             "exceed_5pct", "half", "width_rel", "analytic", "cv" "bp", "bp_crit", "skew", "kurt", "jb", "c_trend", "c_each",
             "worse", "coords_flat")


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def collect(obj, path="", out=None, depth=0) -> list:
    """递归收集「关键数值」及其 JSON 路径（路径就是来源）。"""
    if out is None:
        out = []
    if depth > 8:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            collect(v, f"{path}.{k}" if path else str(k), out, depth + 1)
    elif isinstance(obj, list):
        # 列表里的数值——只取前 20 个，避免把 84 行数据全冻进去
        for i, v in enumerate(obj[:20]):
            collect(v, f"{path}[{i}]", out, depth + 1)
    elif _is_number(obj):
        key = path.split(".")[-1].split("[")[0].lower()
        if any(h in key for h in KEY_HINTS) or depth <= 2:
            out.append(dict(path=path, value=float(obj)))
    return out


def freeze(rep: dict, source: str = "", y: str = "",
           x=None) -> dict:
    """把一次运行的报告冻成可核对的表。

    y / x 一起记下来：泄漏检查要拿它们去查「自变量里有没有混进响应」。
    论文是英文、列名被转成符号，从正文反查是查不到的。
    """
    items = collect(rep)
    return dict(
        source=source,
        y=y or (rep.get("y") or ""),
        x=list(x or rep.get("x") or []),
        n=len(items),
        items=items,
        # 反查表：数值 -> 路径（用于"论文里这个数从哪来"）
        by_value={},
        note=("每项是「值 + 来源路径」；单位在来源路径里能看出来"
              "（如 dimensionless 前缀）。论文引用时按数值匹配。"),
    )


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()


def _found_in_paper(num: float, tex: str) -> bool:
    """这个数在论文里出现过吗？

    容忍四类常见写法的等价形态（verify.py 里验证过这几类）：
        0.0074342  ↔  0.00743（四舍五入）
        0.5918     ↔  59.18%（百分比）
        0.5918     ↔  59.18\\%（LaTeX 转义）
    """
    if num == 0:
        return "0" in tex
    cands = set()
    for p in (2, 3, 4, 5, 6):
        cands.add(f"{num:.{p}f}")
    # 百分比
    for p in (1, 2):
        cands.add(f"{num * 100:.{p}f}")
        cands.add(f"{num * 100:.{p}f}\\%")
    # 科学计数
    cands.add(f"{num:.2e}")
    for c in cands:
        if c in tex:
            return True
        # 去掉尾随 0 再试（0.7500 → 0.75）
        stripped = c.rstrip("0").rstrip(".")
        if stripped and stripped in tex:
            return True
    return False


def _decimals(tok: str) -> int:
    """书写精度 → 小数位数（可为负）。**唯一实现在 verify._written_decimals。**

    第 122 轮把这里的第二份实现删掉了。原来 freeze 与 verify 各有一套
    精度换算，后果是同一份产物在 gate 与 verify 两个门里判决不同
    （实测 age_struct：gate PASS 116/116、verify 报 88.0%）。
    现在只剩一处，改那边这这边自动跟着变。

    （历史：旧实现 `len(tok.split(".")[1])` 对 "5.924e+04" 返回 7，
    要求论文值精确到 1e-7 —— 而生成器用 %.3g/%.4g 打印，
    5 篇模板卷 106/152 个未溯源全是这一类。）
    """
    import verify as _V
    return _V._written_decimals(tok)


def _match_written(v: float, dec: int, frozen_vals) -> bool:
    """论文写的 v（保留 dec 位）是否是某个冻结值的合法写法。

    三个方向都试：原值、×100（百分比写法）、÷100（小数写法）。

    第 122 轮（红队独立验收 §2.4-②）：
    `tol` 原来带 `+1e-12` 的**绝对**地板。当时看不出来，因为 dec 最大也就
    几位小数；精度判据修好之后 dec 可以到 18（`1.96e-11` 这类），
    `0.5*10**-18 = 5e-19` 远小于 1e-12，地板反而成了真容差 —— 于是
    1e-13 量级的 token 能被 `0.0` 或 `1e-17` 解释（实测 5 篇 9 例）。

    但**不能简单删掉地板**：`0.78751` 与真值 `0.787505` 的差是
    `5.0000000000287557e-06`，比半格 `5e-6` 大 2.9e-17（浮点表示误差），
    删掉地板就会把「恰好半格的合法舍入」判成无源 —— 实测 23 题里
    heat_sink / life_exp / dwts2026c 各冒出一到两个假阳性。

    正确做法是**相对余量**：`tol = 0.5*10^-dec * (1 + 1e-9)`。
    它吸收「恰好半格」时的浮点误差（量级 1e-16 相对），又把容差锁在
    该书写精度的量级上 —— dec=17 时 tol≈5e-18，仍挡得住 1e-13 的假通过。
    """
    tol = 0.5 * (10.0 ** -dec) * (1.0 + 1e-9)
    for f in frozen_vals:
        for cand_v, cand_f in ((abs(v), abs(f)),
                               (abs(v), abs(f) * 100.0),
                               (abs(v), abs(f) / 100.0)):
            if abs(cand_v - cand_f) <= tol:
                return True
    return False


def check_paper(tex: str, frozen: dict, must: int = 3,
                max_untraced: float = 0.10,
                single_point: bool = True,
                data_values=None, strict_source: bool = True,
                single_point_min_dec: int = 3) -> dict:
    """论文里的关键数，能不能在冻结表找到出处？

    判据（第 114 轮）：
      ① 每个候选值按其**书写精度**四舍五入后，必须等于某个冻结值
         （或它的百分比/小数写法）；
      ② 未溯源比例 <= max_untraced（容忍版面常数）；
      ③ **单点检测**：只要有一个 >= single_point_min_dec 位小数的值未溯源，
         就判失败 —— 这是种子缺陷基准逼出来的：10% 额度会吸收单个编造数。

    `max_untraced` / `must` / `single_point_min_dec` 都是**可调参数**，
    它们是设计选择不是数学定理（唯一是定理的是 `_match_written` 的半格容差）。
    第 123 轮加了 `single_point_min_dec`，为 `tools/param_sensitivity.py`
    能扫描「这条单点规则到底有多敏感」——参数值不许藏在函数体里。
    """
    # 先剥掉 LaTeX 的可选参数：\includegraphics[width=0.68\textwidth]
    # 以及正文里**举例用的字面量**：\code{3.3342e-12}、\verb|arXiv:2211.09527|
    # 它们是在讲分词器缺陷，不是测量值（第 114 轮：单点检测上线后立刻被点名）。
    # 参考文献条目里的卷期页码/arXiv 编号不是测量（与 verify.py 同一条规则）
    tex = re.sub(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}",
                 " ", tex, flags=re.S)
    # 第 118 轮：不再自己分词。走 verify.extract_numbers（全量 token），
    # 这里只过滤「带小数」的那些 —— 一套抽取规则，两个视图。
    # 这样 numbers 与 verify 永远不会给出互相矛盾的判决。
    try:
        import verify as _V
        _all = _V.extract_numbers(tex, skip_meta=False)
    except Exception:                                   # noqa: BLE001
        _all = []
    toks = [t for t, _line in _all if "." in t]
    # 第 122 轮（红队独立诊断 §3.5a）：整数 token 不进候选这件事，
    # 原来是**静默**的。后果是判据结果部分取决于排版选择 ——
    # 把 `:.4g` 改成 `:.0f`，一批数就从「受检」变成「免检」。
    # 这里把「有多少个整数没纳入」明写出来，让边界可见而不是被利用。
    # 判决仍只用带小数的 token：整数里混着行号/年份/表号（A_struct），
    # 全判会制造大量假阳性（实测 4 道题会因此变红，而变红的
    # 全是 Pareto 前沿表的 Design 列编号 1009/1016/1037）。
    n_int_skipped = sum(1 for t, _l in _all if "." not in t)
    pairs = []
    for tok in toks:
        try:
            v = float(tok)
        except ValueError:
            continue
        # 第 122 轮：原来 `abs(v) < 1e6` 直接把大数丢掉 ——
        # 而「移动量是 +24969352.7%」这类最可疑的数恰好在大数一侧。
        # 实测去掉上限对当前语料零代价（那些数经 ×100 分支能正确
        # 匹配到 q5_tradeoff.shift / per.rel），所以不再设上限，
        # 只挡非有限值。
        if v != v or v in (float("inf"), float("-inf")):
            continue
        pairs.append((v, _decimals(tok)))
    # 同一个值可能以不同精度出现：按 (值, 精度) 去重
    seen = set()
    uniq = []
    for v, dec in pairs:
        key = (round(v, 6), dec)
        if key in seen:
            continue
        seen.add(key)
        uniq.append((v, dec))

    frozen_vals = [it["value"] for it in frozen.get("items", [])]
    traced, untraced = [], []
    # 第 118 轮：输入表里的观测值（E 类）应算「可解释」——
    # 它该追到输入文件，而不是追到某次计算。论文自己的分类就是这个主张，
    # 判据不认它会把这 6 道题判红，而它们其实只是抄了原始数据。
    n_data = 0
    for v, dec in uniq:
        if _match_written(v, dec, frozen_vals):
            traced.append(v)
        elif data_values and round(v, 6) in data_values:
            traced.append(v)
            n_data += 1
        else:
            untraced.append((v, dec))

    n = len(uniq)
    ratio = (len(untraced) / n) if n else 0.0
    hp = [(v, d) for v, d in untraced if d >= single_point_min_dec]
    # A1（第 120 轮）：数字太少不能算通过 —— 空稿曾报「0/0 可溯源，通过」。
    # 原来写的是 len(traced) >= min(must, n)，n=0 时恒真。
    few = n < must
    # A2：冻结表必须交代它是谁生成的，且条目要带来源路径；
    # 否则「拿论文自己的数字生成冻结表」就能自证 100%。
    _gf = str(frozen.get("generated_from") or "").strip()
    if not _gf:
        _src_ok = False
    else:
        _p = _gf if os.path.isabs(_gf) else os.path.join(HERE, _gf)
        _src_ok = os.path.exists(_p)
    _paths = [str(it.get("path") or "") for it in (frozen.get("items") or [])]
    _self_proving = bool(_paths) and all(
        p.strip().lower() in ("", "self", "paper", "tex") for p in _paths)
    # 第 122 轮（红队独立验收 §3-④）：判死的时候必须说清是哪一条判的。
    # 原来 detail 仍是「4/4 可溯源（0.0%）」却 FAIL —— 读日志的人只看到
    # 「0% 无出处却红」，会去查错方向。把每条判死理由写成一句话。
    _reasons = []
    if few:
        _reasons.append(f"候选数 {n} 少于下限 {must}（空稿/短稿不算通过）")
    if ratio > max_untraced:
        _reasons.append(f"未溯源 {ratio:.1%} 超过 {max_untraced:.0%}")
    if strict_source and not _src_ok:
        _reasons.append(
            "冻结表没写 generated_from（或它指向的文件不存在）——"
            "交稿要求能追到生成它的脚本")
    if _self_proving:
        _reasons.append(
            "冻结表自证：条目 path 全是 self/paper/tex，等于拿论文自己当出处")
    if single_point and hp:
        _reasons.append(
            f"{len(hp)} 个 ≥3 位小数的值未溯源（交稿单点严判）")
    return dict(
        ok=not _reasons,
        reasons=_reasons,
        n_numbers=n, n_traced=len(traced),
        untraced_ratio=round(ratio, 4),
        untraced=[v for v, _d in untraced[:20]],
        high_precision_untraced=[v for v, _d in hp[:5]],
        high_precision_bad=bool(hp),
        n_from_data=n_data,
        # 未纳入判定的整数 token 数。判决不用它，但必须报出来 ——
        # 否则「把小数改成整数」就是一条静默的免检通道。
        n_int_not_judged=n_int_skipped,
        few_numbers=few,
        frozen_has_source=_src_ok,
        frozen_self_proving=_self_proving,
        note=("未溯源值要么是笔误，要么是手写常数；"
              "单点高精度未溯源一律判失败（声称可溯源就要做到）。"),
    )

def _close(a: float, b: float, rel: float = 0.02) -> bool:
    """两个数是否「同一个值」。

    第 114 轮的修正：原来只有 2% 相对容差，于是任何与真实值相差 2% 以内的
    编造数都被判为溯源成功 —— 而真实测量值有 6~8 位有效数字，2% 的邻域
    足够藏一个假数。现在：
      · 幅度大（>=1）→ 相对容差 1e-4（四位小数以内算同一个数）
      · 幅度小（<1） → 绝对容差 1e-6
    仍然保留 rel 参数，供「百分比 vs 小数」这类跨量纲比较显式放宽。
    """
    if a == b:
        return True
    if rel != 0.02:                     # 调用方显式放宽时按原语义
        d = max(abs(a), abs(b))
        return d > 0 and abs(a - b) / d <= rel
    if max(abs(a), abs(b)) >= 1:
        return abs(a - b) <= 1e-4
    return abs(a - b) <= 1e-6


def detect_stale(old: dict, new: dict) -> dict:
    """传播检测：哪些数的值变了？

    这是「改完代码忘改论文数字」的防线。
    """
    old_map = {it["path"]: it["value"] for it in old.get("items", [])}
    new_map = {it["path"]: it["value"] for it in new.get("items", [])}
    changed, added, removed = [], [], []
    for p, v in new_map.items():
        if p not in old_map:
            added.append(dict(path=p, value=v))
        elif not _close(v, old_map[p], 1e-9):
            changed.append(dict(path=p, old=old_map[p], new=v,
                                delta=round(v - old_map[p], 8)))
    for p, v in old_map.items():
        if p not in new_map:
            removed.append(dict(path=p, value=v))
    return dict(n_changed=len(changed), changed=changed[:20],
                n_added=len(added), added=added[:10],
                n_removed=len(removed), removed=removed[:10],
                needs_update=bool(changed or removed))


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

    rep = dict(
        fit=dict(best_rmse=0.0074342, r2=0.5918, n=84,
                 cands=[dict(label="linear", rmse=0.0074342),
                        dict(label="quadratic", rmse=0.0088)]),
        robustness=dict(bp=5.87, bp_crit=7.81, n_stable=2),
        opt=dict(front=9, n_obj=2),
    )
    fz = freeze(rep, "mmkit run")
    ck("能收集关键数值", fz["n"] >= 5, f"{fz['n']} 项")
    ck("来源是可追溯路径",
       all("." in it["path"] or "[" in it["path"] for it in fz["items"]),
       fz["items"][0]["path"])
    ck("冻结值正确",
       any(_close(it["value"], 0.0074342, 1e-9) for it in fz["items"]))

    # 论文核对：写对了
    tex_ok = (r"CV RMSE of $0.00743$ with $R^2 = 59.18\%$ on $n = 84$ "
              r"observations; the Pareto front holds $9$ points.")
    r = check_paper(tex_ok, fz, must=3)
    ck("论文里对得上的数被认出", r["n_traced"] >= 2,
       f"traced {r['n_traced']}/{r['n_numbers']}")

    # 论文核对：写错了（0.00734 vs 0.0074342）
    tex_bad = r"CV RMSE of $0.00911$ which is wrong entirely."
    r2 = check_paper(tex_bad, fz, must=1)
    ck("论文里对不上的数被抓出", 0.00911 in r2["untraced"],
       f"untraced={r2['untraced'][:3]}")

    # 百分比 / 千分位写法
    ck("百分比等价识别", _found_in_paper(0.5918, r"R^2 = 59.18\%"))
    ck("四舍五入等价识别", _found_in_paper(0.0074342, "0.00743"))
    ck("尾随零等价识别", _found_in_paper(0.75, "0.7500"))

    # 传播检测
    rep2 = json.loads(json.dumps(rep))
    rep2["fit"]["best_rmse"] = 0.0071
    fz2 = freeze(rep2, "mmkit run")
    st = detect_stale(fz, fz2)
    ck("传播检测发现值变了", st["needs_update"] and st["n_changed"] >= 1,
       f"{st['n_changed']} 项变化")
    ck("变化项带新旧值和差",
       all({"old", "new", "delta"} <= set(c) for c in st["changed"]),
       str(st["changed"][0])[:70] if st["changed"] else "")

    # 没变的情况
    st2 = detect_stale(fz, freeze(rep, "same"))
    ck("没变时不报 stale", not st2["needs_update"])

    # 落盘往返
    p = os.path.join(HERE, "out", "freeze_selftest.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(fz, fh, ensure_ascii=False, indent=2)
    back = json.load(open(p, encoding="utf-8"))
    ck("冻结表可落盘往返", back["n"] == fz["n"], f"{back['n']} 项")

    # ── 第 123 轮：把「半格边界」钉死 ──
    # 这段坑在 _match_written 的 docstring 里写了 7 行，**断言原来是 0 条**。
    # 后果：删掉 +1e-12 绝对地板之后冒出 5 个假阳性
    # （heat_sink 0.78751 / 0.73916、life_exp 32.95、dwts2026c 98.3 / 78.8），
    # 而 run_all 一条都没抓到 —— 是红队的探针先发现的。
    # 现在四个方向各钉一条：合法舍入必须过，地板假通过必须红。
    ck("半格边界：0.78751 ← 0.787505 应通过（合法舍入）",
       _match_written(0.78751, 5, [0.787505]),
       "差 5.0000000000287557e-06，比半格大 2.9e-17")
    ck("半格边界：32.95 ← 32.945 应通过（合法舍入）",
       _match_written(32.95, 2, [32.945]))
    ck("半格边界：2.0839e-13 ← 0.0 应判红（地板假通过）",
       not _match_written(2.0839e-13, 13, [0.0]),
       "1e-13 量级不能由 0.0 解释")
    ck("半格边界：1e-17 ← 0.0 应判红（地板假通过）",
       not _match_written(1e-17, 17, [0.0]))

    print(f"\n{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="数字冻结与传播检测")
    ap.add_argument("cmd", nargs="?", default="selftest",
                    choices=["selftest", "write", "check", "stale"])
    ap.add_argument("--data", default="")
    ap.add_argument("--y", default="")
    ap.add_argument("--x", default="")
    ap.add_argument("--out", default="冻结数字.json")
    ap.add_argument("--frozen", default="")
    ap.add_argument("--old", default="")
    ap.add_argument("tex", nargs="?", default="")
    a = ap.parse_args(argv)

    if a.cmd == "selftest":
        return selftest()

    if a.cmd == "write":
        if not (a.data and a.y):
            print("  write 需要 --data 与 --y")
            return 2
        import mm
        import mmkit
        ds = mm.DS(a.data)
        xs = ds.pick(a.x.split(",")) if a.x else ds.num_names[:3]
        rep = mm.fit(ds, ds.pick([a.y])[0], xs)
        fz = freeze(rep, f"{os.path.basename(a.data)} · fit")
        with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(fz, fh, ensure_ascii=False, indent=2)
        print(f"  冻结 {fz['n']} 个数值 → {a.out}")
        return 0

    if a.cmd == "check":
        if not (os.path.exists(a.tex) and a.frozen):
            print("  check 需要 tex 路径与 --frozen")
            return 2
        tex = open(a.tex, encoding="utf-8").read()
        fz = json.load(open(a.frozen, encoding="utf-8"))
        r = check_paper(tex, fz)
        print(f"  论文 {r['n_numbers']} 个数，"
              f"{r['n_traced']} 个能溯源，{len(r['untraced'])} 个不能")
        for v in r["untraced"][:10]:
            print(f"    找不到出处：{v}")
        return 0 if r["ok"] else 1

    if a.cmd == "stale":
        if not (a.frozen and a.old):
            print("  stale 需要 --frozen 与 --old")
            return 2
        new = json.load(open(a.frozen, encoding="utf-8"))
        old = json.load(open(a.old, encoding="utf-8"))
        st = detect_stale(old, new)
        print(f"  变化 {st['n_changed']} 项 / 新增 {st['n_added']} / "
              f"移除 {st['n_removed']}")
        for c in st["changed"]:
            print(f"    {c['path']}: {c['old']} → {c['new']} "
                  f"({c['delta']:+})")
        if st["needs_update"]:
            print("  ⚠ 论文里引用这些数的地方要同步更新")
        return 0 if not st["needs_update"] else 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
