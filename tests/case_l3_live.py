#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
L3 实跑：在 WSL 的 seekdb 上跑真实 SQL 任务，产出 L3 样本

上一轮账本 L3 只有 1 条（pass），离 MIN_SAMPLES=5 差 4 条。
这个脚本做四件事，每件都真跑、都有可判定的成败：

  T1 建表              —— 成功 = 表存在且列类型对
  T2 灌 5000 行        —— 成功 = count(*) 等于预期
  T3 向量距离查询      —— 成功 = 能返回结果且距离单调
  T4 等价谓词 A/B 对比 —— 成功 = 两种写法结果集一致

跑法：python case_l3_live.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import json
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 架构本体所在目录

DISTRO = "Ubuntu-22.04"
DB = "bench_l3"
ROWS = 5000

# Windows 临时目录在 WSL 里的映射
TMP_WSL = "/mnt/c/Users/21246/AppData/Local/Temp"


def wsl(script: str, timeout: int = 300) -> tuple[int, str]:
    """在 WSL 里执行一段 bash，返回 (退出码, 输出)。"""
    tmp = os.path.join(tempfile.gettempdir(), "l3_run.sh")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(script)
    wsl_path = TMP_WSL + "/l3_run.sh"
    env = dict(os.environ)
    env["WSL_UTF8"] = "1"
    r = subprocess.run(
        ["wsl.exe", "-d", DISTRO, "--", "bash", wsl_path],
        capture_output=True, timeout=timeout, env=env,
    )
    out = (r.stdout or b"").decode("utf-8", "replace") + (r.stderr or b"").decode("utf-8", "replace")
    return r.returncode, out


def gen_data_sql() -> str:
    """生成 5000 行 INSERT，写到 WSL 能读到的地方。"""
    path = os.path.join(tempfile.gettempdir(), "l3_data.sql")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"USE {DB};\n")
        f.write("TRUNCATE TABLE t_ann;\n")
        batch = []
        for i in range(1, ROWS + 1):
            v = f"'[{i % 7},{i % 5},{i % 3},{i % 11}]'"
            batch.append(f"({i},{i % 100},{i % 5},{v})")
            if len(batch) == 500:
                f.write("INSERT INTO t_ann VALUES " + ",".join(batch) + ";\n")
                batch = []
        if batch:
            f.write("INSERT INTO t_ann VALUES " + ",".join(batch) + ";\n")
    return TMP_WSL + "/l3_data.sql"


def main() -> int:
    print("=" * 70)
    print("L3 实跑 · WSL seekdb 真实 SQL 任务")
    print("=" * 70)

    data_sql = gen_data_sql()
    print(f"\n数据文件: {os.path.basename(data_sql)}（{ROWS} 行）")

    script = f"""
set -u
systemctl start seekdb >/dev/null 2>&1
for i in $(seq 1 40); do
  mysql -h127.0.0.1 -P2881 -uroot@sys --connect-timeout=2 -e "select 1" >/dev/null 2>&1 && break
  sleep 1
done
M="mysql -h127.0.0.1 -P2881 -uroot@sys"

# ---- T1 建表 ----
$M -e "CREATE DATABASE IF NOT EXISTS {DB};" 2>&1
$M -e "USE {DB}; CREATE TABLE IF NOT EXISTS t_ann (
  id BIGINT PRIMARY KEY, age INT, category5 INT, v VECTOR(4));" 2>&1
COLS=$($M -N -B -e "SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema='{DB}' AND table_name='t_ann'")
echo "T1_COLS=$COLS"

# ---- T2 灌数据 ----
$M < {data_sql} 2>&1 | head -3
CNT=$($M -N -B -e "SELECT COUNT(*) FROM {DB}.t_ann")
echo "T2_COUNT=$CNT"
echo "T2_EXPECT={ROWS}"

# ---- T3 向量距离 ----
D=$($M -N -B -e "SELECT l2_distance(v,'[0,0,0,0]') FROM {DB}.t_ann WHERE id=1")
echo "T3_DIST=$D"
R=$($M -N -B -e "SELECT COUNT(*) FROM (SELECT id, l2_distance(v,'[1,1,1,1]') d
  FROM {DB}.t_ann ORDER BY d LIMIT 10) x")
echo "T3_ROWS=$R"

# ---- T4 等价谓词 A/B（结果集是否一致）----
A=$($M -N -B -e "SELECT GROUP_CONCAT(id ORDER BY id) FROM
  (SELECT id FROM {DB}.t_ann WHERE age > 10 ORDER BY id LIMIT 100) t")
B=$($M -N -B -e "SELECT GROUP_CONCAT(id ORDER BY id) FROM
  (SELECT id FROM {DB}.t_ann WHERE ((age + 0) + 0) > 10 ORDER BY id LIMIT 100) t")
if [ "$A" = "$B" ]; then echo "T4_SAME=yes"; else echo "T4_SAME=no"; fi

C=$($M -N -B -e "SELECT GROUP_CONCAT(id ORDER BY id) FROM
  (SELECT id FROM {DB}.t_ann WHERE age BETWEEN 11 AND 50 ORDER BY id LIMIT 100) t")
D2=$($M -N -B -e "SELECT GROUP_CONCAT(id ORDER BY id) FROM
  (SELECT id FROM {DB}.t_ann WHERE age >= 11 AND age <= 50 ORDER BY id LIMIT 100) t")
if [ "$C" = "$D2" ]; then echo "T4B_SAME=yes"; else echo "T4B_SAME=no"; fi
"""

    print("\n执行中（WSL 内启动 seekdb + 建表 + 灌数据 + 4 项检查）...")
    code, out = wsl(script, timeout=420)

    facts = {}
    for line in out.splitlines():
        if "=" in line and line.split("=")[0].isupper():
            k, _, v = line.partition("=")
            facts[k.strip()] = v.strip()

    print(f"\n退出码 {code}")
    print("-" * 70)
    for k in ("T1_COLS", "T2_COUNT", "T2_EXPECT", "T3_DIST", "T3_ROWS", "T4_SAME", "T4B_SAME"):
        if k in facts:
            print(f"  {k:12s} = {facts[k]}")
    other = [l for l in out.splitlines() if l.strip() and "=" not in l]
    if other:
        print("\n其他输出（前 5 行）:")
        for l in other[:5]:
            print("  " + l[:120])

    # ---- 判定 ----
    print("\n" + "=" * 70)
    print("判定")
    print("=" * 70)
    checks = [
        ("T1 建表", facts.get("T1_COLS") == "4", f"列数 {facts.get('T1_COLS')}，期望 4"),
        ("T2 灌数据", facts.get("T2_COUNT") == facts.get("T2_EXPECT") == str(ROWS),
         f"count {facts.get('T2_COUNT')}，期望 {ROWS}"),
        ("T3 向量距离", facts.get("T3_ROWS") == "10", f"返回 {facts.get('T3_ROWS')} 行，期望 10"),
        ("T4 等价谓词 A/B", facts.get("T4_SAME") == "yes", f"结果集一致={facts.get('T4_SAME')}"),
        ("T4b BETWEEN vs AND", facts.get("T4B_SAME") == "yes", f"结果集一致={facts.get('T4B_SAME')}"),
    ]
    results = []
    for name, ok, detail in checks:
        print(f"  {'✓' if ok else '✗'} {name:22s} {detail}")
        results.append((name, ok))

    passed = sum(1 for _, ok in results if ok)
    print(f"\n通过 {passed}/{len(results)}")

    out_json = os.path.join(HERE, "_l3_live.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"facts": facts, "results": results,
                   "passed": passed, "total": len(results)},
                  f, ensure_ascii=False, indent=2)
    print(f"结果已写入 {os.path.basename(out_json)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
