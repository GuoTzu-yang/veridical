#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
投喂真题：把 APMCM 题库的数据拆成可判定主张

架构的输入是「主张」，不是「题目」。这层适配把题目里的**可验证断言**抽出来，
挂上 `data` 域的确定性断言，跑一次就知道成不成立。

为什么值得做：这是唯一能拿到 `e3=measured` 的题源。
前面所有样本要么是构造的 SQL 任务，要么是文件读写——
**真题数据的断言是"算一遍就知道对错"的**。

跑法：python tests/feed_qb.py
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from probe import do_exec  # noqa: E402

QB = (r"C:\Users\21246\Documents\deepseek-harness\default-workspace"
      r"\apmcm2026\题库\2026中文-A_B_C三题")

B_DATA = os.path.join(
    QB, "B题 高性能芯片热管理系统的优化问题", "附件",
    "附件 2：不同结构参数下无量纲的热阻、压降和温度非均匀性结果数据.xlsx")
A_JAN = os.path.join(
    QB, "A题 自来水厂水质预测与评估", "附件", "附件1  2025数据集", "JBALB_Jan2025.xlsx")
A_2026_JAN = os.path.join(
    QB, "A题 自来水厂水质预测与评估", "附件", "附件2  2026数据集", "2026年1月.xls")

# (题, 主张原文, 断言规格, 我的预判)
# 预判这一列是**故意留着**的：跑完对比，才知道自己的直觉准不准。
CLAIMS = [
    # ---- 2026-B 芯片热管理：3 个结构参数 → 3 个输出 ----
    ("B", "附件2 至少 50 个样本",
     {"assert": "row_count", "params": {"op": ">=", "value": 50}}, True),
    ("B", "附件2 有无量纲热阻列",
     {"assert": "column_exists", "params": {"column": "无量纲热阻"}}, True),
    ("B", "无量纲热阻都在 0~1 之间",
     {"assert": "value_bounds",
      "params": {"column": "无量纲热阻", "min": 0, "max": 1}}, True),
    ("B", "针肋宽度比越大，热阻越大（正相关）",
     {"assert": "corr_sign",
      "params": {"x": "针肋宽度比", "y": "无量纲热阻", "expect": "positive"}}, True),
    ("B", "热阻与压降是反向权衡",
     {"assert": "corr_sign",
      "params": {"x": "无量纲热阻", "y": "无量纲压降", "expect": "negative"}}, True),
    ("B", "歧管深高比越大，压降越低",
     {"assert": "corr_sign",
      "params": {"x": "歧管深高比", "y": "无量纲压降", "expect": "negative"}}, True),
    ("B", "热阻列没有缺失值",
     {"assert": "no_null_in", "params": {"column": "无量纲热阻"}}, True),
    ("B", "温度非均匀性随时间推移恶化（四段递增）",
     {"assert": "monotone_quarters",
      "params": {"column": "无量纲温度非均匀性", "expect": "increasing"}}, True),

    # ---- 2026-A 自来水厂：真实传感器时序 ----
    ("A", "1 月数据有 300 行以上",
     {"assert": "row_count", "params": {"op": ">=", "value": 300}}, True),
    ("A", "有 FILT. NTU（滤后浊度）列",
     {"assert": "column_exists", "params": {"column": "FILT. NTU"}}, True),
    ("A", "1 月滤后浊度始终低于 1 NTU",
     {"assert": "value_bounds",
      "params": {"column": "FILT. NTU", "min": 0, "max": 1}}, True),
    ("A", "原水浊度（R/W NTU）与滤后浊度同向",
     {"assert": "corr_sign",
      "params": {"x": "R/W NTU", "y": "FILT. NTU", "expect": "positive"}}, True),
    ("A", "河水水位与流量同向",
     {"assert": "corr_sign",
      "params": {"x": "RIVER LEVEL", "y": "R/W FLOW", "expect": "positive"}}, True),
]

# 各表的表头行：B 附件2 第 1 行是大标题，第 2 行才是表头
HEADER = {"B": 2, "A": 1}


def main() -> int:
    dry = "--dry-run" in sys.argv
    do_record = "--record" in sys.argv

    print("=" * 82)
    print("投喂真题 · 主张 × 确定性断言")
    if dry:
        print("【dry-run】不执行、不落账")
    print("=" * 82)

    hit = miss = guilty = 0
    per_q = {}
    for q, text, spec, guess in CLAIMS:
        path = B_DATA if q == "B" else A_JAN
        task = {"file": path, "header_row": HEADER[q], **spec}
        ok, why = do_exec("data", task)
        mark = "✓" if ok == guess else "✗"
        if ok == guess:
            hit += 1
        else:
            miss += 1
        guilty += 1 if ok else 0
        per_q.setdefault(q, [0, 0])
        per_q[q][0] += 1 if ok else 0
        per_q[q][1] += 1
        print(f"  [{q}] {mark} {text}")
        print(f"      判定={'成立' if ok else '不成立'}  预判={'成立' if guess else '不成立'}"
              f"   {why[:60]}")

    print()
    print("=" * 82)
    print(f"  共 {len(CLAIMS)} 条主张：成立 {guilty} / 不成立 {len(CLAIMS) - guilty}")
    print(f"  我的预判命中 {hit}/{len(CLAIMS)}"
          + (f"，错了 {miss} 条" if miss else "（这次全对）"))
    for q, (a, b) in sorted(per_q.items()):
        print(f"    [{q}] 成立 {a}/{b}")
    print("=" * 82)
    print()
    print("怎么读这个数：")
    print("  「预判错了 N 条」不是失败，是**投喂真题的意义**——")
    print("  我对这份数据的直觉有 N 处是错的，而数据本身给了确定答案。")
    print("=" * 82)

    if do_record:
        _record_all(blind=("--blind" in sys.argv))
    return 0


def _record_all(blind: bool = False) -> None:
    """按正确语义记账。

    **盲判模式（--blind）**：只凭「题目 + 数据结构」判，**不跑断言**，
    记 `success=None` 挂起。下一轮用 `ledger.py resolve-blind` 结算。

    这才是对判据的真检验——判的时候还不知道答案。
    非盲判模式下先跑断言再记，`prejudged=True`，**不检验判据**
    （第五十二轮发现自己虚高精确率，就是混了这两种）。
    """
    import ledger as L
    from harness import Claim, run_gates, EvidenceEnv

    L.bind_production("真题投喂：真实数据断言")

    env = EvidenceEnv(3)
    recs = []
    for q, text, spec, _guess in CLAIMS:
        path = B_DATA if q == "B" else A_JAN
        task = {"file": path, "header_row": HEADER[q], **spec}

        if blind:
            # 只看结构：任务声明了 e1=2（能指到文件+列）、e3=2（有确定性验法）
            # 但**没跑**。按第五十一轮的读法，没跑就不该给 e3=2——
            # 所以盲判时 e3=1，结论落在 degrade，等验证来升或否。
            c = Claim(f"QB-{q}", text, e1=2, e2=1, e3=1, kind="world",
                      input_valid=True)
            g = run_gates(c, env)
            rec = L.record(g["final"], task=f"真题·{q} {text[:30]}",
                           note=f"盲判（未跑断言）断言={spec['assert']}",
                           success=None,          # ← 挂起，等结算
                           exec_ok=None,
                           evidence="盲判：只看题目与数据结构，未执行断言",
                           env_level=3, cause=g.get("cause"), origin="qb",
                           replay={"domain": "data", "task": task},
                           prejudged=False)       # 真检验
            recs.append((g["final"], None, rec["id"]))
            continue

        ok, why = do_exec("data", task)
        c = Claim(f"QB-{q}", text, e1=2, e2=2, e3=2, kind="world",
                  input_valid=True, refuted_by_test=(not ok))
        g = run_gates(c, env)
        rec = L.record(g["final"],
                       task=f"真题·{q} {text[:30]}",
                       note=f"断言={spec['assert']}",
                       success=ok,
                     conclusion_held=ok,
                       exec_ok=True,
                       evidence=why[:70],
                       env_level=3,
                       cause=g.get("cause"),
                       origin="qb",
                       replay={"domain": "data", "task": task},
                       prejudged=True)
        recs.append((g["final"], ok, rec["id"]))

    from collections import Counter
    print()
    if blind:
        c = Counter(v for v, _ok, _i in recs)
        print(f"已记 **盲判** {len(recs)} 条（success=None，等 resolve-blind 结算）")
        for k, n in sorted(c.items()):
            print(f"  {k}: {n}")
        print("下一步：python ledger.py resolve-blind")
    else:
        dist = Counter(f"{v}/{'成立' if ok else '被推翻'}" for v, ok, _ in recs)
        print(f"已记账 {len(recs)} 条（origin=qb，prejudged=True）")
        for k, n in sorted(dist.items()):
            print(f"  {k}: {n}")


if __name__ == "__main__":
    raise SystemExit(main())
