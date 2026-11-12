#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
攒 v2 样本：不再改判据，只跑真实任务

第二十七轮的结论：当前判据（v2）只有 1 条样本，而框架已经有
三态前置检查、e3 来源推导、cause 分流、复合键先验、版本隔离。

继续改判据，只会让这 1 条也变成旧版本。所以这一轮**只攒数据**。

十二个任务，覆盖三档：
  pass    —— 做得了，也能验证（建表/插入/计数/建索引/删索引）
  degrade —— 做了，但「算不算达成」说不清（优化方向不唯一、指标是估算）
  reject  —— 做不了（表/列/库不存在、语法错、维度不符）

每个任务的成败都由**真实执行**决定，不预先写死。

跑法：
  python collect_v2.py --dry-run
  python collect_v2.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 架构本体所在目录
sys.path.insert(0, ROOT)

from harness import Claim, run_gates, detect_env, derive_e3, e3_reason  # noqa: E402
import ledger as L  # noqa: E402
import precheck as P  # noqa: E402

DISTRO = "Ubuntu-22.04"
TMP_WSL = "/mnt/c/Users/21246/AppData/Local/Temp"

# (id, 说明, sql, e1, e3_source, 期望判定)
TASKS = [
    ("A1", "建表 t_c1",        "CREATE TABLE IF NOT EXISTS bench_l3.t_c1(a INT, b VECTOR(3))",
     2, "measured", "pass"),
    ("A2", "插入 5 行",        "INSERT INTO bench_l3.t_c1 VALUES (1,'[1,0,0]'),(2,'[0,1,0]'),(3,'[0,0,1]'),(4,'[1,1,0]'),(5,'[0,0,0]')",
     2, "measured", "pass"),
    ("A3", "计数",             "SELECT COUNT(*) FROM bench_l3.t_c1",
     2, "measured", "pass"),
    ("A4", "新建索引",          "CREATE INDEX idx_a ON bench_l3.t_c1(a)",
     2, "measured", "pass"),
    ("A5", "删索引",           "ALTER TABLE bench_l3.t_c1 DROP INDEX idx_a",
     2, "measured", "pass"),
    ("A6", "限 1 行查询",       "SELECT a FROM bench_l3.t_c1 ORDER BY a LIMIT 1",
     2, "measured", "pass"),

    # degrade：做得了，但「算不算达成」说不清
    ("B1", "让这条查询更快",     "SELECT COUNT(*) FROM bench_l3.t_c1 WHERE a > 2",
     1, "fullscan_est", "degrade"),
    ("B2", "确认索引是否生效",   "SELECT COUNT(*) FROM bench_l3.t_ann WHERE age > 50",
     1, "fullscan_est", "degrade"),

    # reject：做不了
    ("C1", "查不存在的表",       "SELECT * FROM bench_l3.no_such_table",
     2, "measured", "reject"),
    ("C2", "语法残缺",          "SELECT x FROM",
     2, "measured", "reject"),
    ("C3", "向量维度不符",       "INSERT INTO bench_l3.t_c1 VALUES (9,'[1,2]')",
     2, "measured", "reject"),
    ("C4", "引用不存在的列",     "SELECT no_such_col FROM bench_l3.t_c1",
     2, "measured", "reject"),
]

# ---------------------------------------------------------------------------
# 第二批：补 degrade/info（差 3 条）和 reject（差 1 条）
# degrade 的共性：做得了，但「算不算达成」说不清——方向不唯一，或指标是估算
# ---------------------------------------------------------------------------
TASKS_B = [
    ("D1", "让这条查询走索引",     "CREATE INDEX idx_age2 ON bench_l3.t_ann(age)",
     1, "fullscan_est", "degrade"),
    ("D2", "减少这次全表扫描",     "SELECT COUNT(*) FROM bench_l3.t_ann WHERE age >= 0",
     1, "fullscan_est", "degrade"),
    ("D3", "评估这条查询的成本",    "EXPLAIN SELECT COUNT(*) FROM bench_l3.t_ann WHERE age > 50",
     1, "fullscan_est", "degrade"),
    ("D4", "确认数据分布是否均匀",   "SELECT category5, COUNT(*) FROM bench_l3.t_ann GROUP BY category5",
     1, "fullscan_est", "degrade"),
    ("D5", "验证索引是否被采用",    "SELECT COUNT(*) FROM bench_l3.t_ann WHERE category5 = 1",
     1, "fullscan_est", "degrade"),

    # reject：真的做不了
    ("E1", "查不存在的库",        "SELECT * FROM no_such_db.t",
     2, "measured", "reject"),
    ("E2", "插入到不存在的表",     "INSERT INTO bench_l3.no_such_table VALUES (1)",
     2, "measured", "reject"),
    ("E3", "语法错（缺表名）",     "SELECT a FROM WHERE b = 1",
     2, "measured", "reject"),
]

# ---------------------------------------------------------------------------
# 「跑成功」≠「目标达成」
# ---------------------------------------------------------------------------
# 第四十四轮修正：原来所有任务都记 success = 执行成功。
# 对"A1 新建表"这类纯动作任务是对的；但对"B1 让这条查询更快"就错了——
# SQL 只是跑了个 SELECT，根本没做任何优化，目标显然没达成。
#
# 判据：**这条 SQL 是否真的做了任务名说的那件事**。
#   D1 让查询走索引   → CREATE INDEX 就是达成动作           → True
#   D3 评估查询成本   → EXPLAIN 就是评估                   → True
#   D4 确认数据分布   → GROUP BY 给出了分布                → True
#   B1 让查询更快     → 只跑了 SELECT，没优化               → False
#   B2 确认索引用没用 → 只拿到行数，没看执行计划            → False
#   D2 减少全表扫描   → 又跑了一次全表扫描，没减少          → False
#   D5 验证索引被采用 → 普通 SELECT 看不出索引有没有用      → False
INTENT_ACHIEVED = {
    "B1": False, "B2": False,
    "D1": True, "D2": False, "D3": True, "D4": True, "D5": False,
}

# 这 7 个结论已由 tests/measure_v2_conclusion.py 用 EXPLAIN 实测并记账。
# 本脚本若再记一遍，同一结论会算两次，推翻率被稀释。
# 跳过它们不是删证据：实测那 7 条就在账本里，前缀是 v2实测·。
MEASURED_ELSEWHERE = ("B1", "B2", "D1", "D2", "D3", "D4", "D5")


# 采集时建了又删的临时表：查它们的样本**依赖会消失的状态**，
# 重跑必然对不上（不是记错）。这类不挂 replay 规格，如实报查不了。
_EPHEMERAL = ("t_c1", "t_g")

def _replay_spec(sql: str):
    low = (sql or "").lower()
    if any(t in low for t in _EPHEMERAL):
        return None
    return {"domain": "sql", "task": {"sql": sql}}

BATCHES = {"a": TASKS, "b": TASKS_B}


def wsl(script: str, timeout: int = 400) -> tuple[int, str]:
    tmp = os.path.join(tempfile.gettempdir(), "collect_run.sh")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(script)
    env = dict(os.environ)
    env["WSL_UTF8"] = "1"
    r = subprocess.run(["wsl.exe", "-d", DISTRO, "--", "bash", TMP_WSL + "/collect_run.sh"],
                       capture_output=True, timeout=timeout, env=env)
    out = (r.stdout or b"").decode("utf-8", "replace") + (r.stderr or b"").decode("utf-8", "replace")
    return r.returncode, out


def main() -> int:
    L.bind_production("采集脚本：真实 SQL 任务")  # 本脚本产出真实证据   # 只有真跑这个脚本才绑定，导入不绑
    dry = "--dry-run" in sys.argv
    batch = "a"
    if "--batch" in sys.argv:
        i = sys.argv.index("--batch")
        if i + 1 < len(sys.argv):
            batch = sys.argv[i + 1]
    if batch not in BATCHES:
        print(f"未知批次 {batch}，可用：{sorted(BATCHES)}")
        return 2
    tasks = BATCHES[batch]

    env, why = detect_env(ROOT, None, True,
                          wsl_distro=DISTRO, wsl_executable="/usr/bin/observer")

    print("=" * 84)
    print(f"攒 v2 样本 · 批次 {batch.upper()} · 只跑不改判据")
    if dry:
        print("【dry-run】不写账本")
    print("=" * 84)
    print(f"环境: L{env.level}   任务数: {len(tasks)}")

    # 一次 WSL 调用搞定：起库 → 清场地 → 按顺序执行 → 输出每步成败
    # 不能分开调用：WSL 在所有终端退出后会回收 VM，seekdb 跟着没了
    #
    # dry-run 绝不碰数据库。第二十八轮踩过：dry-run 也执行了 SQL，
    # 把 CREATE INDEX 真建了出来，正式跑时「索引已存在」导致这条任务判错。
    # dry-run 的语义是"只看不摸"，不是"跑一遍但不记账"。
    actual: dict[str, bool] = {}
    if dry:
        print("\n（dry-run：不执行任何 SQL，只显示事前判定）")
    else:
        script = ["set -u",
                  "systemctl start seekdb >/dev/null 2>&1",
                  "for i in $(seq 1 40); do",
                  "  mysql -h127.0.0.1 -P2881 -uroot@sys --connect-timeout=2 -e 'select 1' >/dev/null 2>&1 && break",
                  "  sleep 1",
                  "done",
                  "mysql -h127.0.0.1 -P2881 -uroot@sys -e 'CREATE DATABASE IF NOT EXISTS bench_l3' 2>/dev/null",
                  "mysql -h127.0.0.1 -P2881 -uroot@sys -e 'DROP TABLE IF EXISTS bench_l3.t_c1' 2>/dev/null",
                  "mysql -h127.0.0.1 -P2881 -uroot@sys -e 'ALTER TABLE bench_l3.t_ann DROP INDEX idx_age2' 2>/dev/null"]
        for tid, name, sql, e1, src, want in tasks:
            q = sql.replace("'", "'\\''")
            script.append(f"if mysql -h127.0.0.1 -P2881 -uroot@sys -e '{q}' >/dev/null 2>&1; then")
            script.append(f"  echo \"R {tid}=ok\"")
            script.append("else")
            script.append(f"  echo \"R {tid}=fail\"")
            script.append("fi")
        code, out = wsl("\n".join(script), timeout=400)
        for line in out.splitlines():
            if line.startswith("R "):
                k, _, v = line[2:].partition("=")
                actual[k.strip()] = (v.strip() == "ok")

    # 起始表集合（执行完才发现，但对 A1 之前的状态判断够用了——
    # 因为脚本开头就 DROP 了 t_c1）
    base_tables = {"t_ann", "t_p1", "t_p2", "t_c1"} - {"t_c1"}

    # ---- 边执行边判断：串行依赖必须按顺序判 ----
    # 批量预判的错误在第一次 dry-run 就暴露了：A2/A3/A6 依赖 A1 建的表，
    # 一次性判断时表还不存在，全被判 reject，实际却都能跑。
    print(f"\n【1】按执行顺序逐条判定（前置紧跟执行）")
    print(f"  {'ID':<4}{'任务':<20}{'前置':>6}{'e1':>3}{'e3':>3}{'判定':>9}{'期望':>9}{'实际':>7}  一致")
    print("  " + "-" * 82)

    known = set(base_tables)
    rows = []
    for (tid, name, sql, e1, src, want) in tasks:
        pr = P.check_task("sql", {"sql": sql}) if False else None
        # 用本地维护的表集合判断（避免每条都打一次数据库）
        from sqlcheck import precheck as sql_precheck
        ok, reason = sql_precheck(sql, known)
        status = "ok" if ok else "fail"

        e3 = derive_e3(src)
        c = Claim(tid, name, e1=e1, e2=0, e3=e3, kind="procedure",
                  input_valid=ok)
        g = run_gates(c, env)
        act = actual.get(tid)

        predicted_ok = g["final"] in ("pass", "degrade")
        consistent = (predicted_ok == act) if act is not None else None
        mark = "✓" if consistent else ("✗" if consistent is False else "?")

        print(f"  {tid:<4}{name:<20}{('✓' if ok else '✗'):>6}{e1:>3}{e3:>3}"
              f"{g['final']:>9}{want:>9}{('成' if act else '败' if act is False else '?'):>7}  {mark}")

        rows.append({"tid": tid, "name": name, "sql": sql, "g": g,
                     "pre_ok": ok, "pre_reason": reason, "act": act,
                     "want": want, "rid": None})

        # 执行后就更新状态——这就是"边跑边看"
        if act:
            low = sql.lower()
            if "create table" in low:
                known.add("t_c1")
            if "drop index" in low or "create index" in low:
                pass    # 索引不影响表存在性

    # ---- 2. 记账 ----
    print(f"\n【2】记账（v2）")
    hit = scored = 0
    for r in rows:
        if r["act"] is None:
            continue
        scored += 1
        predicted_ok = r["g"]["final"] in ("pass", "degrade")
        hit += 1 if predicted_ok == r["act"] else 0
        if r["tid"] in MEASURED_ELSEWHERE:
            continue        # 已由 measure_v2_conclusion.py 实测记账
        if not dry:
            rec = L.record(r["g"]["final"], task=f"v2收集·{r['tid']} {r['name']}",
                           note=f"前置={'ok' if r['pre_ok'] else 'fail'}",
                           # 跑成功 ≠ 目标达成：见 INTENT_ACHIEVED
                           success=(r["act"] and INTENT_ACHIEVED.get(r["tid"], True)),
                           conclusion_checkable=False,
                           check_why="结论未实测（用的是手写 INTENT_ACHIEVED 表）",
                           exec_ok=r["act"],
                           evidence=r["pre_reason"][:60],
                           env_level=env.level,
                           cause=r["g"].get("cause"),
                           origin="collect",
                           replay=_replay_spec(r["sql"]))
            r["rid"] = rec["id"]

    print(f"  记入 {len([r for r in rows if r['rid']])} 条（dry-run 时为 0）")
    print()
    print("=" * 84)
    print(f"事前预测命中率: {hit}/{scored}" +
          (f" = {hit/scored*100:.0f}%" if scored else ""))
    print("=" * 84)

    if not dry:
        from harness import MODEL_VERSION
        s = L.stats(env.level, MODEL_VERSION)
        s_all = L.stats(env.level, None)
        print(f"\nL{env.level} 当前判据（v{MODEL_VERSION}）：{s['total']} 条"
              f"（同环境全部版本 {s_all['total']} 条）")
        for v in ("pass", "degrade", "reject"):
            c = s["calibration"].get(v)
            if c:
                print(f"  {v:8s} n={c['n']:<3} succ={c['success']:<3} "
                      f"Laplace={c['laplace']}  Wilson[{c['wilson_lo']}, {c['wilson_hi']}]")
        prior, det = L.current_prior(env_level=env.level)
        print("\n先验（v%d 口径）：" % MODEL_VERSION)
        for k in sorted(prior):
            d = det.get(k, {})
            print(f"  {k:14s} {prior[k]:.3f}  source={d.get('source','base')}  n={d.get('n','-')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
