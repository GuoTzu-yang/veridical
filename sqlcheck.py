#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQL 前置检查：不问"步骤清不清楚"，问"现在做得了吗"

predict_check.py 跑出 50% 命中率，误判全部是「判 pass，实际失败」：
  查不存在的表 / 语法错 / 向量维度不匹配 / 引用了不存在的列

这四件事**不需要执行就能知道**。所以评估阶段就该查，而不是等跑完才发现。

对应到判据里：这是 procedure 类的 input_valid —— 关键输入无效，一票否决。

跑法：python sqlcheck.py
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile

DISTRO = "Ubuntu-22.04"
TMP_WSL = "/mnt/c/Users/21246/AppData/Local/Temp"
DB = "bench_l3"

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_VEC_LIT = re.compile(r"'\[([0-9.,\-\s]*)\]'")


def _wsl_mysql(sql: str, db: str = DB, timeout: int = 25) -> tuple[int, str]:
    """在 WSL 里跑一条 mysql 命令，返回 (退出码, 合并输出)。"""
    script = (
        "set -u\n"
        "systemctl start seekdb >/dev/null 2>&1\n"
        "for i in $(seq 1 40); do\n"
        "  mysql -h127.0.0.1 -P2881 -uroot@sys --connect-timeout=2 -e 'select 1' >/dev/null 2>&1 && break\n"
        "  sleep 1\n"
        "done\n"
        f"mysql -h127.0.0.1 -P2881 -uroot@sys {db} -N -B -e {_shq(sql)}\n"
    )
    tmp = os.path.join(tempfile.gettempdir(), "sqlcheck_run.sh")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(script)
    env = dict(os.environ)
    env["WSL_UTF8"] = "1"
    try:
        r = subprocess.run(["wsl.exe", "-d", DISTRO, "--", "bash",
                            TMP_WSL + "/sqlcheck_run.sh"],
                           capture_output=True, timeout=timeout, env=env)
    except Exception as e:
        return 1, f"wsl error: {e}"
    out = (r.stdout or b"").decode("utf-8", "replace") + (r.stderr or b"").decode("utf-8", "replace")
    return r.returncode, out.strip()


def _shq(s: str) -> str:
    """把字符串安全地塞进单引号里给 bash 用。"""
    return "'" + s.replace("'", "'\\''") + "'"


def _tables() -> set[str]:
    code, out = _wsl_mysql(
        "SELECT table_name FROM information_schema.tables "
        f"WHERE table_schema='{DB}'")
    return {x.strip().lower() for x in out.splitlines() if x.strip()} if code == 0 else set()


def _columns(table: str) -> dict[str, str]:
    code, out = _wsl_mysql(
        "SELECT column_name, column_type FROM information_schema.columns "
        f"WHERE table_schema='{DB}' AND table_name='{table}'")
    cols = {}
    if code == 0:
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                cols[parts[0].strip().lower()] = parts[1].strip().lower()
    return cols


def _indexed_columns(table: str) -> dict[str, str]:
    """表上真正有索引的列 → 列类型。

    「机制适用性」只对有索引的列才有意义——没索引时走全表扫描是合理的，
    不是「机制不适用」。所以这里查真实的索引清单，不硬编码列名。
    """
    code, out = _wsl_mysql(
        "SELECT DISTINCT s.column_name, c.column_type "
        "FROM information_schema.statistics s "
        "JOIN information_schema.columns c "
        "  ON c.table_schema = s.table_schema AND c.table_name = s.table_name "
        " AND c.column_name = s.column_name "
        f"WHERE s.table_schema='{DB}' AND s.table_name='{table}'")
    cols: dict[str, str] = {}
    if code == 0:
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                cols[parts[0].strip().lower()] = parts[1].strip().lower()
    return cols


def precheck(sql: str, known_tables: set[str] | None = None) -> tuple[bool, str]:
    """在**执行之前**判断这条 SQL 现在做得了吗。

    返回 (ok, reason)。ok=False 对应 input_valid=False，一票否决。
    """
    s = sql.strip()
    low = s.lower()

    # --- 1. 语法残缺：明显不完整 ---
    if re.search(r"\bfrom\s*$", low) or re.search(r"\bselect\s*$", low):
        return False, "语法残缺（FROM/SELECT 后面没东西）"
    if low.count("(") != low.count(")"):
        return False, "括号不配对"

    tables = known_tables if known_tables is not None else _tables()

    # --- 2. 引用的表是否存在 ---
    m = re.search(r"\bfrom\s+([A-Za-z_][A-Za-z0-9_.]*)", low)
    if m:
        t = m.group(1).split(".")[-1]
        if t not in ("dual",) and t not in tables:
            return False, f"表 {t} 不存在"

    m = re.search(r"\binto\s+([A-Za-z_][A-Za-z0-9_.]*)", low)
    if m:
        t = m.group(1).split(".")[-1]
        if t not in tables:
            return False, f"表 {t} 不存在"

    # --- 3. 引用的列是否存在（只对已知表做，避免误伤）---
    m = re.search(r"\bfrom\s+([A-Za-z_][A-Za-z0-9_.]*)", low)
    if m:
        t = m.group(1).split(".")[-1]
        if t in tables:
            cols = _columns(t)
            if cols:
                sel = re.search(r"\bselect\b(.*?)\bfrom\b", low, re.S)
                if sel:
                    proj = sel.group(1)
                    if "*" not in proj and "(" not in proj:
                        for name in _IDENT.findall(proj):
                            n = name.lower()
                            if n in ("as", "distinct"):
                                continue
                            if n not in cols:
                                return False, f"列 {n} 在 {t} 中不存在"

    # --- 4. 向量维度匹配 ---
    literals = _VEC_LIT.findall(s)
    if literals:
        for lit in literals:
            dim = len([x for x in lit.split(",") if x.strip()])
            # 找列声明里的 VECTOR(n)
            mcol = re.search(r"vector\(\s*(\d+)\s*\)", low)
            if mcol:
                want = int(mcol.group(1))
                if dim != want:
                    return False, f"向量维度 {dim} 与声明 VECTOR({want}) 不符"
            else:
                for t in tables:
                    for cname, ctype in _columns(t).items():
                        mc = re.search(r"vector\((\d+)\)", ctype)
                        if mc and cname != "":
                            # 只在插入目标表上比
                            mtarget = re.search(r"\binto\s+([A-Za-z_][A-Za-z0-9_.]*)", low)
                            if mtarget and mtarget.group(1).split(".")[-1] == t:
                                if dim != int(mc.group(1)):
                                    return False, f"向量维度 {dim} 与 {t}.{cname} VECTOR({mc.group(1)}) 不符"

    # --- 5. SELECT 用 EXPLAIN 兜底（能抓语法错）---
    if low.startswith("select"):
        code, out = _wsl_mysql("EXPLAIN " + s)
        if code != 0 and out:
            first = out.splitlines()[0][:80]
            return False, f"EXPLAIN 失败：{first}"

    return True, "前置检查通过"


CASES = [
    ("P1", "建普通表",      "CREATE TABLE IF NOT EXISTS bench_l3.t_p1(a INT)"),
    ("P2", "建带向量表",     "CREATE TABLE IF NOT EXISTS bench_l3.t_p2(a INT, b VECTOR(3))"),
    ("P3", "插入合法行",     "INSERT INTO bench_l3.t_p1 VALUES (4)"),
    ("P4", "LIMIT 0 查询",  "SELECT * FROM bench_l3.t_p1 LIMIT 0"),
    ("Q1", "查不存在的表",   "SELECT * FROM bench_l3.no_such_table"),
    ("Q2", "语法错误",      "SELECT bad_syntax FROM"),
    ("Q3", "向量维度不匹配",  "INSERT INTO bench_l3.t_p2 VALUES (2, '[1,2]')"),
    ("Q4", "引用不存在的列",  "SELECT no_such_col FROM bench_l3.t_p1"),
]

EXPECT = {"P1": True, "P2": True, "P3": True, "P4": True,
          "Q1": False, "Q2": False, "Q3": False, "Q4": False}


def main() -> int:
    print("=" * 78)
    print("SQL 前置检查 · 执行之前判断「现在做得了吗」")
    print("=" * 78)
    tables = _tables()
    print(f"当前 {DB} 里的表: {sorted(tables) or '（空）'}\n")

    print(f"  {'ID':<4}{'任务':<14}{'应否可行':>9}{'检查结论':>9}   理由")
    print("  " + "-" * 66)
    hit = 0
    for tid, name, sql in CASES:
        ok, why = precheck(sql, tables)
        want = EXPECT[tid]
        correct = ok == want
        hit += 1 if correct else 0
        print(f"  {tid:<4}{name:<14}{('可行' if want else '不可行'):>9}"
              f"{('可行' if ok else '不可行'):>9}   {'✓' if correct else '✗'} {why}")

    print()
    print("=" * 78)
    print(f"前置检查准确率: {hit}/{len(CASES)} = {hit/len(CASES)*100:.0f}%")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
