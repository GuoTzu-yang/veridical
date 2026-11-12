#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
框架升级：从「判单条」到「判整题」

前五轮都在做一件事：给一条结论打分（e1/e2/e3 → C → pass/degrade/reject）。
但真用起来，要回答的不是「这条几分」，是「这题能不能做成」。

一条流水线的成败由组合决定：
  - 三项全过才拿满分（and）
  - 任一环死掉整体死
  - 成本却是累加的

这个文件加一层 TaskGraph：把 N 条结论按组合关系算整体成功率，
再用已有的实测记录校准「degrade 到底有多可靠」。

跑法：python taskgraph.py
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from itertools import product as cartesian

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from harness import Claim, run_gates, EvidenceEnv, detect_env  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

# 先验：在没有任何校准数据时的默认成功率。
# 这三个数是拍的，后面的 calibrate() 会用实测把它们修正。
VERDICT_PRIOR = {
    "pass": 0.95,
    "degrade": 0.65,
    "reject": 0.02,
}


def prior_for(prior: dict[str, float], verdict: str,
              cause: str | None = None) -> float:
    """取值时先查 "degrade/env" 这类复合键，查不到再回落到 verdict。

    degrade 的两种成因实测差 4 倍（0.833 vs 0.222），按 verdict 混算出来的
    中间值没有物理意义，所以必须先查复合键。
    """
    if cause:
        key = f"{verdict}/{cause}"
        if key in prior:
            return prior[key]
    return prior.get(verdict, 0.5)


@dataclass
class Item:
    label: str
    claim: Claim
    weight: float = 1.0


@dataclass
class TaskGraph:
    """一道题（或一条流水线）的成败图。

    relation:
      and      —— 全部成功才算成功（提测三项）
      or       —— 任一成功即成功（多条备选路线）
      weighted —— 加权求和（部分得分场景）
    """
    name: str
    items: list[Item] = field(default_factory=list)
    relation: str = "and"

    def evaluate(self, env: EvidenceEnv, prior: dict[str, float] | None = None) -> dict:
        prior = prior or VERDICT_PRIOR
        rows = []
        for it in self.items:
            r = run_gates(it.claim, env)
            p = prior_for(prior, r["final"], r.get("cause"))
            rows.append({
                "label": it.label,
                "verdict": r["final"],
                "cause": r.get("cause"),
                "p": p,
                "weight": it.weight,
                "blocked_at": r.get("blocked_at"),
                "C": r["C"],
            })

        if self.relation == "and":
            p_total = 1.0
            for r in rows:
                p_total *= r["p"]
        elif self.relation == "or":
            q = 1.0
            for r in rows:
                q *= (1.0 - r["p"])
            p_total = 1.0 - q
        elif self.relation == "weighted":
            wsum = sum(r["weight"] for r in rows) or 1.0
            p_total = sum(r["p"] * r["weight"] for r in rows) / wsum
        else:
            raise ValueError(f"未知关系 {self.relation}")

        weakest = min(rows, key=lambda r: (r["p"], r["C"])) if rows else None
        return {
            "name": self.name,
            "relation": self.relation,
            "rows": rows,
            "p_success": round(p_total, 4),
            "weakest": weakest["label"] if weakest else None,
        }


# ---------------------------------------------------------------------------
# 校准：用实测记录修正先验
# ---------------------------------------------------------------------------
# 每条都是真发生过的判定 → 实际结果。
# 来源：case_train.py 的提测记录（3 条）、calibrate_procedure.py 的五场景（5 条）。
# ---------------------------------------------------------------------------
OBSERVED = [
    # (判定, 实际是否成功, 来源)
    ("degrade", True,  "case_train T1 部署UUID"),
    ("degrade", True,  "case_train T2 Fork"),
    ("degrade", True,  "case_train T3 PR"),
    ("degrade", True,  "calib S1 真UUID"),
    ("reject",  False, "calib S2 伪UUID"),
    ("reject",  False, "calib S3 格式错"),
    ("reject",  False, "calib S4 空值"),
    ("reject",  False, "calib S5 已认领"),
]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson 95% 区间。n 很小的时候，[k/n] 这种点估计没有意义，区间才有。"""
    import math
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def calibrate(observed: list[tuple[str, bool, str]]) -> dict:
    """按判定分桶统计实测成功率，并用 Laplace 平滑给出估计。

    样本很少时 Laplace 会把 0% 拉到非零，这是刻意的：
    宁可高估失败概率，也不要因为「没见过失败」就认为不可能失败。
    同时给出 Wilson 区间——样本量 < 10 时，点估计基本没有解释力。
    """
    buckets: dict[str, list[bool]] = {}
    for verdict, ok, _ in observed:
        buckets.setdefault(verdict, []).append(ok)

    out = {}
    for verdict, oks in buckets.items():
        n = len(oks)
        succ = sum(1 for x in oks if x)
        lo, hi = wilson(succ, n)
        out[verdict] = {
            "n": n,
            "success": succ,
            "raw_rate": round(succ / n, 3) if n else None,
            "laplace": round((succ + 1) / (n + 2), 3),
            "wilson_lo": round(lo, 3),
            "wilson_hi": round(hi, 3),
        }
    return out


def main() -> int:
    env, why = detect_env(HERE, None, True)

    print("=" * 80)
    print("框架升级 · 从「判单条」到「判整题」")
    print(f"环境 L{env.level}（{why['reason']}）")
    print("=" * 80)

    # --- 1. 校准 ---
    print("\n【1】先验校准（用已有实测修正 VERDICT_PRIOR）")
    cal = calibrate(OBSERVED)
    print(f"  {'判定':<10}{'样本':>5}{'成功':>5}{'实测率':>8}{'Laplace':>9}{'Wilson95%':>16}{'原先验':>8}")
    print("  " + "-" * 68)
    for v in ("pass", "degrade", "reject"):
        c = cal.get(v)
        if c:
            ci = f"[{c['wilson_lo']}, {c['wilson_hi']}]"
            print(f"  {v:<10}{c['n']:>5}{c['success']:>5}"
                  f"{str(c['raw_rate']):>8}{c['laplace']:>9}{ci:>16}{VERDICT_PRIOR[v]:>8}")
        else:
            print(f"  {v:<10}{0:>5}{0:>5}{'-':>8}{'-':>9}{'-':>16}{VERDICT_PRIOR[v]:>8}")
    d = cal.get("degrade", {})
    if d:
        print(f"\n  degrade 只有 {d['n']} 个样本，{d['success']}/{d['n']} 成功。")
        print(f"  Wilson 95% 区间 [{d['wilson_lo']}, {d['wilson_hi']}] —— 下界才是能拿去用的数。")
        print(f"  4/4 不说明成功率接近 1，只说明「还没见过它失败」。")

    calibrated = {k: v["laplace"] for k, v in cal.items()}
    for k, v in VERDICT_PRIOR.items():
        calibrated.setdefault(k, v)
    # 保守版：用 Wilson 下界——样本 4 个的时候，这才是能拿去决策的数
    conservative = {k: v["wilson_lo"] for k, v in cal.items()}
    for k, v in VERDICT_PRIOR.items():
        conservative.setdefault(k, v)

    # --- 2. 用校准后的先验算整题 ---
    print("\n【2】整题成功率 · 提测三项（and 关系）")
    graph = TaskGraph(
        name="seekdb 基础实践",
        items=[
            Item("T1 部署UUID", Claim("T1", "部署取UUID", e1=2, e3=2, kind="procedure")),
            Item("T2 Fork",     Claim("T2", "Fork+验证行", e1=2, e3=2, kind="procedure")),
            Item("T3 PR",       Claim("T3", "提PR+验证行", e1=1, e3=2, kind="procedure")),
        ],
        relation="and",
    )
    before = graph.evaluate(env, VERDICT_PRIOR)
    after = graph.evaluate(env, calibrated)
    cons = graph.evaluate(env, conservative)

    print(f"  {'条目':<14}{'判定':>9}{'先验p':>8}{'校准p':>8}{'保守p':>8}")
    print("  " + "-" * 50)
    for rb, ra, rc in zip(before["rows"], after["rows"], cons["rows"]):
        print(f"  {rb['label']:<14}{rb['verdict']:>9}{rb['p']:>8}{ra['p']:>8}{rc['p']:>8}")
    print(f"\n  整体成功率  先验 {before['p_success']:.3f}"
          f"  校准 {after['p_success']:.3f}  保守 {cons['p_success']:.3f}")
    print(f"  最弱一环(按 p 再按 C): {after['weakest']}")
    print()
    print("  三个数分别是：拍脑袋 / 用 4 样本的 Laplace 中点 / 用 Wilson 下界。")
    print("  样本只有 4 个时，**保守值才是能拿去决策的那个**——校准值会误导。")

    # --- 3. 实际结果对照 ---
    print("\n【3】对照实际结果")
    print("  2026-11-06 01:31 提测：执行成功 · 30.000 · 成功3 失败0")
    print(f"  先验 {before['p_success']*100:.0f}% / 校准 {after['p_success']*100:.0f}%"
          f" / 保守 {cons['p_success']*100:.0f}%  vs 实际 100%")
    print()
    print("  三个预测全部偏低。方向是对的（都判对了每一项），但数值没有解释力：")
    print("  三个样本撑不起概率模型。现在能说的只有一句——")
    print("  **degrade 的先验 0.65 低估了，实测 4/4 从未失败过。**")

    # --- 4. 反例：一条 reject 拖垮整题 ---
    print("\n【4】反例 · 把 T1 换成伪 UUID（input_valid=False）")
    bad = TaskGraph(
        name="seekdb 基础实践（伪UUID）",
        items=[
            Item("T1 部署UUID", Claim("T1", "伪UUID", e1=2, e3=2,
                                     kind="procedure", input_valid=False)),
            Item("T2 Fork",     Claim("T2", "Fork+验证行", e1=2, e3=2, kind="procedure")),
            Item("T3 PR",       Claim("T3", "提PR+验证行", e1=1, e3=2, kind="procedure")),
        ],
        relation="and",
    )
    bad_r = bad.evaluate(env, conservative)
    print(f"  T1 verdict = {bad_r['rows'][0]['verdict']}，整题成功率 {bad_r['p_success']}")
    print(f"  一条 reject 把 30 分题打成 {bad_r['p_success']*100:.1f}% —— and 关系下，最弱一环决定上限。")
    print(f"  （这里用保守值算：Laplace 会把 reject 抬到 0.167，掩盖它本该是 0 的事实）")

    print()
    print("=" * 80)
    print("升级点：")
    print("  旧：每条结论独立打分，看不出组合成败")
    print("  新：TaskGraph 按 and/or/weighted 算整体， weakest 指出先修哪个")
    print("  限制：只有 8 个实测样本，校准值只能当方向，不能当概率")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
