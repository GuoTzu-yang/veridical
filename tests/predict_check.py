#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
事前预测检验：先判、再跑、后回填

前十二轮的所有样本都是"先跑后记"——只能证明管道通，不能证明判据准。
这一轮反过来：**先让框架判，再执行，看命中率**。

关键设计：任务里故意混入**必然失败**的 SQL（查不存在的表、语法错、向量维度不匹配）。
如果框架对这些也判 pass，就说明判据有盲区——这正是要测的。

跑法：python predict_check.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 架构本体所在目录
sys.path.insert(0, ROOT)

from harness import Claim, run_gates, EvidenceEnv, detect_env  # noqa: E402
from taskgraph import TaskGraph, Item  # noqa: E402
import ledger as L  # noqa: E402
from sqlcheck import precheck, _tables  # noqa: E402

DISTRO = "Ubuntu-22.04"
TMP_WSL = "/mnt/c/Users/21246/AppData/Local/Temp"

# ---------------------------------------------------------------------------
# 八个任务：四个应当成功，四个应当失败
# 评估时只看"步骤是否清楚"，**不看**它们会不会失败
# ---------------------------------------------------------------------------
TASKS = [
    ("P1", "建普通表",       "CREATE TABLE IF NOT EXISTS bench_l3.t_p1(a INT)", True,
     "合法 DDL"),
    ("P2", "建带向量表",      "CREATE TABLE IF NOT EXISTS bench_l3.t_p2(a INT, b VECTOR(3))", True,
     "合法向量 DDL"),
    ("P3", "插入合法行",      "INSERT INTO bench_l3.t_p1 VALUES (1),(2),(3)", True,
     "合法 DML"),
    ("P4", "LIMIT 0 查询",   "SELECT * FROM bench_l3.t_p1 LIMIT 0", True,
     "边界但合法"),
    ("Q1", "查不存在的表",    "SELECT * FROM bench_l3.no_such_table", False,
     "表不存在"),
    ("Q2", "语法错误",       "SELECT bad_syntax FROM", False,
     "SQL 语法残缺"),
    ("Q3", "向量维度不匹配",   "INSERT INTO bench_l3.t_p2 VALUES (1, '[1,2]')", False,
     "声明 VECTOR(3) 却插 2 维"),
    ("Q4", "引用不存在的列",   "SELECT no_such_col FROM bench_l3.t_p1", False,
     "列不存在"),
]


def wsl(script: str, timeout: int = 300) -> tuple[int, str]:
    tmp = os.path.join(tempfile.gettempdir(), "predict_run.sh")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(script)
    env = dict(os.environ)
    env["WSL_UTF8"] = "1"
    r = subprocess.run(["wsl.exe", "-d", DISTRO, "--", "bash", TMP_WSL + "/predict_run.sh"],
                       capture_output=True, timeout=timeout, env=env)
    out = (r.stdout or b"").decode("utf-8", "replace") + (r.stderr or b"").decode("utf-8", "replace")
    return r.returncode, out


def main() -> int:
    L.bind_production("案例脚本：事前预测")  # 本脚本产出真实证据   # 只有真跑这个脚本才绑定，导入不绑
    # --dry-run：只判不记，用于反复试验而不污染账本
    dry = "--dry-run" in sys.argv

    env, why = detect_env(ROOT, None, True,
                          wsl_distro=DISTRO, wsl_executable="/usr/bin/observer")
    print("=" * 78)
    print("事前预测检验 · 先判 → 再跑 → 后回填")
    if dry:
        print("【dry-run】不写账本")
    print("=" * 78)
    print(f"环境: L{env.level}（{why['reason']}）")

    # ---- 阶段 1：先判 ----
    print("\n【1】框架先判（此时不知道会不会失败）")
    tables = _tables()
    print(f"  当前 {DB if 'DB' in dir() else 'bench_l3'} 里的表: {sorted(tables) or '（空）'}")
    print(f"  {'ID':<4}{'任务':<14}{'前置':>6}{'e1':>3}{'e3':>3}{'判定':>9}{'先验':>8}")
    print("  " + "-" * 58)

    pending = []
    for tid, name, sql, _should_ok, _why in TASKS:
        # 关键改动：执行之前先查「这一步现在做得了吗」
        feasible, reason = precheck(sql, tables)
        # 评估只看"步骤是否清楚" + "关键输入是否有效"
        c = Claim(tid, name, e1=2, e2=0, e3=2, kind="procedure",
                  input_valid=feasible)
        r = run_gates(c, env)
        prior, _ = L.current_prior(env_level=env.level)
        p = prior[r["final"]]
        rec = L.record(verdict=r["final"], task=f"预测·{tid} {name}",
                       note="事前预测（执行前记录）", success=None,
                       evidence=f"precheck={'ok' if feasible else reason} | sql={sql[:40]}",
                       env_level=env.level,
                       cause=r.get("cause"),
                       origin="case") if not dry else {"id": "(dry-run)"}
        pending.append({"tid": tid, "name": name, "sql": sql,
                        "verdict": r["final"], "p": p, "rid": rec["id"],
                        "feasible": feasible, "reason": reason})
        mark = "✓" if feasible else "✗"
        print(f"  {tid:<4}{name:<14}{mark:>6}{2:>3}{2:>3}{r['final']:>9}{p:>8}")
        if not feasible:
            print(f"       └ {reason}")

    # ---- 阶段 2：执行 ----
    print("\n【2】在 WSL seekdb 上逐条执行")
    lines = ["set -u",
             "systemctl start seekdb >/dev/null 2>&1",
             "for i in $(seq 1 40); do",
             "  mysql -h127.0.0.1 -P2881 -uroot@sys --connect-timeout=2 -e 'select 1' >/dev/null 2>&1 && break",
             "  sleep 1",
             "done",
             "M=$(which mysql)",
             "mysql -h127.0.0.1 -P2881 -uroot@sys -e 'CREATE DATABASE IF NOT EXISTS bench_l3' 2>/dev/null",
             "mysql -h127.0.0.1 -P2881 -uroot@sys -e 'DROP TABLE IF EXISTS bench_l3.t_p2' 2>/dev/null"]
    for t in pending:
        sql = t["sql"].replace("'", "'\\''")
        lines.append(f"if mysql -h127.0.0.1 -P2881 -uroot@sys -e '{sql}' 2>/dev/null; then")
        lines.append(f"  echo \"RESULT {t['tid']}=ok\"")
        lines.append("else")
        lines.append(f"  echo \"RESULT {t['tid']}=fail\"")
        lines.append("fi")
    code, out = wsl("\n".join(lines), timeout=300)

    actual = {}
    for line in out.splitlines():
        if line.startswith("RESULT "):
            k, _, v = line[7:].partition("=")
            actual[k.strip()] = (v.strip() == "ok")

    print(f"  {'ID':<4}{'任务':<14}{'实际':>8}{'依据'}")
    print("  " + "-" * 50)
    for t in pending:
        ok = actual.get(t["tid"])
        note = ""
        if ok is None:
            note = "未执行"
        print(f"  {t['tid']:<4}{t['name']:<14}{('成功' if ok else '失败' if ok is False else '?'):>8}  {note}")

    # ---- 阶段 3：回填 ----
    print("\n【3】回填账本")
    hit = 0
    scored = 0
    print(f"  {'ID':<4}{'预测':<9}{'实际':<7}{'命中'}")
    print("  " + "-" * 34)
    for t in pending:
        ok = actual.get(t["tid"])
        if ok is None:
            continue
        scored += 1
        predicted_ok = t["verdict"] in ("pass", "degrade")
        correct = predicted_ok == ok
        hit += 1 if correct else 0
        if not dry:
            L.resolve(t["rid"], ok, f"predict_check.py 执行结果 {'成功' if ok else '失败'}")
        print(f"  {t['tid']:<4}{t['verdict']:<9}{('成功' if ok else '失败'):<7}{'✓' if correct else '✗'}")

    print()
    print("=" * 78)
    print(f"命中率: {hit}/{scored} = {hit/scored*100:.0f}%" if scored else "没有可评分的任务")
    print("=" * 78)

    if hit < scored:
        print("\n误判明细：")
        for t in pending:
            ok = actual.get(t["tid"])
            if ok is None:
                continue
            predicted_ok = t["verdict"] in ("pass", "degrade")
            if predicted_ok != ok:
                print(f"  {t['tid']} {t['name']}：判 {t['verdict']}，实际 {'成功' if ok else '失败'}"
                      f"  —— {next(x[4] for x in TASKS if x[0] == t['tid'])}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
