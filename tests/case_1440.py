#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真实长任务测试：用 model1 架构处理 seekdb issue #1440

数据来源（全部为本地实测，非编造）：
  1. tasks/issue-1440.md                       —— 任务卡（落点/改法/验收/自检）
  2. data/issues_detail.json  number==1440     —— 完整 issue 原文 5910 字符，2 条评论
  3. data/tree_2026competition.json            —— 源码树 9879 条路径
  4. docs/*.md                                 —— 三份官方解析，均 0 次提到 1440
  5. ls bench/                                 —— 只有 eqfilter.sql 与 records.csv

跑法：python case_1440.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Claim, SubQ, group, run_gates, detect_fork, detect_missing, \
    build_questions, ask_gate, render_degraded, EvidenceEnv, ENV_LEVELS, detect_env  # noqa: E402
from extend import LoopJournal, RetryBudget, mainline_loop, choose_route, TopicLibrary  # noqa: E402


# =============================================================================
# 一、拆解（人工，但每个子问题都对应 task 卡里的一句）
# =============================================================================

SUBQS = [
    # 来自「2. 改法」前半句：区间保持原语
    SubQ("SQ1", "range谓词侧改动点", "求值", "文本", {"来源": "改法前半句"}, ["源码内容"]),
    # 来自「2. 改法」后半句：OR 链先化简再下推
    SubQ("SQ2", "OR链化简位置", "求值", "文本", {"来源": "改法后半句"}, ["源码内容"]),
    # 来自「3. 验收」：延迟差 < 10%
    SubQ("SQ3", "复现73.578x差距", "求值", "数值", {"环境": "seekdb 1.3.0.0"}, ["可运行实例"]),
    # 来自「5. 提测前自检」第 1 条
    SubQ("SQ4", "bench/case_1440.sql是否存在", "求值", "布尔", {"路径": "bench/"}, []),
    # 与 SQ1 同 target 但来源不同 —— 用来测强同类合并
    SubQ("SQ1b", "range谓词侧改动点", "求值", "文本", {"来源": "改法前半句"}, ["源码内容"]),
    # 与 SQ3 同 target 但年份/口径不同 —— 用来测冲突
    SubQ("SQ3b", "复现73.578x差距", "求值", "数值", {"环境": "裸机非容器"}, ["可运行实例"]),
    # 不同 op —— 用来测分列
    SubQ("SQ5", "该题能否在3天内完成", "评价", "文本", {}, []),
]

# =============================================================================
# 二、证据打分（每一条都对应本地实测）
# =============================================================================
# E1: 0 无来源 / 1 指到名字 / 2 指到位置
# E2: 0 单一同源 / 1 两个疑同源 / 2 三源独立或一源+复算
# E3: 0 不可复现 / 1 部分 / 2 完整可复现

CLAIMS = [
    Claim(
        cid="C_SQ1",
        text="range 谓词侧落点在 src/oblib/common/ob_range.{h,cpp}",
        e1=1,   # 只拿到文件路径，没读到内容，不知道具体函数
        e2=0,   # 只有一个来源：tree 路径列表
        e3=0,   # 无实例，跑不了
        sources=["data/tree_2026competition.json: src/oblib/common/ob_range.cpp"],
    ),
    Claim(
        cid="C_SQ2",
        text="OR 链化简位置未定位",
        e1=0,   # tree 里搜 or_ 得 509 条，全是 for/cor 的误匹配，无专属模块
        e2=0,
        e3=0,
        sources=["data/tree_2026competition.json: 'or_' 命中均为子串误匹配"],
    ),
    Claim(
        cid="C_SQ3",
        text="73.578x 差距无法在本地重现（缺运行实例）",
        e1=2,   # issue body 给了精确版本号、revision、硬件规格
        e2=0,   # 单一来源（报告者自述），2 条评论未提供独立复现
        e3=1,   # 有完整参数但无环境
        sources=["issues_detail.json#1440 body(5910字符)", "issue-1440.md §4"],
    ),
    Claim(
        cid="C_SQ4",
        text="bench/case_1440.sql 不存在",
        e1=2,   # 指到目录，可见实际内容只有 2 个文件
        e2=0,   # 单次列目录
        e3=2,   # 任何人 ls bench/ 都能确认
        sources=["ls bench/ → eqfilter.sql, records.csv"],
        kind="observation",
    ),
    Claim(
        cid="C_SQ5",
        text="3 天内完成不可判定",
        e1=1,
        e2=0,
        e3=0,
        sources=["无工期类证据"],
    ),
]

# =============================================================================
# 三、歧义探测：task 卡的「落点」与「改法」可推出两种改动方向
# =============================================================================

FORK_RUNS = [
    {
        "interpretation": "按『区间保持原语』→ 主改 range 侧",
        "fields": {"改动模块": "ob_range.cpp", "是否需改OR层": False, "预计文件数": 1},
    },
    {
        "interpretation": "按『OR 链先化简再下推』→ 主改 OR 侧",
        "fields": {"改动模块": "未定位（OR化简器）", "是否需改OR层": True, "预计文件数": 3},
    },
]

KEY_FIELDS = ["改动模块", "是否需改OR层"]


# =============================================================================
# 四、跑
# =============================================================================

def main() -> int:
    line = "=" * 74

    print(line)
    print("真实长任务 · seekdb issue #1440")
    print("标题: Range-to-OR equivalent filters cause up to 73.578x latency difference")
    print(line)

    # --- 1. 汇总同类 ---
    print("\n【1】汇总同类 · 结构化判等")
    g = group(SUBQS)
    print(f"  {g['n_columns']} 列 / {g['n_items']} 项 / 合并 {g['merged']} 次 / 冲突 {g['conflicts']} 处")
    for col in g["columns"]:
        print(f"  列 {col['signature']}:")
        for it in col["items"]:
            extra = ""
            if it["merged_in"]:
                extra += f"  并入{it['merged_in']}"
            if it["conflicted"]:
                extra += f"  冲突{it['conflicted']}"
            print(f"    - {it['target']}（主 {it['primary']}）{extra}")
        for cf in col["conflicts"]:
            print(f"    ! {cf['reason']}")

    # --- 2. 主线循环 ---
    print("\n【2】主线循环 · 留痕")
    journal = LoopJournal()
    lifted = [mainline_loop(c, journal, rounds=3) for c in CLAIMS]
    print(f"  {journal.stats()}")
    print(f"  强度建议: {journal.recommend_strength()['strength']} — {journal.recommend_strength()['reason']}")

    # --- 3. 路由 ---
    print("\n【3】冷启动路由")
    lib = TopicLibrary({"seekdb-bug-fix": 0.2})   # 库里没有这个题型的历史
    route = choose_route("seekdb-bug-fix", lib)
    print(f"  {route['route']} · {route['calls_per_subq']} 次/子问题 · {route['reason']}")

    # --- 4. 三道闸 ---
    print("\n【4】三道闸 · 逐项判定")
    verdicts = {}
    for c in lifted:
        r = run_gates(c)
        verdicts[c.cid] = r
        path = " → ".join(f"{x['gate']}:{x['verdict']}" for x in r["ledger"])
        print(f"  {c.cid:7s} e1={c.e1} e2={c.e2} e3={c.e3} C={r['C']}  {path}"
              + (f"  卡在{r['blocked_at']}" if r["blocked_at"] else ""))

    # --- 5. 歧义探测 ---
    print("\n【5】分叉探测 · 两种理解各跑一次")
    fork = detect_fork(FORK_RUNS, KEY_FIELDS)
    print(f"  forked={fork['forked']}  {fork['reason']}")
    for f, vals in fork["diverged"].items():
        print(f"    {f}: " + " | ".join(f"{v['interpretation']}={v['value']!r}" for v in vals))

    # --- 6. 缺参探测 ---
    print("\n【6】缺参探测")
    missing = detect_missing(
        ["bench/case_1440.sql", "可运行实例", "OR化简器位置"],
        {"bench/case_1440.sql": None, "可运行实例": None, "OR化简器位置": None},
    )
    print(f"  缺失: {missing}")

    # --- 7. 提问闸 ---
    print("\n【7】提问闸 · 不回答会怎样")
    qs = build_questions(fork, missing, defaults={
        "bench/case_1440.sql": "自建 bench/case_1440.sql",
        "可运行实例": "跳过复现，仅静态分析",
        "OR化简器位置": "按 range 侧单点修改",
    })
    for q in qs:
        print(f"  [{q.qid}] {q.reason}")
        print(f"       默认: {q.default}")
    gate_res = ask_gate(qs, answered={}, wait_rounds=2)
    print(f"  状态: {gate_res['state']}")

    # --- 8. 结论 ---
    print("\n【8】结论")
    passed = [k for k, v in verdicts.items() if v["final"] == "pass"]
    rejected = [k for k, v in verdicts.items() if v["final"] == "reject"]
    blocked = {k: v["blocked_at"] for k, v in verdicts.items() if v["blocked_at"]}
    print(f"  通过 {len(passed)}/{len(verdicts)} 项: {passed}")
    print(f"  打回 {len(rejected)}/{len(verdicts)} 项: {rejected}")
    if blocked:
        from collections import Counter
        cnt = Counter(blocked.values())
        print(f"  卡口分布: {dict(cnt)}")
    print()
    headline = (f"本题当前不具备落地条件：{len(verdicts)} 个子问题中 "
                f"{len(rejected)} 个被打回（卡口 {dict(Counter(blocked.values()))}），"
                f"{len(missing)} 个关键参数缺失。")
    print("  能给出去的东西：")
    print("  " + render_degraded(
        headline,
        gate_res["caveats"],
        [f"{k} 未能指到位置或复现" for k in rejected],
    ).replace("\n", "\n  "))

    print()
    print("【9】这次跑出来的三个问题")
    print("  P1 主线凭空造源：C_SQ2 原本 e1=0（OR 链位置没定位），"
          "若不限制，主线会把它抬成 2 —— 已修：e1=0 不允许被抬。")
    print("  P2 阴性结论被误杀 → 已修：加 kind=observation，位置精确且可复现时豁免独立性。"
          "C_SQ4 现可过 G2（C=4 仍在 G3 降级）。")
    print("  P3 结论文字硬编码：初版写死『4 个子问题』『2 个参数』，与实际不符 —— 已改为动态。")

    # --- 10. 环境自适应对比 ---
    print("\n【10】环境自动探测 + 自适应对比")
    env_auto, why_auto = detect_env(source_root=None, executable=None, network=True)
    print(f"  自动探测 → L{env_auto.level}：{ENV_LEVELS[env_auto.level]}")
    print(f"  依据：{why_auto['reason']}（本地只有 tree 清单，没有 .cpp 源码，也没有 observer）")
    print(f"  {'档位':<34}{'pass':>5}{'degrade':>9}{'reject':>8}")
    agg_by_level = {}
    for lvl in (3, 2, 1):
        env = EvidenceEnv(level=lvl)
        agg = {"pass": 0, "degrade": 0, "reject": 0}
        per = {}
        for c in CLAIMS:
            f = run_gates(c, env)["final"]
            agg[f] += 1
            per[c.cid] = f
        agg_by_level[lvl] = per
        print(f"  L{lvl} {ENV_LEVELS[lvl]:<30}{agg['pass']:>5}{agg['degrade']:>9}{agg['reject']:>8}")

    rescued = [k for k in agg_by_level[3]
               if agg_by_level[3][k] == "reject" and agg_by_level[1][k] != "reject"]
    print()
    print(f"  从 L3 降到 L1，救了 {len(rescued)} 项: {rescued or '无'}")
    print("  结论：环境自适应只削掉『环境造成的缺』，削不掉『本来就缺的』。")
    print("        本题被拒的主因是缺第二来源（e2=0），那属于后者——降档救不回来。")

    print()
    print(line)
    print("判定：系统给出的是『做不了 + 为什么做不了』，不是硬凑一个方案")
    print(line)

    # --- 落盘 ---
    out = {
        "issue": 1440,
        "grouping": {"columns": g["n_columns"], "items": g["n_items"],
                     "merged": g["merged"], "conflicts": g["conflicts"]},
        "journal": journal.stats(),
        "strength": journal.recommend_strength(),
        "route": route,
        "verdicts": {k: {"C": v["C"], "final": v["final"], "blocked_at": v["blocked_at"]}
                     for k, v in verdicts.items()},
        "fork": {"forked": fork["forked"], "diverged": list(fork["diverged"].keys())},
        "missing": missing,
        "ask_state": gate_res["state"],
        "conclusion": {"passed": passed, "rejected": rejected},
    }
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_case_1440.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n结果已落盘: {os.path.basename(p)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
