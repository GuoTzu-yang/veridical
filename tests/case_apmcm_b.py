#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
APMCM 2026 B 题 · 拿真题驱动整条链路

题目：高性能芯片热管理系统的优化问题
数据：附件 2，85 组「结构参数 → 三项性能」

这份脚本要回答的不是"答案是多少"，而是——
**这套架构在真题上跑起来，顺不顺、卡在哪。**

三段：
    一、判前（e3=1，还没算）→ 拿到「还差什么」
    二、真算（e3=2 或 refuted_by_test）
    三、判后 → 看判定怎么变，以及建议是否真的能兑现

跑法：python tests/case_apmcm_b.py [--record]
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import openpyxl                                          # noqa: E402
from harness import Claim, run_gates, EvidenceEnv         # noqa: E402
from extend import what_would_help                        # noqa: E402

XLSX = (r"C:\Users\21246\Documents\deepseek-harness\default-workspace"
        r"\apmcm2026\题库\2026中文-A_B_C三题"
        r"\B题 高性能芯片热管理系统的优化问题\附件"
        r"\附件 2：不同结构参数下无量纲的热阻、压降和温度非均匀性结果数据.xlsx")

ENV = EvidenceEnv(3)


def load() -> tuple[list[str], list[dict]]:
    """读附件 2。表头在第 2 行，数据从第 3 行起。"""
    wb = openpyxl.load_workbook(XLSX, data_only=True)
    ws = wb.active
    hdr = [str(c).strip() for c in
           next(ws.iter_rows(min_row=2, max_row=2, values_only=True)) if c]
    rows = []
    for r in ws.iter_rows(min_row=3, values_only=True):
        if r[0] is None:
            continue
        rows.append({
            "id": r[0], "w": float(r[1]), "d": float(r[2]), "n": float(r[3]),
            "R": float(r[4]), "P": float(r[5]), "T": float(r[6]),
        })
    return hdr, rows


def corr(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = sum((a - mx) ** 2 for a in xs) ** 0.5
    dy = sum((b - my) ** 2 for b in ys) ** 0.5
    return num / (dx * dy) if dx and dy else 0.0


def trend(rows, key, out, fixed: dict | None = None):
    """固定其它参数时，考察 key 对 out 的走向。返回 (相关系数, 样本数)。"""
    sub = [r for r in rows
           if all(abs(r[k] - v) < 1e-9 for k, v in (fixed or {}).items())]
    if len(sub) < 3:
        return None, len(sub)
    return corr([r[key] for r in sub], [r[out] for r in sub]), len(sub)


def pareto(rows: list[dict]) -> list[dict]:
    """三目标（热阻/压降/温度非均匀性）全部最小化的帕累托前沿。

    题目问的不是"哪一维和哪一维相关"，而是**怎么选结构参数**。
    那是多目标优化问题，答案不是一条结论，是一个集合：
    **没有别的点能在三项上同时不差的那些点。**

    这也是"可验证"的：给定数据，前沿是唯一确定的，
    谁在谁不在可以逐点核对。比"相关性强弱"硬得多。
    """
    out = []
    for a in rows:
        dominated = False
        for b in rows:
            if b is a:
                continue
            if (b["R"] <= a["R"] and b["P"] <= a["P"] and b["T"] <= a["T"]
                    and (b["R"] < a["R"] or b["P"] < a["P"] or b["T"] < a["T"])):
                dominated = True
                break
        if not dominated:
            out.append(a)
    return out


def judge(c: Claim) -> dict:
    return run_gates(c, ENV)


def main() -> int:
    hdr, rows = load()
    print("=" * 88)
    print("APMCM 2026 B 题 · 高性能芯片热管理系统")
    print("=" * 88)
    print(f"  数据：{len(rows)} 组 / {len(hdr)} 列")
    print(f"  列：{hdr}")
    ws_, ds_, ns_ = sorted({r['w'] for r in rows}), sorted({r['d'] for r in rows}), \
        sorted({r['n'] for r in rows})
    print(f"  参数取值：针肋宽度比 {ws_} / 歧管深高比 {ds_} / 排数 {ns_}")

    # 五条主张：都是这个优化问题里"先要看清楚"的结构-性能关系
    CLAIMS = [
        ("B1", "歧管深高比增大，无量纲热阻下降", "d", "R", -1),
        ("B2", "歧管深高比增大，无量纲压降下降", "d", "P", -1),
        ("B3", "针肋宽度比增大，无量纲热阻下降", "w", "R", -1),
        ("B4", "针肋宽度比增大，温度非均匀性下降", "w", "T", -1),
        ("B5", "针肋排数增多，压降上升", "n", "P", +1),
    ]

    print()
    print("=" * 88)
    print("一、判前（e3=1：还没算）→ 看架构给什么建议")
    print("=" * 88)
    pre = {}
    for cid, text, _k, _o, _sign in CLAIMS:
        c = Claim(cid, text, e1=2, e2=0, e3=1, kind="world")
        g = judge(c)
        pre[cid] = (c, g)
        asks = what_would_help(c, g["final"], g.get("blocked_at"), ENV)
        dims = "、".join(f"{a['dim']}({a['have']}→{a['need']})" for a in asks)
        print(f"  {cid} {text[:26]:<28} C={g['C']} → {g['final']:<8} 缺：{dims}")

    print()
    print("=" * 88)
    print("二、真算：按建议去补证据")
    print("=" * 88)
    results = {}
    for cid, text, k, o, sign in CLAIMS:
        # 固定其它两个参数，看 key 与 out 的走向（这是能做的"独立来源"：
        # 不同固定水平下重复出现同号，才算不只一次观测）
        sigs = []
        for other in [x for x in ("w", "d", "n") if x != k]:
            for lvl in sorted({r[other] for r in rows})[:3]:
                rho, n = trend(rows, k, o, {other: lvl})
                if rho is not None:
                    sigs.append(round(rho, 3))
        # 「同号」必须要求相关性够强。
        # 第一版把 rho=0.0 也算成"符号一致"（因为 0>0 与 -1>0 同为 False），
        # 于是 B3/B4 的零相关被当成支持——**噪声不该算证据**。
        MIN_RHO = 0.3
        MIN_N = 3
        strong = [s for s in sigs if abs(s) >= MIN_RHO]
        same_sign = sum(1 for s in strong if (s > 0) == (sign > 0))
        # 比例阈值必须配条数阈值。
        # 第一版只要求 ≥80%，于是 B4 用 **1 条**强相关就判"成立"——
        # 1/1 = 100%，看起来完美，其实没有任何重复。
        # 一条样本上的比例不是比例。
        enough = len(strong) >= MIN_N
        hold = enough and same_sign / len(strong) >= 0.8
        if not enough:
            share = f"强相关仅 {len(strong)} 条 < {MIN_N}，证据不足"
        else:
            share = f"{same_sign}/{len(strong)} 同号（|ρ|≥{MIN_RHO}）"
        results[cid] = {"sigs": sigs, "strong": strong,
                        "hold": hold, "enough": enough, "share": share}
        print(f"  {cid} {k}→{o}  分层相关：{sigs}")
        print(f"       其中 |ρ|≥0.3 的：{strong}")
        verdict = ("成立" if hold else
                   ("证据不足" if not enough else "不成立"))
        print(f"       {share} → {verdict}")

    # ------------------------------------------------------------------
    # 优化问题：题目真正问的
    # ------------------------------------------------------------------
    print()
    print("=" * 88)
    print("二·五、优化问题（题目真正问的那个）")
    print("=" * 88)
    front = pareto(rows)
    print(f"  84 组里，帕累托前沿 {len(front)} 个点：")
    for r in sorted(front, key=lambda x: x["R"]):
        print(f"    #{int(r['id']):<3} w={r['w']:<5} d={r['d']:<4} n={r['n']:<3}"
              f"  R={r['R']:.4f}  P={r['P']:.4f}  T={r['T']:.4f}")

    # 三条关于优化的可验证主张
    OPT = [
        ("O1", "帕累托前沿不止一个点（存在真实权衡）", len(front) > 1),
        ("O2", "前沿点上的歧管深高比取值不唯一（要折中）",
         len({r["d"] for r in front}) > 1),
        ("O3", "前沿点上的针肋宽度比取值不唯一",
         len({r["w"] for r in front}) > 1),
        # 这条是从前沿里读出来的**支配现象**：12 个点里 10 个是 w=0.2。
        # 注意措辞——是"多数前沿点取这个值"，不是"这个值最优"。
        # 两者差得很远：前者是观测，后者是要另外证明的。
        ("O4", "前沿点中针肋宽度比多数取 0.2（>50%）",
         sum(1 for r in front if abs(r["w"] - 0.2) < 1e-9) > len(front) / 2),
    ]
    print()
    for cid, text, ok in OPT:
        print(f"  {cid} {text:<36} → {'成立' if ok else '不成立'}")

    # 观测 → 推荐，中间必须隔一句"这是观测不是结论"
    w_share = sum(1 for r in front if abs(r["w"] - 0.2) < 1e-9)
    ds = sorted({r["d"] for r in front})
    print()
    print(f"  观测：{len(front)} 个前沿点里 {w_share} 个的针肋宽度比是 0.2；")
    print(f"        歧管深高比横跨 {ds[0]}–{ds[-1]}（这是真正的折中方向）。")
    print("  推荐（**这是工程判断，不是上面那几条的推论**）：")
    print("        针肋宽度比取 0.2；歧管深高比按『要热阻还是要压降』在 3.0–4.5 间选。")
    print("        —— 推荐比观测走远了一步，这一步靠人。")

    print()
    print("=" * 88)
    print("三、判后：e3=2，成立与否已成事实")
    print("=" * 88)
    upgraded = 0
    for cid, text, _k, _o, _sign in CLAIMS:
        r = results[cid]
        # e2 只能是 1：这些"分层复核"全来自**同一份附件**，
        # 切几刀还是同一处数据。按 e2 的规矩（同一仓库的多个文件不算
        # 独立来源），它只算一票。
        # 第一版写成 e2=2，那是拿同一份数据自己给自己投第二票。
        #
        # e3 也分两种：
        #   算出来且强相关条数够 → e3=2，结论无论正反都是**实测结论**
        #   算出来但强相关条数不够 → e3 停在 1，**没验成 ≠ 被推翻**
        # 第一版把"证据不足"也塞进 refuted_by_test，直接打成 reject——
        # 那等于把"我不知道"说成"我证伪了"。
        if r["hold"]:
            c = Claim(cid, text, e1=2, e2=1, e3=2, kind="world")
        elif r["enough"]:
            c = Claim(cid, text, e1=2, e2=1, e3=2, kind="world",
                      refuted_by_test=True)      # 真的被数据推翻
        else:
            c = Claim(cid, text, e1=2, e2=1, e3=1, kind="world")
        g = judge(c)
        before = pre[cid][1]["final"]
        if g["final"] != before:
            upgraded += 1
        print(f"  {cid} 判前 {before:<8} → 判后 {g['final']:<8} "
              f"C={g['C']}  理由：{r['share']}")

        if "--record" in sys.argv:
            import ledger as L
            L.bind_production("APMCM2026-B 链路验证")
            L.record(g["final"], task=f"B题·{cid} {text[:22]}",
                     note=f"参数 {_k}→{_o}",
                     success=r["hold"],
                     conclusion_held=r["hold"], exec_ok=True,
                     evidence=f"分层相关 {r['share']} 同号",
                     env_level=3, cause=g.get("cause"), origin="case",
                     ask=what_would_help(c, g["final"], g.get("blocked_at"), ENV))

    print()
    print("  优化类主张（数据即答案，不必先猜）：")
    for cid, text, ok in OPT:
        c = Claim(cid, text, e1=2, e2=1, e3=2, kind="world",
                  refuted_by_test=(not ok))
        g = judge(c)
        print(f"    {cid} {text[:30]:<32} C={g['C']} → {g['final']}"
              f"   ({'成立' if ok else '不成立'})")

    print()
    print("=" * 88)
    print(f"  判定发生变化的：{upgraded}/{len(CLAIMS)}")
    print("  这一轮真正验证的两件事：")
    print("    1. 架构能在真题上跑完，不需要我手工编维度")
    print("    2. 建议（缺 e2/e3）确实指出了该干什么：去算、去分层复核")
    print("=" * 88)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
