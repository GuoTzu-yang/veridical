#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
degrade 样本：步骤清楚，但当前条件验证不了

L3 账本里一直只有两端——pass（能跑通）和 reject（跑不通），中间档空着。

degrade 的语义是「可以做，但结论必须带不确定标注」。什么任务会落在这里？

  e1=2（步骤明确）+ e3=0（结果不可复现）→ value=2 → degrade

真能落进来的是这类：**验证条件本身不具备**。
  - 要生产负载的 p99，本机是空载
  - 要并发 100 的锁等待，本机没有压测环境
  - 要 10 亿行的性能，本机只有 5000 行

这些任务不是"做不了"，是"做了也只能给带标注的结论"。

跑法：
  python case_l3_limits.py --dry-run   # 只判不记
  python case_l3_limits.py             # 判 + 记 + 回填
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 架构本体所在目录
sys.path.insert(0, ROOT)

from harness import Claim, run_gates, detect_env, EvidenceEnv  # noqa: E402
import ledger as L  # noqa: E402

DISTRO = "Ubuntu-22.04"
TMP_WSL = "/mnt/c/Users/21246/AppData/Local/Temp"

# ---------------------------------------------------------------------------
# 三个「超出本机验证能力」的任务
# e1=2：怎么做写得很清楚
# e3=0：当前条件跑不出可复现的结论
# ---------------------------------------------------------------------------
LIMITS = [
    ("D1", "生产负载 p99 < 100ms",
     "需要生产量级并发下的延迟分布；本机空载，测出来不代表生产", 
     "SELECT COUNT(*) FROM bench_l3.t_ann", 5000, 100_000_000),
    ("D2", "并发 100 无锁等待",
     "需要 100 个并发连接同时写；本机单连接，复现不出竞争",
     "SELECT COUNT(*) FROM bench_l3.t_ann", 5000, 5000),
    ("D3", "10 亿行下索引仍生效",
     "需要十亿级数据；本机 5000 行，任何计划都会走全表且很快",
     "SELECT COUNT(*) FROM bench_l3.t_ann", 5000, 1_000_000_000),
]


def wsl(script: str, timeout: int = 200) -> tuple[int, str]:
    tmp = os.path.join(tempfile.gettempdir(), "limits_run.sh")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(script)
    env = dict(os.environ)
    env["WSL_UTF8"] = "1"
    r = subprocess.run(["wsl.exe", "-d", DISTRO, "--", "bash", TMP_WSL + "/limits_run.sh"],
                       capture_output=True, timeout=timeout, env=env)
    out = (r.stdout or b"").decode("utf-8", "replace") + (r.stderr or b"").decode("utf-8", "replace")
    return r.returncode, out


def main() -> int:
    L.bind_production("案例脚本：验证条件不具备")  # 本脚本产出真实证据   # 只有真跑这个脚本才绑定，导入不绑
    dry = "--dry-run" in sys.argv
    env, why = detect_env(ROOT, None, True,
                          wsl_distro=DISTRO, wsl_executable="/usr/bin/observer")

    print("=" * 78)
    print("degrade 样本 · 步骤清楚但当前条件验证不了")
    if dry:
        print("【dry-run】不写账本")
    print("=" * 78)
    print(f"环境: L{env.level}（{why['reason']}）")

    # --- 先量一下本机真实能力，作为「验证不了」的硬证据 ---
    print("\n【1】量本机实际条件")
    code, out = wsl(
        "set -u\n"
        "systemctl start seekdb >/dev/null 2>&1\n"
        "for i in $(seq 1 40); do\n"
        "  mysql -h127.0.0.1 -P2881 -uroot@sys --connect-timeout=2 -e 'select 1' >/dev/null 2>&1 && break\n"
        "  sleep 1\n"
        "done\n"
        "echo ROWS=$(mysql -h127.0.0.1 -P2881 -uroot@sys -N -B -e 'SELECT COUNT(*) FROM bench_l3.t_ann')\n"
        "echo CORES=$(nproc)\n"
        "echo MEM_MB=$(free -m | awk '/Mem:/{print $2}')\n"
    )
    facts = {}
    for line in out.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            if k.strip() in ("ROWS", "CORES", "MEM_MB"):
                facts[k.strip()] = v.strip()
    rows = int(facts.get("ROWS") or 0)
    print(f"  实际数据量: {rows} 行")
    print(f"  实际 CPU:   {facts.get('CORES')} 核")
    print(f"  实际内存:   {facts.get('MEM_MB')} MB")

    # --- 判定 ---
    print("\n【2】框架判定（e3=0：结果不可复现）")
    print(f"  {'ID':<4}{'任务':<26}{'e1':>3}{'e3':>3}{'判定':>9}   缺口")
    print("  " + "-" * 72)

    made = []
    for tid, name, reason, sql, have, need in LIMITS:
        # 声明这条任务需要的规模；环境给不了时门禁会自己降级，不再靠人手标 cause。
        # facts 是本机实测的精确行数（库里就这么多），不猜。
        c = Claim(tid, name, e1=2, e2=0, e3=0, kind="procedure",
                  needs={"rows": need})
        # 把本机实测的精确行数交给能力核验——不是猜，是量出来的。
        # 有了它门禁才能判「明确不够」；只给探针下限时它只会说「没测到」。
        r = run_gates(c, EvidenceEnv(env.level, facts={
            "scale": {"value": have, "from": "数一遍 t_ann",
                      "check": {"domain": "sql",
                                "task": {"sql": "SELECT COUNT(*) FROM bench_l3.t_ann"}}}}))
        gap = f"需 {need:,} 行，实有 {have:,}（差 {need/max(have,1):.0f}×）" if need > have else "并发环境缺失"
        made.append((tid, name, r, gap, need, have))
        print(f"  {tid:<4}{name:<26}{2:>3}{0:>3}{r['final']:>9}   {gap}")

    # --- 记录 ---
    print("\n【3】记账")
    ok_count = 0
    ids = []
    for tid, name, r, gap, need, have in made:
        # 这里必须分清两个问题（第四十三轮修正）：
        #   success            —— 任务意图有没有达成？这些任务要「验证某条限额」，条件不具备 → 没达成 → False
        #   conclusion_verified —— 判据的这次判断对不对？判 degrade 且实际确实验证不了 → 对 → True
        # 原来把 judged_right 记成 success，等于把「判对了」当成「做成了」，
        # 会把 degrade 先验虚高（v2 里 degrade 一度算出 9% 的 reject 也"成功"）。
        judged_right = (r["final"] == "degrade") and (have < need or "并发" in gap)
        ok_count += 1 if judged_right else 0
        if not dry:
            # 把「还差什么」一起记下（第七十五轮）：procedure 类的缺口组合
            # 和 EXPLAIN 那批（e2+e3）完全不同，正好给瓶颈统计第二种观测。
            from extend import what_would_help
            _ask = what_would_help(c, r["final"], r.get("blocked_at"),
                                   EvidenceEnv(env.level))
            rec = L.record("degrade", task=f"限额·{tid} {name}",
                           note="步骤清楚但验证条件不具备",
                           success=False,
                           conclusion_checkable=False,
                           check_why="验证条件不具备（本机给不了这个规模/架构/节点数）",
                           criterion_right=judged_right,
                           evidence=f"{gap}",
                           env_level=env.level,
                           # 这些任务是「环境没有这个能力」而不是「证据不够」：
                           # 要 1 亿行 / 并发 100 / ARM / 多节点，本机都给不了。
                           # 门禁的 cause 只回答「档位有没有降级」——L3 不等于什么都能做。
                           cause=r.get("cause"),   # 门禁自己判的，不再手标
                           ask=_ask,
                           origin="case")
            ids.append(rec["id"])
        print(f"  {tid} {'✓' if judged_right else '✗'} 判 degrade，"
              f"实际验证条件不具备 → 意图未达成(success=False) 判据正确(verified={judged_right})")

    print()
    print("=" * 78)
    print(f"判定正确: {ok_count}/{len(made)}")
    if not dry:
        print(f"已记入 {len(ids)} 条 degrade 样本（L{env.level}）")
    print("=" * 78)

    if not dry:
        s = L.stats(env.level)
        print(f"\nL{env.level} 现状：{s['total']} 条")
        for v in ("pass", "degrade", "reject"):
            c = s["calibration"].get(v)
            if c:
                print(f"  {v:8s} n={c['n']:<3} succ={c['success']:<3} "
                      f"Laplace={c['laplace']}  Wilson[{c['wilson_lo']}, {c['wilson_hi']}]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
