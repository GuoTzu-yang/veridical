#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
degrade 的正确度量：结论能不能被推翻

第三十二轮的自评暴露了一个真问题：

    L3 的 degrade 成功率 6/7 = 85.7%，和 pass 的 12/14 = 85.7% **完全相同**。

degrade 宣称「结论带保留」，那它的成功率就该比 pass 低。持平只有一个解释：
**用「任务是否做成」衡量 degrade 是错的**——做成 ≠ 结论对。

这一轮换一个度量：任务做完会产出一个**可证伪的结论**，事后用确定性手段复查
它还成不成立。

任务族全是「加索引让查询更快」这类优化：
  - 谓词选择性高（age=42，约 0.02%）→ 加索引大概率真走索引，结论成立
  - 谓词选择性低（category5 IN (0,1)，约 40%）→ 优化器可能仍选全表扫描，结论被推翻

EXPLAIN 的 OPERATOR 是确定的，所以复查也是确定的——不用墙钟时间。

跑法：
  python collect_degrade.py --dry-run
  python collect_degrade.py
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

DISTRO = "Ubuntu-22.04"
TMP_WSL = "/mnt/c/Users/21246/AppData/Local/Temp"

# (id, 说明, 建索引的列, 索引名, 复查用的查询, 谓词选择性)
TASKS = [
    ("H1", "给 age 建索引让 age=42 更快", "age", "ix_dg_age_eq",
     "SELECT COUNT(*) FROM bench_l3.t_ann WHERE age = 42", "0.02%"),
    ("H2", "给 category5 建索引让 =0 更快", "category5", "ix_dg_c5_eq",
     "SELECT COUNT(*) FROM bench_l3.t_ann WHERE category5 = 0", "20%"),
    ("H3", "给 age 建索引让 age>50 更快", "age", "ix_dg_age_gt",
     "SELECT COUNT(*) FROM bench_l3.t_ann WHERE age > 50", "49%"),
    ("H4", "给 category5 建索引让 IN(0,1) 更快", "category5", "ix_dg_c5_in",
     "SELECT COUNT(*) FROM bench_l3.t_ann WHERE category5 IN (0,1)", "40%"),
    ("H5", "给 age 建索引让 BETWEEN 更快", "age", "ix_dg_age_bt",
     "SELECT COUNT(*) FROM bench_l3.t_ann WHERE age BETWEEN 10 AND 20", "11%"),
    ("H6", "给 category5 建索引让 <=1 更快", "category5", "ix_dg_c5_le",
     "SELECT COUNT(*) FROM bench_l3.t_ann WHERE category5 <= 1", "40%"),
]

# 第二批：让索引**因 SARGable 问题失效**的谓词。
# 第一批 6 条结论全部成立（推翻率 0%），说明「选择性低 → 走全表」这个假设在
# seekdb 上不成立——它有索引就用。第二批换成「加了索引但用不上」的情形：
# 列被表达式包住（SARGable 违反），索引在原理上就用不了，结论必然被推翻。
# 这正是 eqfilter.sql 里 #1538「算术恒等」那一类。
TASKS_B = [
    ("J1", "给 age 建索引让 age+0=42 更快", "age", "ix_dg_s_age_p0",
     "SELECT COUNT(*) FROM bench_l3.t_ann WHERE age + 0 = 42", "算术恒等"),
    ("J2", "给 age 建索引让 age*1=42 更快", "age", "ix_dg_s_age_m1",
     "SELECT COUNT(*) FROM bench_l3.t_ann WHERE age * 1 = 42", "乘恒等"),
    ("J3", "给 category5 建索引让 c5+0=0 更快", "category5", "ix_dg_s_c5_p0",
     "SELECT COUNT(*) FROM bench_l3.t_ann WHERE category5 + 0 = 0", "算术恒等"),
    ("J4", "给 age 建索引让 CAST(age)=42 更快", "age", "ix_dg_s_age_cast",
     "SELECT COUNT(*) FROM bench_l3.t_ann WHERE CAST(age AS SIGNED) = 42", "函数包列"),
    ("J5", "给 age 建索引让 age=42 更快（对照）", "age", "ix_dg_s_age_ok",
     "SELECT COUNT(*) FROM bench_l3.t_ann WHERE age = 42", "无恒等，对照组"),
]

BATCHES = {"a": TASKS, "b": TASKS_B}

# 第三批：阴性对照。
# 和批次 B **完全同一批任务、同一个结论**，只把判据的 e1/e3 调高
#   批次 B：e1=1（方向不唯一）e3=1（指标是估算）→ 判 degrade
#   批次 C：e1=2（方向明确）  e3=2（指标确定）→ 判 pass
# 结论复查口径完全相同。
#
# 这样能隔离出一件事：判据标成 degrade 的那批，结论是不是真的更容易被推翻。
#   两组推翻率一样 → degrade 标签没带来判别力，它只是换个说法
#   degrade 组更高   → 判据抓到了 pass 会漏掉的东西
TASKS_C = [
    ("K1", "给 age 建索引让 age+0=42 更快", "age", "ix_dg_c_age_p0",
     "SELECT COUNT(*) FROM bench_l3.t_ann WHERE age + 0 = 42", "算术恒等"),
    ("K2", "给 age 建索引让 age*1=42 更快", "age", "ix_dg_c_age_m1",
     "SELECT COUNT(*) FROM bench_l3.t_ann WHERE age * 1 = 42", "乘恒等"),
    ("K3", "给 category5 建索引让 c5+0=0 更快", "category5", "ix_dg_c_c5_p0",
     "SELECT COUNT(*) FROM bench_l3.t_ann WHERE category5 + 0 = 0", "算术恒等"),
    ("K4", "给 age 建索引让 CAST(age)=42 更快", "age", "ix_dg_c_age_cast",
     "SELECT COUNT(*) FROM bench_l3.t_ann WHERE CAST(age AS SIGNED) = 42", "函数包列"),
    ("K5", "给 age 建索引让 age=42 更快（对照）", "age", "ix_dg_c_age_ok",
     "SELECT COUNT(*) FROM bench_l3.t_ann WHERE age = 42", "无恒等，对照组"),
]

BATCHES["c"] = TASKS_C

# 每批次的 (e1, e3_source)——阴性对照只改这两个，其余完全一致
BATCH_E = {
    "a": (1, "fullscan_est"),
    "b": (1, "fullscan_est"),
    "c": (2, "measured"),      # 对照组：把判据调高，看它判成 pass
}


def wsl(script: str, timeout: int = 400) -> tuple[int, str]:
    tmp = os.path.join(tempfile.gettempdir(), "dg_run.sh")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(script)
    env = dict(os.environ)
    env["WSL_UTF8"] = "1"
    r = subprocess.run(["wsl.exe", "-d", DISTRO, "--", "bash", TMP_WSL + "/dg_run.sh"],
                       capture_output=True, timeout=timeout, env=env)
    out = (r.stdout or b"").decode("utf-8", "replace") + (r.stderr or b"").decode("utf-8", "replace")
    return r.returncode, out


def parse_operator(text: str) -> str:
    """从 EXPLAIN 输出里取根算子的 OPERATOR 名。"""
    for line in text.splitlines():
        if "|" in line and "SCAN" in line:
            parts = [p.strip() for p in line.strip("|").split("|")]
            if len(parts) >= 3 and parts[0].isdigit():
                return re.sub(r"[└─]+", "", parts[1]).strip()
    return ""


def main() -> int:
    L.bind_production("采集脚本：结论复查")  # 本脚本产出真实证据   # 只有真跑这个脚本才绑定，导入不绑
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
    env = EvidenceEnv(3)

    print("=" * 84)
    print("degrade 结论复查 · 任务做成 ≠ 结论对")
    if dry:
        print("【dry-run】不执行，不写账本")
    print("=" * 84)
    print(f"环境: L{env.level}   批次 {batch.upper()}   任务 {len(tasks)}")

    # ---- 判定（e1=1 方向不唯一；e3=1 指标是估算）----
    print(f"\n  {'ID':<4}{'任务':<30}{'判定':>9}{'成因':>8}")
    print("  " + "-" * 58)
    rows = []
    e1_use, src_use = BATCH_E[batch]
    for tid, name, col, idx, query, sel in tasks:
        c = Claim(tid, name, e1=e1_use, e2=0, e3=derive_e3(src_use), kind="procedure")
        g = run_gates(c, env)
        print(f"  {tid:<4}{name:<30}{g['final']:>9}{(g.get('cause') or '-'):>8}")
        rows.append({"tid": tid, "name": name, "col": col, "idx": idx,
                     "query": query, "sel": sel, "g": g})

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

        # 解析：R 行给执行结果，P..E 之间是 EXPLAIN 输出
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
            # 结论成立 = 真的走了索引（RANGE SCAN 且带索引名）
            held[tid] = ("RANGE" in op) or ("INDEX" in op)
            r["operator"] = op

    # ---- 输出 + 记账 ----
    print(f"\n  {'ID':<4}{'任务':<30}{'实际':>6}{'结论':>8}{'算子':<22}")
    print("  " + "-" * 74)
    n_held = n_over = 0
    for r in rows:
        tid = r["tid"]
        act = actual.get(tid)
        h = held.get(tid)
        if h is True:
            n_held += 1
        elif h is False:
            n_over += 1
        print(f"  {tid:<4}{r['name']:<30}"
              f"{('成' if act else '败' if act is False else '-'):>6}"
              f"{('成立' if h else '被推翻' if h is False else '-'):>8}"
              f"  {detail.get(tid, ''):<20}")

    print()
    print("=" * 84)
    if not dry:
        for r in rows:
            tid = r["tid"]
            if actual.get(tid) is None:
                continue
            L.record(r["g"]["final"], task=f"degrade复查·{tid} {r['name']}",
                     note=f"优化类任务，选择性 {r['sel']}",
                     success=actual[tid],
                     evidence=f"算子={detail.get(tid,'')} 谓词选择性={r['sel']}",
                     env_level=env.level,
                     cause=r["g"].get("cause"),
                     conclusion_held=held.get(tid),
                     group=batch,
                     origin="collect")
        total = n_held + n_over
        print(f"结论复查: 成立 {n_held} / 被推翻 {n_over}  （共 {total}）")
        if total:
            print(f"  推翻率 {n_over/total:.0%}  —— 这才是 degrade 该管的量")
        s = L.stats(env.level, MODEL_VERSION)
        cc = s.get("conclusion_check", {})
        print("\n账本里的结论复查口径：")
        for k, b in sorted(cc.items()):
            print(f"  {k:16s} n={b['n']:<3} 成立={b['verified']:<3} 推翻={b['overturned']:<3} 未复查={b['unchecked']}")
    print("=" * 84)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
