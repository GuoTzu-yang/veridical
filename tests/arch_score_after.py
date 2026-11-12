#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优化后的设计评分：拆成三块分别算，避免"加条数"把均分稀释成好看的数字

  块 A  原 8 条主张，在优化后的状态   —— 与优化前 72.9 直接可比
  块 B  新增 4 条主张                 —— 本轮加的东西，单独计
  块 C  A+B 合并                      —— 只作参考，不与 72.9 对比

跑法：python arch_score_after.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Claim, run_gates, EvidenceEnv, ENV_LEVELS  # noqa: E402

# ---------------------------------------------------------------------------
# 块 A：原 8 条，按优化后的状态重新打分
# 变化只在能验证性上：e3 从 0/1 升到 1/2（因为现在有实现、有测试）
# ---------------------------------------------------------------------------
BLOCK_A = [
    Claim("D1", "主线/支线双轨并行，底部收束",
          e1=2, e2=2, e3=1,
          sources=["原图", "mainline_loop 实测有效率 0.083"]),
    Claim("D2", "三闸递进 + 环境自适应（通过线随能力收缩）",
          e1=2, e2=1, e3=2,
          sources=["gate(env=)", "harness ENV 段 10 项断言"]),
    Claim("D3", "回边分级 + 预算（单边 2/3 + 全局 4）",
          e1=2, e2=2, e3=2,
          sources=["RetryBudget", "Astra 反复修复循环先例"]),
    Claim("D4", "失败资产化（疑难1库/疑难2库）",
          e1=2, e2=1, e3=0,
          sources=["原图"]),
    Claim("D5", "问方向 + 可判触发（分叉探测/缺参/超时降级）",
          e1=2, e2=1, e3=2,
          sources=["detect_fork", "差分测试先例"]),
    Claim("D6", "循环推理档位化（原为固定≥3，已按有效率调档）",
          e1=2, e2=2, e3=2,
          sources=["LoopJournal.recommend_strength", "12 轮 11 空转实测"]),
    Claim("D7", "终末内容冻结（只改表述）",
          e1=2, e2=2, e3=1,
          sources=["原图"]),
    Claim("D8", "Prompt 优化作为融合接口",
          e1=2, e2=1, e3=1,
          sources=["原图位置"]),
]

# ---------------------------------------------------------------------------
# 块 B：本轮新增
# ---------------------------------------------------------------------------
BLOCK_B = [
    Claim("N1", "证据环境分四档（L0-L3），自动探测",
          e1=2, e2=1, e3=2,
          sources=["detect_env", "ENV_LEVELS"]),
    Claim("N2", "反证一票否决（refuted_by_test）",
          e1=2, e2=1, e3=2,
          sources=["run_gates REFUTED 分支"]),
    Claim("N3", "冷启动路由（lite/std/full 三档）",
          e1=2, e2=2, e3=2,
          sources=["choose_route", "缓存/分级路由先例"]),
    Claim("N4", "结论类别区分（world / observation）",
          e1=2, e2=0, e3=2,
          sources=["Claim.kind", "本次实测才发现"]),
]

BEFORE = {"total": 35, "max": 48, "pct": 72.9}


def score(block, env):
    total = 0
    rows = []
    for c in block:
        r = run_gates(c, env)
        total += r["C"]
        rows.append((c, r))
    return rows, total, len(block) * 6


def show(title, rows, total, mx, env):
    print(f"\n{title}")
    print("-" * 78)
    for c, r in rows:
        mark = {"pass": "✓", "degrade": "~", "reject": "✗"}[r["final"]]
        print(f"  {mark} {c.cid:3}{c.text[:48]:<50}{r['C']:>3}")
    print(f"    {'合计':<55}{total:>3}/{mx}  = {total / mx * 100:.1f}")


def main() -> int:
    env2 = EvidenceEnv(2)
    env3 = EvidenceEnv(3)

    print("=" * 78)
    print("优化后的设计评分（拆三块算）")
    print(f"当前真实环境 L{env2.level}；另附 L3 假设环境作对照")
    print("=" * 78)

    rowsA2, tA2, mA = score(BLOCK_A, env2)
    show("块 A · 原 8 条（优化后状态）· L2 实测环境", rowsA2, tA2, mA, env2)

    rowsA3, tA3, _ = score(BLOCK_A, env3)
    print(f"    L3 假设环境下同一批: {tA3}/{mA}  = {tA3 / mA * 100:.1f}")

    rowsB2, tB2, mB = score(BLOCK_B, env2)
    show("块 B · 新增 4 条 · L2", rowsB2, tB2, mB, env2)

    print()
    print("=" * 78)
    print("对比")
    print("-" * 78)
    print(f"  优化前（原 8 条）        {BEFORE['total']}/{BEFORE['max']} = {BEFORE['pct']:.1f}")
    print(f"  优化后（原 8 条重评）     {tA2}/{mA} = {tA2 / mA * 100:.1f}"
          f"   （+{tA2 / mA * 100 - BEFORE['pct']:.1f}）")
    print(f"  新增 4 条               {tB2}/{mB} = {tB2 / mB * 100:.1f}")
    print(f"  合并 12 条              {tA2 + tB2}/{mA + mB} = "
          f"{(tA2 + tB2) / (mA + mB) * 100:.1f}   （仅供参考，分母变了）")

    print()
    print("  提升来自哪（绝对分只涨了 4，其余是百分制换算）：")
    print("    D6  4→6   e2 0→2：固定≥3轮被推翻后改成档位化，找到了先例（Astra 五档）")
    print("    D5  3→5   e3 0→2：问方向从'没验证'做成'有可判触发 + 降级路径'")
    print("    D2  5→5   加了环境自适应，但 e2 仍只有 1（这做法没先例）")
    print("    其余四条未动（D1/D4/D7/D8）")
    print()
    print("  注意：块 B 里 N4 判 reject（e2=0），但那 4 分仍计入合计——")
    print("        '有分'和'可交付'是两回事，合计分不代表能用。")

    print()
    print("=" * 78)
    print("这份分的水分，比 72.9 那份更大：")
    print("  新增 4 条全是我这一轮自己加的，e2 最高只到 2，N4 甚至是 0。")
    print("  涨的 4 分里，2 分是'找到了先例'，2 分是'把没验的做成能验的'。")
    print("  可验证 ≠ 已被验证。真正跑过的只有 1 道题（1440），而它是被拒的。")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
