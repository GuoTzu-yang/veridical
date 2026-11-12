#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
校准 e3：优化器估算到底准不准

一直凭感觉给 e3（结果可复现度）打 1 或 2。现在能算了：
  对同一个查询，EXPLAIN 给的 EST.ROWS  vs  实际 COUNT(*) 返回的行数
偏差越小，说明"看计划就能推断结果"越可信，e3 就越该给 2。

这比拍脑袋强，但也只在一个数据分布上成立——结论要带范围。

跑法：python case_l3_estacc.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 架构本体所在目录
sys.path.insert(0, ROOT)

DISTRO = "Ubuntu-22.04"
TMP_WSL = "/mnt/c/Users/21246/AppData/Local/Temp"

# 不同选择性的查询：从全表到极窄
QUERIES = [
    ("Q1", "age > 10", "宽"),
    ("Q2", "age > 50", "中"),
    ("Q3", "age > 90", "窄"),
    ("Q4", "category5 = 0", "等值"),
    ("Q5", "age > 50 AND category5 = 0", "组合"),
]


def wsl(script: str, timeout: int = 300) -> tuple[int, str]:
    tmp = os.path.join(tempfile.gettempdir(), "est_run.sh")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(script)
    env = dict(os.environ)
    env["WSL_UTF8"] = "1"
    r = subprocess.run(["wsl.exe", "-d", DISTRO, "--", "bash", TMP_WSL + "/est_run.sh"],
                       capture_output=True, timeout=timeout, env=env)
    out = (r.stdout or b"").decode("utf-8", "replace") + (r.stderr or b"").decode("utf-8", "replace")
    return r.returncode, out


def main() -> int:
    print("=" * 76)
    print("校准 e3：EXPLAIN 的 EST.ROWS 有多准")
    print("=" * 76)

    script = ["set -u",
              "systemctl start seekdb >/dev/null 2>&1",
              "for i in $(seq 1 40); do",
              "  mysql -h127.0.0.1 -P2881 -uroot@sys --connect-timeout=2 -e 'select 1' >/dev/null 2>&1 && break",
              "  sleep 1",
              "done",
              "M='mysql -h127.0.0.1 -P2881 -uroot@sys bench_l3'"]
    for qid, cond, _ in QUERIES:
        script.append(f'echo "===PLAN {qid}==="')
        script.append(f"mysql -h127.0.0.1 -P2881 -uroot@sys bench_l3 -e "
                      f"\"EXPLAIN SELECT * FROM t_ann WHERE {cond}\" 2>&1")
        script.append(f'echo "===ACT {qid}==="')
        script.append(f"mysql -h127.0.0.1 -P2881 -uroot@sys bench_l3 -N -B -e "
                      f"\"SELECT COUNT(*) FROM t_ann WHERE {cond}\" 2>&1")

    code, out = wsl("\n".join(script), timeout=300)

    plans, acts = {}, {}
    for qid, _, _ in QUERIES:
        pm = re.search(rf"===PLAN {qid}===(.*?)===ACT {qid}===", out, re.S)
        am = re.search(rf"===ACT {qid}===\s*(\d+)", out)
        if pm:
            est = None
            op = None
            for line in pm.group(1).splitlines():
                if "|" in line and "SCAN" in line:
                    parts = [p.strip() for p in line.strip("|").split("|")]
                    if len(parts) >= 5 and parts[0].isdigit():
                        op = re.sub(r"[└─]+", "", parts[1]).strip()
                        try:
                            est = int(parts[3])
                        except ValueError:
                            pass
                        break
            plans[qid] = (op, est)
        if am:
            acts[qid] = int(am.group(1))

    print(f"\n  {'ID':<4}{'条件':<28}{'算子':<20}{'EST':>7}{'实际':>7}{'偏差':>9}")
    print("  " + "-" * 76)
    errs = []
    for qid, cond, _ in QUERIES:
        op, est = plans.get(qid, (None, None))
        act = acts.get(qid)
        if est is None or act is None:
            print(f"  {qid:<4}{cond:<28}{str(op):<20}{'-':>7}{str(act):>7}{'-':>9}")
            continue
        err = abs(est - act) / act * 100 if act else 0
        errs.append(err)
        print(f"  {qid:<4}{cond:<28}{str(op):<20}{est:>7}{act:>7}{err:>8.1f}%")

    print()
    print("=" * 76)
    if errs:
        avg = sum(errs) / len(errs)
        mx = max(errs)
        print(f"平均偏差 {avg:.1f}%   最大偏差 {mx:.1f}%   样本 {len(errs)} 条")
        print()
        if avg < 20:
            print("结论：在这份数据分布上，看计划就能较可靠地推断结果 → e3 可给 2")
        else:
            print("结论：估算偏差大，看计划推不出结果 → e3 只能给 1")
        print()
        print("范围限制：")
        print("  - 只测了一种数据分布（5000 行、列值高度规律 i%100 / i%5）")
        print("  - 真实数据的相关性会让偏差显著变大，那时 e3 要回落")
    else:
        print("没取到数据")
    print("=" * 76)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
