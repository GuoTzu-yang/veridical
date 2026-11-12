#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
给「设计」打分：评估那张手绘图本身，不是评估 harness.py

评估对象是 8 条设计主张。每条的 e 值对应三类独立佐证：
  ① 图上是否明确画出
  ② 业界是否有先例（双过程理论 / Astra 五档 / 多级门禁）
  ③ 本次会话是否实测验证过

三条齐 → e2=2；两条 → 1；一条 → 0。

跑法：python arch_score.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Claim, run_gates, detect_env, ENV_LEVELS  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 架构本体所在目录

# 8 条设计主张
CLAIMS = [
    Claim(
        cid="D1", text="主线（人做题）与支线（做研究）双轨并行，底部收束",
        e1=2,   # 图上明确画出，口述确认
        e2=2,   # 先例：双过程理论 / Astra 五档推理强度 / Plan-Execute
        e3=1,   # 咱实测出主线有效率 0.083，但没做「单轨 vs 双轨」对照实验
        sources=["原图 主线/支线标注", "extend.py mainline_loop 实测"],
    ),
    Claim(
        cid="D2", text="三道置信度评估递进，各判不同维度（值不值得/可不可信/能不能用）",
        e1=2,   # 图上三处「置信度评估」+ 红圈 ②③④
        e2=1,   # 多级门禁有先例，但「递进判不同维度」少见
        e3=2,   # harness 已实现并出分布：G2 拦 31.6%，G3 主要降级
        sources=["原图 ②③④", "extend.py bench 19 条"],
    ),
    Claim(
        cid="D3", text="四条回边分级（重拆/重切/放弃/归档），落点各不相同",
        e1=2,   # 图上四条弧线，字迹清楚
        e2=2,   # Astra 实测踩过「反复进入修复循环」，证明必须分级+设上限
        e3=2,   # RetryBudget 实现并验证：全局预算 4 堵住交替绕过
        sources=["原图四条弧", "extend.py RetryBudget"],
    ),
    Claim(
        cid="D4", text="失败资产化：疑难1库/疑难2库把「放弃」变成生产行为",
        e1=2,   # 图上明确，红字标注
        e2=1,   # 经验库常见，但「失败分两库」少见
        e3=0,   # 没有长期运行数据证明库真能反哺
        sources=["原图 疑难1库/疑难2库"],
    ),
    Claim(
        cid="D5", text="对宿主提问独立成环节，作用是方向校准而非补信息",
        e1=2,   # 图上节点，口述明确「保证大方向不跑偏」
        e2=1,   # 澄清提问常见，「方向校准作为独立环节」少见
        e3=0,   # 没做「问 vs 不问」对照
        sources=["原图 对宿主提问"],
    ),
    Claim(
        cid="D6", text="循环推理固定「至少大于 3」轮",
        e1=2,   # 图上写了
        e2=0,   # 业界不固定轮数，按难度给档（Astra low→max）
        e3=2,   # 本次实测：12 轮里 11 轮空转，有效率 0.083
        sources=["原图「至少大于3」", "case_1440 主线留痕 0.133", "harness 12 轮 0.083"],
        refuted_by_test=True,   # 实测反证：固定 3 轮在这批题上全是浪费
    ),
    Claim(
        cid="D7", text="终末内容冻结线：主要内容不变，只允许优化表述",
        e1=2,   # 图上「主要内容不变 → 优化表述」
        e2=2,   # 先例：编译器的 IR 冻结 / 发布流程的内容锁定
        e3=1,   # 逻辑自洽，但没有实测它拦不拦得住
        sources=["原图 整理复查分支"],
    ),
    Claim(
        cid="D8", text="Prompt 优化放在支线内部，作为与主线的融合接口",
        e1=2,   # 图上位置在生成方案之后、⑤之前
        e2=1,   # 「接口层前置」有先例，但少见
        e3=1,   # 位置合理，未实测融合效果
        sources=["原图 Prompt优化 位置"],
    ),
]


def main() -> int:
    env, why = detect_env(ROOT, None, True)
    print("=" * 86)
    print("评估对象：手绘图「模型一」的设计主张（不是 harness.py 的实现）")
    print(f"环境自动探测 → L{env.level}：{ENV_LEVELS[env.level]}  ({why['reason']})")
    print("=" * 86)
    print(f"{'':4}{'设计主张':<52}{'C':>3}{'判定':>9}")
    print("-" * 86)

    total = 0
    finals = []
    for c in CLAIMS:
        r = run_gates(c, env)
        total += r["C"]
        finals.append(r["final"])
        mark = {"pass": "✓", "degrade": "~", "reject": "✗"}[r["final"]]
        note = "  ← 实测反证" if c.refuted_by_test else ""
        print(f"{mark:4}{c.text[:50]:<52}{r['C']:>3}{r['final']:>9}{note}")

    print("-" * 86)
    n = len(CLAIMS)
    print(f"\n  C 之和: {total}/{n * 6}   百分制 {total / (n * 6) * 100:.1f}")
    print(f"  分布:   通过 {finals.count('pass')} / 降级 {finals.count('degrade')}"
          f" / 打回 {finals.count('reject')}")

    print("\n  按证据强度分三档：")
    strong = [c.cid for c, f in zip(CLAIMS, finals) if f in ("pass", "degrade") and not c.refuted_by_test]
    weak = [c.cid for c, f in zip(CLAIMS, finals) if f == "reject" and not c.refuted_by_test]
    dead = [c.cid for c, f in zip(CLAIMS, finals) if c.refuted_by_test]
    print(f"    站得住（有图+有先例+能验证）: {strong}")
    print(f"    存疑（e3 或 e2 不足）        : {weak}")
    print(f"    已被实测推翻                 : {dead}")

    print()
    print("=" * 86)
    print("设计 vs 实现：")
    print(f"  设计 {n} 条：{len(strong)} 条站得稳，{len(weak)} 条存疑（缺验证），"
          f"{len(dead)} 条被实测推翻 → {total / (n * 6) * 100:.1f} 分")
    print("  实现 5 项：0 条能直接用，1 条带标注 → 50.0 分")
    print("  差在——设计有先例背书，实现缺样本和校准。")
    print("  但设计的分含水分：e3=0 那几条，恰恰是设计里最有个性的部分（失败资产化、问方向），")
    print("  它们没被验证过，只是没被证伪。")
    print("=" * 86)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
