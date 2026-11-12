#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用 model1 架构评估 OceanBase 训练营题：seekdb 基础实践（部署、Fork、PR，共 30 分）

来源：https://open.oceanbase.com/train/detail/21?questionId=600071
题面取自用户截图（页面为 SPA，web_fetch 只能拿到标题）。

注意：这是**评估**，不是替用户执行。部署与 Fork 需要他的账号和环境。

跑法：python case_train.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import Claim, SubQ, group, run_gates, detect_missing, build_questions, \
    ask_gate, render_degraded, EvidenceEnv, ENV_LEVELS, detect_env  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 架构本体所在目录

# ---------------------------------------------------------------------------
# 题面拆解：三个实践任务，每题 10 分，平台自动核验
# ---------------------------------------------------------------------------
SUBQS = [
    SubQ("T1", "部署UUID", "求值", "文本", {"来源": "题面一"}, ["seekdb实例"]),
    SubQ("T2", "Fork验证行", "求值", "文本", {"来源": "题面二"}, ["GitHub账号"]),
    SubQ("T3", "PR验证行", "求值", "文本", {"来源": "题面三"}, ["GitHub账号", "PR子题要求"]),
]

# 规程类：判据用 e1+e3，独立性不适用
CLAIMS = [
    Claim(
        cid="C_T1", text="部署 seekdb 后在配置文件取 36 位 UUID 填入表单",
        e1=2,   # 题面明确：配置文件里找、36 位含连字符、仅提交 UUID 不取验证行
        e2=0,   # 规程类不使用
        e3=2,   # 平台查遥测上报，确认存在且未被认领
        kind="procedure",
        sources=["题面一", "seekdb_pkg/report.json clusterId"],
    ),
    Claim(
        cid="C_T2", text="Fork 官方仓库 → 取本队验证行 → 原样加入 README 并提交",
        e1=2,   # 四步 + "原样、独立一行" + 填 Fork 仓库 HTTPS 地址
        e2=0,
        e3=2,   # 平台核验是否为真 Fork + README 是否含验证行
        kind="procedure",
        sources=["题面二"],
    ),
    Claim(
        cid="C_T3", text="向 oceanbase/seekdb 提交 PR，验证行写进 PR 正文",
        e1=1,   # 步骤清楚，但「按 PR 子题要求完成修改」——子题要求尚未获取
        e2=0,
        e3=2,   # 平台核验 PR 存在 + 正文含验证行 + 链接格式
        kind="procedure",
        sources=["题面三"],
    ),
]


def main() -> int:
    print("=" * 78)
    print("OceanBase 训练营 · seekdb 基础实践（部署 / Fork / PR，共 30 分）")
    print("=" * 78)

    # --- 0. 环境 ---
    env, why = detect_env(ROOT, None, True)
    print(f"\n【0】环境自动探测 → L{env.level}：{ENV_LEVELS[env.level]}")
    print(f"     依据：{why['reason']}")
    print("     本题额外需要：可运行的 seekdb 实例 + GitHub 账号（本地均无）")

    # --- 1. 拆解 ---
    print("\n【1】题面拆解")
    g = group(SUBQS)
    for col in g["columns"]:
        for it in col["items"]:
            print(f"     {it['primary']:<4}{it['target']:<14}签名{col['signature']}")

    # --- 2. 规程类判定 ---
    print("\n【2】三道闸（规程类判据：e1+e3，独立性不适用）")
    verdicts = {}
    for c in CLAIMS:
        r = run_gates(c, env)
        verdicts[c.cid] = r
        uses = r["ledger"][1]["uses"] if len(r["ledger"]) > 1 else ["-"]
        print(f"     {c.cid:6s} e1={c.e1} e3={c.e3} C={r['C']} uses={uses} → {r['final']}"
              + ("  [环境受限]" if r["env_limited"] else ""))

    # --- 3. 对照：换成世界断言判据会怎样 ---
    print("\n【3】对照 · 若按「世界断言」判据判同一批题")
    for c in CLAIMS:
        alt = Claim(cid=c.cid, text=c.text, e1=c.e1, e2=c.e2, e3=c.e3, kind="world")
        r = run_gates(alt, env)
        base = verdicts[c.cid]["final"]
        flag = "  ← 判据选错，可做的题被毙" if base != r["final"] else ""
        print(f"     {c.cid:6s} 规程类={base:8s} 世界类={r['final']:8s}{flag}")

    # --- 4. 缺参 ---
    print("\n【4】缺参探测")
    missing = detect_missing(
        ["seekdb实例", "GitHub账号", "PR子题要求"],
        {"seekdb实例": None, "GitHub账号": None, "PR子题要求": None},
    )
    print(f"     缺失：{missing}")

    qs = build_questions(None, missing, defaults={
        "seekdb实例": "按官方 docker 部署",
        "GitHub账号": "用队伍账号 Fork",
        "PR子题要求": "待查 PR 子题页面",
    })
    res = ask_gate(qs, answered={}, wait_rounds=0)
    print(f"     提问闸（批处理模式）: {res['state']}")

    # --- 5. 结论 ---
    print("\n【5】结论")
    ok = [k for k, v in verdicts.items() if v["final"] in ("pass", "degrade")]
    bad = [k for k, v in verdicts.items() if v["final"] == "reject"]
    head = (f"三项均具备执行条件（{len(ok)}/3 判 degrade）：步骤明确、平台可核验。"
            if not bad else
            f"{len(ok)}/3 可执行，{len(bad)} 项被打回。")
    print(f"     可执行：{ok}")
    print(f"     打回：  {bad or '无'}")
    print()
    print("  " + render_degraded(
        head + " 缺口不在题面，在执行条件：需要 seekdb 实例与 GitHub 账号；"
               "第三项还需先拿到 PR 子题的具体修改要求。",
        res["caveats"],
        ["本地无 seekdb 实例与 GitHub 账号，无法替用户执行",
         "浏览器实例未登录 OceanBase，点『立即提测』直接跳登录页"],
    ).replace("\n", "\n  "))

    print()
    print("=" * 78)
    print("架构能做的到此为止：给出拆解、判定、缺什么、怎么补。")
    print("实际部署与 Fork 需要你的账号和环境，我不动。")
    print("=" * 78)

    # --- 6. 实际结果回填（2026-11-06 01:31 提测） ---
    print()
    print("=" * 78)
    print("实际结果 · 平台提测记录")
    print("=" * 78)
    actual = {
        "T1": ("成功", 10),
        "T2": ("成功", 10),
        "T3": ("成功", 10),
    }
    print("  记录: 2026-11-06 01:31 · 执行成功 · 30.000 · 成功3 失败0")
    print()
    print(f"  {'子任务':<6}{'架构预判':<10}{'实际':<8}{'得分':>4}   一致?")
    print("  " + "-" * 56)
    agree = 0
    for c in CLAIMS:
        verdict = verdicts[c.cid]["final"]
        res, sc = actual[c.cid.split("_")[-1]]
        same = (verdict in ("pass", "degrade")) and res == "成功"
        agree += 1 if same else 0
        print(f"  {c.cid.split('_')[-1]:<6}{verdict:<10}{res:<8}{sc:>4}   {'✓' if same else '✗'}")

    print(f"\n  预判与实际一致: {agree}/{len(CLAIMS)}")
    print(f"  预测总分 {sum(actual[k][1] for k in actual)} 分归属: 全部拿到")
    print()
    print("  这是这套架构第一次被现实校验：")
    print("    它判三项都是 degrade（步骤清楚、可执行、但没实际跑过，不下 pass）")
    print("    实际三项全过——degrade 是保守的一侧，没有误判为 pass，也没有误杀。")
    print()
    print("  校准含义：")
    print("    procedure 类的判据（e1+e3>=3）在 L2 环境下给出的降级判定，是可靠的下界。")
    print("    但它还不能区分「会成功」和「不会成功」——要区分，需要一条失败样本做对照。")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
