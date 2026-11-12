#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批次 d：把「机制适用性」接进判据，看能不能补上缺的那一维

第三十四轮的阴性对照结论：e1/e3 预测不了结论会不会被推翻。
这一轮加一维**机制适用性**（sargable.py），判同一批任务，看结论。

关键对照：
  批次 c  SARGable 任务，判据只有 e1/e3（e1=2, e3=2）→ pass
  批次 d  **同一批任务**，加上机制适用性检查        → 应该判 reject
                                （索引原理上用不上，这事根本做不成）

如果 d 组确实从 pass 翻成 reject，说明这一维补上了真东西。

跑法：
  python collect_degrade.py --batch d --dry-run
  python collect_degrade.py --batch d
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

from harness import Claim, run_gates, EvidenceEnv, derive_e3, MODEL_VERSION  # noqa: E402
import ledger as L  # noqa: E402
from sargable import sargable  # noqa: E402

DISTRO = "Ubuntu-22.04"
TMP_WSL = "/mnt/c/Users/21246/AppData/Local/Temp"

# 和批次 b/c 完全同一批任务，只是判据多了机制适用性这一维
TASKS_D = [
    ("M1", "给 age 建索引让 age+0=42 更快", "age", "ix_dg_d_age_p0",
     "SELECT COUNT(*) FROM bench_l3.t_ann WHERE age + 0 = 42", "算术恒等"),
    ("M2", "给 age 建索引让 age*1=42 更快", "age", "ix_dg_d_age_m1",
     "SELECT COUNT(*) FROM bench_l3.t_ann WHERE age * 1 = 42", "乘恒等"),
    ("M3", "给 category5 建索引让 c5+0=0 更快", "category5", "ix_dg_d_c5_p0",
     "SELECT COUNT(*) FROM bench_l3.t_ann WHERE category5 + 0 = 0", "算术恒等"),
    ("M4", "给 age 建索引让 CAST(age)=42 更快", "age", "ix_dg_d_age_cast",
     "SELECT COUNT(*) FROM bench_l3.t_ann WHERE CAST(age AS SIGNED) = 42", "函数包列"),
    ("M5", "给 age 建索引让 age=42 更快（对照）", "age", "ix_dg_d_age_ok",
     "SELECT COUNT(*) FROM bench_l3.t_ann WHERE age = 42", "无恒等，对照组"),
]

# t_ann 的真实列类型（从 information_schema 查过）
TT = {"id": "bigint", "age": "int", "category5": "int"}


def wsl(script: str, timeout: int = 400) -> tuple[int, str]:
    tmp = os.path.join(tempfile.getTempdir() if False else tempfile.gettempdir(), "dg_run.sh")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(script)
    env = dict(os.environ)
    env["WSL_UTF8"] = "1"
    r = subprocess.run(["wsl.exe", "-d", DISTRO, "--", "bash", TMP_WSL + "/dg_run.sh"],
                       capture_output=True, timeout=timeout, env=env)
    out = (r.stdout or b"").decode("utf-8", "replace") + (r.stderr or b"").decode("utf-8", "replace")
    return r.returncode, out


def parse_operator(text: str) -> str:
    for line in text.splitlines():
        if "|" in line and "SCAN" in line:
            parts = [p.strip() for p in line.strip("|").split("|")]
            if len(parts) >= 3 and parts[0].isdigit():
                return re.sub(r"[└─]+", "", parts[1]).strip()
    return ""


def main() -> int:
    L.bind_production("采集脚本：机制维度")  # 本脚本产出真实证据   # 只有真跑这个脚本才绑定，导入不绑
    dry = "--dry-run" in sys.argv
    env = EvidenceEnv(3)

    print("=" * 88)
    print("批次 d · 加入「机制适用性」这一维")
    if dry:
        print("【dry-run】不执行，不写账本")
    print("=" * 88)

    print(f"\n  {'ID':<4}{'任务':<28}{'机制可用':>9}{'判定':>9}{'成因':>8}  依据")
    print("  " + "-" * 78)
    rows = []
    for tid, name, col, idx, query, sel in TASKS_D:
        mech, reason = sargable(query, TT)
        # 机制不适用 = 这件事原理上做不成 = 关键输入无效 → 一票否决
        iv = None if mech is None else mech
        c = Claim(tid, name, e1=2, e2=0, e3=derive_e3("measured"),
                  kind="procedure", input_valid=iv)
        g = run_gates(c, env)
        print(f"  {tid:<4}{name:<28}"
              f"{('可用' if mech else '不可用' if mech is False else '判不了'):>9}"
              f"{g['final']:>9}{(g.get('cause') or '-'):>8}  {reason[:30]}")
        rows.append({"tid": tid, "name": name, "col": col, "idx": idx,
                     "query": query, "sel": sel, "g": g, "mech": mech,
                     "mech_reason": reason})

    # ---- 执行 + 复查结论 ----
    actual: dict[str, bool] = {}
    held: dict[str, bool] = {}
    detail: dict[str, str] = {}

    if dry:
        print("\n（dry-run：不执行）")
    else:
        script = ["set -u",
                  "systemctl start seekdb >/dev/null 2>&1",
                  "for i in $(seq 1 40); do",
                  "  mysql -h127.0.0.1 -P2881 -uroot@sys --connect-timeout=2 -e 'select 1' >/dev/null 2>&1 && break",
                  "  sleep 1",
                  "done"]
        for r in rows:
            idx, col, query = r["idx"], r["col"], r["query"]
            script.append(f"mysql -h127.0.0.1 -P2881 -uroot@sys -e "
                          f"'ALTER TABLE bench_l3.t_ann DROP INDEX {idx}' 2>/dev/null")
            script.append(f"if mysql -h127.0.0.1 -P2881 -uroot@sys -e "
                          f"'CREATE INDEX {idx} ON bench_l3.t_ann({col})' >/dev/null 2>&1; then")
            script.append(f"  echo \"R {r['tid']}=ok\"")
            script.append("else")
            script.append(f"  echo \"R {r['tid']}=fail\"")
            script.append("fi")
            q = query.replace("'", "'\\''")
            script.append(f"echo \"P {r['tid']}\"")
            script.append(f"mysql -h127.0.0.1 -P2881 -uroot@sys bench_l3 -e \"EXPLAIN {q}\" 2>&1")
            script.append(f"echo \"E {r['tid']}\"")
        code, out = wsl("\n".join(script), timeout=400)
        cur = None
        buf: dict[str, list[str]] = {}
        for line in out.splitlines():
            if line.startswith("R "):
                k, _, v = line[2:].partition("=")
                actual[k.strip()] = (v.strip() == "ok")
            elif line.startswith("P "):
                cur = line[2:].strip()
                buf.setdefault(cur, [])
            elif line.startswith("E "):
                cur = None
            elif cur:
                buf[cur].append(line)
        for r in rows:
            tid = r["tid"]
            op = parse_operator("\n".join(buf.get(tid, [])))
            detail[tid] = op or "(无计划)"
            held[tid] = ("RANGE" in op) or ("INDEX" in op)

    print(f"\n  {'ID':<4}{'任务':<28}{'实际':>6}{'结论':>8}{'算子':<20}")
    print("  " + "-" * 70)
    for r in rows:
        tid = r["tid"]
        act = actual.get(tid)
        h = held.get(tid)
        print(f"  {tid:<4}{r['name']:<28}"
              f"{('成' if act else '败' if act is False else '-'):>6}"
              f"{('成立' if h else '被推翻' if h is False else '-'):>8}"
              f"  {detail.get(tid, ''):<18}")

    if not dry:
        for r in rows:
            tid = r["tid"]
            if actual.get(tid) is None:
                continue
            L.record(r["g"]["final"], task=f"机制维度·{tid} {r['name']}",
                     note=f"机制适用性={r['mech_reason'][:40]}",
                     success=actual[tid],
                     evidence=f"算子={detail.get(tid,'')} 机制={r['mech_reason'][:40]}",
                     env_level=env.level,
                     cause=r["g"].get("cause"),
                     conclusion_held=held.get(tid),
                     group="d",
                     origin="collect")
        print("\n已记入批次 d（group=d）")

    print()
    print("=" * 88)
    print("对照：")
    print("  批次 c（同一批任务，只有 e1/e3）  → 判 pass，推翻 3/5 = 60%")
    print("  批次 d（加上机制适用性）           → 见上")
    print("  若 d 组被判 reject，说明这一维补上了 e1/e3 漏掉的东西")
    print("=" * 88)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
