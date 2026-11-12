#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
procedure 判据校准：它到底能不能分清「会过」和「不会过」

2026-11-06 01:31 那次真实提测，三项全过，架构三项都判 degrade。
但那只能证明 degrade 是可靠下界，不能证明它有分辨力——因为它当时没被反例检验过。

这里用五个场景做反例实验：
  S1 真 UUID（平台查得到）          实际成功
  S2 伪 UUID（36 位格式对，查不到）  实际失败
  S3 格式错（32 位无连字符）         实际失败
  S4 空值                           实际失败
  S5 真 UUID 但已被别队认领          实际失败

跑法：python calibrate_procedure.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Claim, run_gates, EvidenceEnv  # noqa: E402

ENV = EvidenceEnv(2)   # 与提测时一致：有网络、无本地实例

# 五个场景。e1/e3 全部相同——题面一样清楚，平台一样能核验。
# 唯一的差别在「关键输入是否有效」，而当前判据根本看不到这一维。
SCENARIOS = [
    ("S1 真UUID",      2, 2, None,  True,  "成功", "46d2f692-...（report.json 实取）"),
    ("S2 伪UUID",      2, 2, None,  False, "失败", "36 位格式正确，平台查不到遥测"),
    ("S3 格式错",      2, 2, None,  False, "失败", "32 位、无连字符"),
    ("S4 空值",        2, 2, None,  False, "失败", "不填"),
    ("S5 已认领",      2, 2, None,  False, "失败", "UUID 有效但被别人先认领"),
]


def build(name, e1, e3, input_valid):
    return Claim(
        cid=name.split()[0], text=name, e1=e1, e2=0, e3=e3,
        kind="procedure", input_valid=input_valid,
    )


def main() -> int:
    print("=" * 84)
    print("procedure 判据校准 · 五场景反例实验")
    print("=" * 84)
    print(f"{'场景':<12}{'e1':>3}{'e3':>3}{'输入有效':>9}{'架构判定':>10}{'实际':>7}{'对上了?':>9}")
    print("-" * 84)

    hit = 0
    for name, e1, e3, iv, valid, actual, note in SCENARIOS:
        c = build(name, e1, e3, valid)   # valid 就是 input_valid
        r = run_gates(c, ENV)
        verdict = r["final"]
        # 只把"能执行"当作预测成功
        predicted_ok = verdict in ("pass", "degrade")
        actual_ok = actual == "成功"
        ok = predicted_ok == actual_ok
        hit += 1 if ok else 0
        print(f"{name:<12}{e1:>3}{e3:>3}{str(valid):>9}{verdict:>10}{actual:>7}"
              f"{'✓' if ok else '✗':>9}")

    print("-" * 84)
    print(f"  区分正确率: {hit}/{len(SCENARIOS)}")
    print()
    if hit == len(SCENARIOS):
        print("  结论：加「关键输入有效性」这一维后，五个场景全部分对。")
        print("        S1 可执行（degrade），S2–S5 一票否决（reject）。")
        print("        判据从「流程能跑」升级到「流程能跑且输入站得住」。")
    elif hit <= 1:
        print("  结论：五个场景判定完全相同，架构只是在说「这条流程能跑」，")
        print("        并没有说「跑了会成」——因为没有任何一维在看「输入对不对」。")
    else:
        print(f"  结论：只分对 {hit}/{len(SCENARIOS)}，判据仍未覆盖全部失败模式。")
    print()
    print("=" * 84)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
