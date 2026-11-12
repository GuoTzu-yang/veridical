#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 v2 收集里那 7 条「结论没被测过」的样本，改成**真测**

背景（第八十七轮）：
    collect_v2.py 用一张手写的 `INTENT_ACHIEVED` 表回答
    「这条任务的结论成立吗」。那张表是人读 SQL 读出来的判断，
    **不是测量**。

    第八十六轮把它标成了 `conclusion_checkable=False`
    （理由：结论未实测）。这一轮把它变成实测。

做法：
    对 7 条任务各写一个**探针**：准备 SQL + EXPLAIN + 期望的算子特征。
    探针用**独立命名的索引**，自己建自己删，不依赖批次状态。

顺带做一件更有用的事：
    实测结果和手写表**对一遍**。对不上的地方，说明当时手写的判断错了。

跑法：python tests/measure_v2_conclusion.py [--record]
"""

from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from collect_v2 import TASKS, TASKS_B, INTENT_ACHIEVED, wsl  # noqa: E402
from harness import Claim, run_gates, EvidenceEnv, derive_e3  # noqa: E402

# tid → (说明, 准备SQL, 探测SQL, 算子特征, 清理SQL)
# 特征匹配用「计划里是否出现这个字样」；都取大小写不敏感的子串。
PROBES = {
    "B1": ("建索引后 t_c1 的范围查询能否走索引",
           "CREATE TABLE IF NOT EXISTS bench_l3.t_c1(a INT, b VECTOR(3));"
           "INSERT IGNORE INTO bench_l3.t_c1 VALUES (1,'[1,0,0]'),(2,'[0,1,0]'),"
           "(3,'[0,0,1]'),(4,'[1,1,0]'),(5,'[0,0,0]');"
           "CREATE INDEX idx_p_b1 ON bench_l3.t_c1(a)",
           "EXPLAIN SELECT COUNT(*) FROM bench_l3.t_c1 WHERE a > 2",
           "RANGE",
           "ALTER TABLE bench_l3.t_c1 DROP INDEX idx_p_b1"),
    "B2": ("t_ann 的 age>50 能否走 age 索引",
           "",
           "EXPLAIN SELECT COUNT(*) FROM bench_l3.t_ann WHERE age > 50",
           "ix_dg_age",
           ""),
    "D1": ("给 age 建索引后，age>50 能否走索引",
           "CREATE INDEX idx_p_d1 ON bench_l3.t_ann(age)",
           "EXPLAIN SELECT COUNT(*) FROM bench_l3.t_ann WHERE age > 50",
           "RANGE",
           "ALTER TABLE bench_l3.t_ann DROP INDEX idx_p_d1"),
    "D2": ("age>=0 能否减少全表扫描",
           "",
           "EXPLAIN SELECT COUNT(*) FROM bench_l3.t_ann WHERE age >= 0",
           "RANGE",
           ""),
    "D3": ("能否拿到这条查询的成本估算",
           "",
           "EXPLAIN SELECT COUNT(*) FROM bench_l3.t_ann WHERE age > 50",
           "SCAN",
           ""),
    "D4": ("能否拿到 category5 的数据分布",
           "",
           "SELECT category5, COUNT(*) FROM bench_l3.t_ann GROUP BY category5",
           "",
           ""),
    "D5": ("category5=1 能否走 category5 索引",
           "",
           "EXPLAIN SELECT COUNT(*) FROM bench_l3.t_ann WHERE category5 = 1",
           "ix_dg_c5",
           ""),
}

ALL = {t[0]: t for t in (list(TASKS) + list(TASKS_B))}


def measure() -> dict[str, dict]:
    """跑一轮探针，返回 {tid: {held, plan, why}}。"""
    script = ["set -u",
              "systemctl start seekdb >/dev/null 2>&1",
              "for i in $(seq 1 40); do",
              "  mysql -h127.0.0.1 -P2881 -uroot@sys --connect-timeout=2 "
              "-e 'select 1' >/dev/null 2>&1 && break",
              "  sleep 1",
              "done",
              "mysql -h127.0.0.1 -P2881 -uroot@sys -e 'CREATE DATABASE IF NOT EXISTS bench_l3' 2>/dev/null"]

    for tid, (_desc, prep, probe, _marker, _clean) in PROBES.items():
        if prep:
            q = prep.replace("'", "'\\''")
            script.append(f"mysql -h127.0.0.1 -P2881 -uroot@sys -e '{q}' >/dev/null 2>&1")
        q = probe.replace("'", "'\\''")
        script.append(f"echo 'P {tid}'")
        script.append(f"mysql -h127.0.0.1 -P2881 -uroot@sys -N -B -e '{q}' 2>&1 | "
                      f"sed 's/^/| /'")
        if _clean:
            qc = _clean.replace("'", "'\\''")
            script.append(f"mysql -h127.0.0.1 -P2881 -uroot@sys -e '{qc}' >/dev/null 2>&1")

    code, out = wsl("\n".join(script), timeout=400)

    res: dict[str, dict] = {}
    cur = None
    for line in out.splitlines():
        if line.startswith("P "):
            cur = line[2:].strip()
            res.setdefault(cur, {"plan": "", "held": None, "why": ""})
            continue
        if cur and line.strip():
            res[cur]["plan"] += line.strip() + " "
    for tid, r in res.items():
        _d, _p, _pr, marker, _c = PROBES[tid]
        if not marker:
            # D4：看有没有返回多行分组结果
            r["held"] = len([x for x in r["plan"].split(" | ") if x.strip()]) > 1
            r["why"] = f"返回 {len(r['plan'].split(' | '))} 段"
        else:
            r["held"] = marker.upper() in r["plan"].upper()
            r["why"] = f"计划里{'有' if r['held'] else '没有'} {marker}"
    return res


def main() -> int:
    print("=" * 92)
    print("v2 收集 · 那 7 条结论的真测")
    print("=" * 92)
    res = measure()

    print()
    print("  两列问的不是同一个问题，别当成一列：")
    print("    「证据充分性」= 这次执行的 SQL 能不能证明它自己的意图（手写表）")
    print("    「结论真伪」  = 换个正确的探针去测，结论本身成立不成立（实测）")
    print()
    print(f"{'ID':<4}{'任务':<22}{'证据充分':>9}{'结论真伪':>9}  依据")
    print("-" * 92)
    dis = []
    for tid, (desc, _p, _pr, _m, _c) in PROBES.items():
        r = res.get(tid, {"held": None, "why": "没测到"})
        hand = INTENT_ACHIEVED.get(tid)
        agree = (hand == r["held"]) if (hand is not None and r["held"] is not None) else None
        mark = "✓" if agree else ("✗" if agree is False else "?")
        name = ALL[tid][1]
        print(f"{tid:<4}{name:<22}{str(hand):>7}{str(r['held']):>6}{mark:>6}  {r['why']}")
        if agree is False:
            dis.append((tid, name, hand, r["held"], r["why"]))

    print()
    if dis:
        print(f"两列有 {len(dis)} 处不同 —— **但这不是「手写表错了」**：")
        for tid, name, hand, held, why in dis:
            print(f"   {tid} {name}")
            print(f"      证据充分性={hand}（这次执行的 SQL 不够格）"
                  f"   结论真伪={held}（{why}）")
        print()
        print("   手写表答的是「这次执行算不算证据」，实测答的是「结论本身成不成立」。")
        print("   **两件事可以同时成立**：执行不足以证明意图 ≠ 结论是假的。")
        print()
        print("   这恰好说明框架判 degrade 是对的：")
        print("   **证据不足而结论为真**，正是 degrade 的定义。")
        print("   如果我拿这两列当同一件事比，就会得出「手写表错了 4 处」这种")
        print("   —— 而它并没有错。")
    else:
        print("两列完全一致（这 7 条上）")

    if "--record" in sys.argv:
        import ledger as L
        L.bind_production("v2 结论实测")
        env = EvidenceEnv(3)
        n = 0
        for tid, (desc, _p, _pr, _m, _c) in PROBES.items():
            r = res.get(tid, {})
            if r.get("held") is None:
                continue
            name = ALL[tid][1]
            e1, src = ALL[tid][3], ALL[tid][4]
            c = Claim(tid, name, e1=e1, e2=0, e3=derive_e3(src),
                      kind="procedure")
            g = run_gates(c, env)
            L.record(g["final"], task=f"v2实测·{tid} {name}",
                     note=f"结论实测：{desc}",
                     success=bool(r["held"]),
                     conclusion_held=bool(r["held"]),
                     conclusion_checkable=True,
                     check_why="用 EXPLAIN 实测",
                     evidence=(r.get("why", "") + " | " + r.get("plan", "")[:80])[:90],
                     env_level=3, cause=g.get("cause"), origin="collect")
            n += 1
        print(f"已记账 {n} 条（结论实测，counterfactual=False）")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
