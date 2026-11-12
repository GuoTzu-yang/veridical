#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
补齐 L3 剩余两档：degrade 再来 2 条，reject 再来 1 条

每个判定都要有**当场量出来的硬证据**，不能凭想象记：
  D4 ARM 平台性能 —— 先查 CPU 架构
  D5 跨机房复制延迟 —— 先查有几个节点
  R1 查不存在的库 —— 先查库在不在

跑法：
  python case_l3_more.py --dry-run
  python case_l3_more.py
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


def wsl(script: str, timeout: int = 200) -> tuple[int, str]:
    tmp = os.path.join(tempfile.gettempdir(), "more_run.sh")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(script)
    env = dict(os.environ)
    env["WSL_UTF8"] = "1"
    r = subprocess.run(["wsl.exe", "-d", DISTRO, "--", "bash", TMP_WSL + "/more_run.sh"],
                       capture_output=True, timeout=timeout, env=env)
    out = (r.stdout or b"").decode("utf-8", "replace") + (r.stderr or b"").decode("utf-8", "replace")
    return r.returncode, out


def main() -> int:
    L.bind_production("案例脚本：补齐档位")  # 本脚本产出真实证据   # 只有真跑这个脚本才绑定，导入不绑
    dry = "--dry-run" in sys.argv
    env, why = detect_env(ROOT, None, True,
                          wsl_distro=DISTRO, wsl_executable="/usr/bin/observer")

    print("=" * 74)
    print("补齐 L3 剩余档位")
    if dry:
        print("【dry-run】不写账本")
    print("=" * 74)

    # ---- 量硬证据 ----
    code, out = wsl(
        "set -u\n"
        "systemctl start seekdb >/dev/null 2>&1\n"
        "for i in $(seq 1 40); do\n"
        "  mysql -h127.0.0.1 -P2881 -uroot@sys --connect-timeout=2 -e 'select 1' >/dev/null 2>&1 && break\n"
        "  sleep 1\n"
        "done\n"
        "echo ARCH=$(uname -m)\n"
        "echo NODES=$(mysql -h127.0.0.1 -P2881 -uroot@sys -N -B "
        "-e 'SELECT COUNT(*) FROM oceanbase.DBA_OB_SERVERS' 2>/dev/null || echo 0)\n"
        "echo DBEXISTS=$(mysql -h127.0.0.1 -P2881 -uroot@sys -N -B "
        "\"SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name='no_such_db'\" 2>/dev/null || echo 0)\n"
    )
    facts = {}
    for line in out.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            if k.strip() in ("ARCH", "NODES", "DBEXISTS"):
                facts[k.strip()] = v.strip()

    arch = facts.get("ARCH", "?")
    nodes = int(facts.get("NODES") or 0)
    dbexists = int(facts.get("DBEXISTS") or 0)

    print(f"\n本机硬证据：")
    print(f"  CPU 架构   = {arch}")
    print(f"  集群节点数 = {nodes}")
    print(f"  no_such_db 是否存在 = {dbexists}")

    # ---- 判定 ----
    print(f"\n{'ID':<4}{'任务':<24}{'e1':>3}{'e3':>3}{'判定':>9}   依据")
    print("-" * 74)

    rows = []

    # D4：只能在 ARM 上验，本机是 x86
    c4 = Claim("D4", "ARM 平台性能一致", e1=2, e2=0, e3=0, kind="procedure")
    r4 = run_gates(c4, env)
    rows.append(("D4", "ARM 平台性能一致", r4,
                 f"本机架构 {arch}，非 aarch64", r4["final"] == "degrade"))
    print(f"{'D4':<4}{'ARM 平台性能一致':<24}{2:>3}{0:>3}{r4['final']:>9}   本机 {arch}")

    # D5：跨机房要 ≥2 节点，本机单节点
    c5 = Claim("D5", "跨机房复制延迟 < 50ms", e1=2, e2=0, e3=0, kind="procedure")
    r5 = run_gates(c5, env)
    rows.append(("D5", "跨机房复制延迟", r5,
                 f"集群 {nodes} 个节点，无法构成跨机房", r5["final"] == "degrade"))
    print(f"{'D5':<4}{'跨机房复制延迟':<24}{2:>3}{0:>3}{r5['final']:>9}   节点数 {nodes}")

    # R1：查一个确定不存在的库 —— 前置检查失败，一票否决
    c6 = Claim("R1", "查询 no_such_db 的表", e1=2, e2=0, e3=2, kind="procedure",
               input_valid=(dbexists > 0))
    r6 = run_gates(c6, env)
    rows.append(("R1", "查询不存在的库", r6,
                 f"库不存在（schema 计数 {dbexists}）", r6["final"] == "reject"))
    print(f"{'R1':<4}{'查询不存在的库':<24}{2:>3}{2:>3}{r6['final']:>9}   schema 计数 {dbexists}")

    # ---- 记账 ----
    print()
    ok = sum(1 for *_, good in rows if good)
    if not dry:
        for tid, name, r, evidence, good in rows:
            # 三条任务都是「在本机无法验证 / 无法执行」：
            #   success            —— 意图（把事验证出来）没达成 → False
            #   conclusion_verified —— 判据这次的判断对不对 → good
            # 第四十三轮修正：原来把 good 记成 success，把「判对了」当成「做成了」。
            # 把「还差什么」一起记下（第七十五轮）：procedure 类的缺口组合
            # 和 EXPLAIN 那批（e2+e3）完全不同，正好给瓶颈统计第二种观测。
            from extend import what_would_help
            # 这个循环没带 claim 对象，但 what_would_help 只看维度和 kind，
            # 用 r["dims"] 原样重建一个即可——不引入新的假设。
            _d = r["dims"]
            _c = Claim(tid, name, e1=_d["e1"], e2=_d["e2"], e3=_d["e3"],
                       kind="procedure")
            _ask = what_would_help(_c, r["final"], r.get("blocked_at"),
                                   EvidenceEnv(env.level))
            L.record(r["final"], task=f"补充·{tid} {name}",
                     note="补齐 L3 档位",
                     success=False,
                     conclusion_checkable=False,
                           check_why="验证条件不具备（本机给不了这个规模/架构/节点数）",
                           criterion_right=good,
                     evidence=evidence,
                     env_level=env.level,
                     # 这些任务是「环境没有这个能力」而不是「证据不够」：
    # 要 1 亿行 / 并发 100 / ARM / 多节点，本机都给不了。
    # 门禁的 cause 只回答「档位有没有降级」——L3 不等于什么都能做。
    cause=("env" if r["final"] == "degrade" else None),
                     ask=_ask,
                     origin="case")
        print(f"已记入 {len(rows)} 条（L{env.level}）"
              f"  判据正确 {ok}/{len(rows)}")

    print("=" * 74)
    print(f"判定与证据相符: {ok}/{len(rows)}")
    print("=" * 74)

    if not dry:
        s = L.stats(env.level)
        print(f"\nL{env.level} 现状：{s['total']} 条")
        for v in ("pass", "degrade", "reject"):
            c = s["calibration"].get(v)
            if c:
                print(f"  {v:8s} n={c['n']:<3} succ={c['success']:<3} "
                      f"Laplace={c['laplace']}  Wilson[{c['wilson_lo']}, {c['wilson_hi']}]")
        prior, det = L.current_prior(env_level=env.level)
        print("\nL3 先验：")
        for k, v in prior.items():
            # det 里不一定有每个键——v2 起 degrade 拆成了 degrade/env、degrade/info，
            # 基键 'degrade' 只作兜底，没有它自己的明细条目
            d = det.get(k) or {}
            print(f"  {k:14s} {v:.3f}  source={d.get('source', 'base')}"
                  f"  n={d.get('n', '-')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
