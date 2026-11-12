#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自评：用 model1 架构给 model1 架构打分

规则和评估 issue #1440 时完全一样，不打折、不放水。
每条结论的分都必须能指到本目录里可核对的东西（文件、断言数、跑出来的结果）。
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Claim, run_gates, detect_env, ENV_LEVELS, GATE_SPEC  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 架构本体所在目录

# 五条要自评的结论。每条的 e 值都对应本目录里能复核的东西。
CLAIMS = [
    Claim(
        cid="S1", text="三个瓶颈的判据已做成可执行代码（不是文档里的说法）",
        e1=2,   # 能指到 harness.py: gate()/run_gates()/group() 具体函数
        e2=1,   # 两个来源：selftest 断言 + README 描述，但同为我产出
        e3=2,   # 任何人跑 python harness.py selftest 都得同样结果
        sources=["harness.py selftest 30 项", "README 瓶颈一/二/三"],
    ),
    Claim(
        cid="S2", text="已用真实题目端到端检验过",
        e1=2,   # case_1440.py 可执行、可复现
        e2=0,   # 只有 1 道题，样本量 1
        e3=2,   # python case_1440.py 随时可重跑
        sources=["case_1440.py / _case_1440.json"],
    ),
    Claim(
        cid="S3", text="已达到生产可用（能走完改→测→交闭环）",
        e1=2,   # survey_19.py 输出 0/19 验收用例
        e2=0,   # 单一来源：一次普查
        e3=2,   # 可重跑
        sources=["survey_19.py / _survey_19.json"],
    ),
    Claim(
        cid="S4", text="成本模型可靠（63→49.6 次调用那组数）",
        e1=1,   # 公式在 README，但没有真实账单对照
        e2=0,
        e3=1,   # 公式可复算，输入 token 数是估的
        sources=["README 成本影响一节"],
    ),
    Claim(
        cid="S5", text="阈值（2/4/5、0.7/0.3、0.34/0.66）已用真实分布校准",
        e1=0,   # 没有任何真实分布数据支撑
        e2=0,
        e3=0,
        sources=[],
    ),
]


def main() -> int:
    env, why = detect_env(ROOT, None, True)

    print("=" * 78)
    print("model1 架构自评")
    print(f"环境自动探测 → L{env.level}：{ENV_LEVELS[env.level]}")
    print(f"依据：{why['reason']}")
    print("=" * 78)
    print(f"{'':4}{'结论':<44}{'C':>3}{'判定':>9}{'路线':>10}")
    print("-" * 78)

    total_c = 0
    finals = []
    for c in CLAIMS:
        r = run_gates(c, env)
        total_c += r["C"]
        finals.append(r["final"])
        route = {"pass": "可交付", "degrade": "带标注交付", "reject": "不可交付"}[r["final"]]
        mark = {"pass": "✓", "degrade": "~", "reject": "✗"}[r["final"]]
        print(f"{mark:4}{c.text[:42]:<44}{r['C']:>3}{r['final']:>9}{route:>10}")

    print("-" * 78)
    n = len(CLAIMS)
    passed = finals.count("pass")
    degraded = finals.count("degrade")
    rejected = finals.count("reject")

    print(f"\n  各项 C 之和: {total_c} / {n * 6}")
    print(f"  折算百分制:  {total_c / (n * 6) * 100:.1f}")
    print(f"  判定分布:    pass {passed} / degrade {degraded} / reject {rejected}")
    print(f"  可交付比例:  {(passed + degraded)}/{n} = {(passed + degraded) / n * 100:.0f}%")

    # 只算真正能拿去用的（不含"带标注"）
    print(f"\n  能直接拿去用的: {passed}/{n} = {passed / n * 100:.0f}%")

    print("\n  卡在哪：")
    for c, f in zip(CLAIMS, finals):
        if f != "pass":
            r = run_gates(c, env)
            print(f"    {c.cid} {c.text[:30]} → {r['blocked_at'] or 'G3 降级'}")

    print()
    print("=" * 78)
    print("自评结论：")
    print("  机制本身是通的（S1 过），但没有样本量、没有校准数据（S2/S3/S5 全拒）。")
    print("  按它自己的标准，这套东西现在不是「可交付」，是「可演示」。")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
