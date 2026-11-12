#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
探：seekdb 的索引到底对哪些谓词形式失效

第三十四轮发现 `WHERE age + 0 = 42` 用不了索引（走 FULL SCAN），
但 `WHERE CAST(age AS SIGNED) = 42` **居然能用**（走 RANGE SCAN）。

这跟"列被表达式包住就不能用索引"的常识相反。**在设计「机制适用性」这一维
之前，必须先测出真实边界**，否则我又要拍一个错规则。

第三十四轮已经吃过一次亏：以为「选择性低 → 走全表」，实测全错。

跑法：python probe_sargable.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile

DISTRO = "Ubuntu-22.04"
TMP_WSL = "/mnt/c/Users/21246/AppData/Local/Temp"

# (描述, 谓词)
VARIANTS = [
    ("裸列等值",            "age = 42"),
    ("裸列范围",            "age > 50"),
    ("列 + 常数",           "age + 0 = 42"),
    ("列 * 常数",           "age * 1 = 42"),
    ("列 - 常数",           "age - 0 = 42"),
    ("列 + 常数（范围）",      "age + 0 > 40"),
    ("列 * 列",             "age * age = 42"),
    ("CAST AS SIGNED",      "CAST(age AS SIGNED) = 42"),
    ("CAST AS CHAR",        "CAST(age AS CHAR) = '42'"),
    ("函数 ABS",            "ABS(age - 42) = 0"),
    ("函数 YEAR",           "YEAR(age) = 42"),
    ("IN 列表",             "age IN (41,42,43)"),
    ("BETWEEN",             "age BETWEEN 41 AND 43"),
    ("OR 真值",             "age = 42 OR FALSE"),
    ("NOT IN",             "age NOT IN (42)"),
]


def wsl(script: str, timeout: int = 300) -> tuple[int, str]:
    tmp = os.path.join(tempfile.gettempdir(), "probe_sarg.sh")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(script)
    env = dict(os.environ)
    env["WSL_UTF8"] = "1"
    r = subprocess.run(["wsl.exe", "-d", DISTRO, "--", "bash", TMP_WSL + "/probe_sarg.sh"],
                       capture_output=True, timeout=timeout, env=env)
    out = (r.stdout or b"").decode("utf-8", "replace") + (r.stderr or b"").decode("utf-8", "replace")
    return r.returncode, out


def main() -> int:
    print("=" * 76)
    print("探：索引在哪些谓词形式下失效")
    print("=" * 76)

    script = ["set -u",
              "systemctl start seekdb >/dev/null 2>&1",
              "for i in $(seq 1 40); do",
              "  mysql -h127.0.0.1 -P2881 -uroot@sys --connect-timeout=2 -e 'select 1' >/dev/null 2>&1 && break",
              "  sleep 1",
              "done",
              "mysql -h127.0.0.1 -P2881 -uroot@sys -e "
              "'ALTER TABLE bench_l3.t_ann DROP INDEX ix_probe' 2>/dev/null",
              "mysql -h127.0.0.1 -P2881 -uroot@sys -e "
              "'CREATE INDEX ix_probe ON bench_l3.t_ann(age)' 2>/dev/null"]
    for i, (desc, pred) in enumerate(VARIANTS):
        q = f"EXPLAIN SELECT COUNT(*) FROM bench_l3.t_ann WHERE {pred}".replace("'", "'\\''")
        script.append(f"echo \"V {i}\"")
        script.append(f"mysql -h127.0.0.1 -P2881 -uroot@sys bench_l3 -e \"{q}\" 2>&1")
        script.append(f"echo \"W {i}\"")
    code, out = wsl("\n".join(script), timeout=300)

    ops: dict[int, str] = {}
    cur = None
    for line in out.splitlines():
        if line.startswith("V "):
            cur = int(line[2:].strip())
        elif line.startswith("W "):
            cur = None
        elif cur is not None and "|" in line and "SCAN" in line:
            parts = [p.strip() for p in line.strip("|").split("|")]
            if len(parts) >= 3 and parts[0].isdigit():
                op = re.sub(r"[└─]+", "", parts[1]).strip()
                if "SCAN" in op:
                    ops[cur] = op
                    cur = None

    print(f"\n  {'描述':<22}{'谓词':<28}{'算子':<20}索引用上了?")
    print("  " + "-" * 84)
    used = notused = 0
    for i, (desc, pred) in enumerate(VARIANTS):
        op = ops.get(i, "(无计划)")
        hit = "RANGE" in op or "INDEX" in op
        used += 1 if hit else 0
        notused += 0 if hit else 1
        print(f"  {desc:<22}{pred:<28}{op:<20}{'✓ 用上' if hit else '✗ 用不上'}")
    print()
    print(f"  用得上 {used} / 用不上 {notused}")
    print()
    print("  规则候选：")
    print("    「列被算术运算包住 → 用不上」")
    print("    「列被函数包住 → ？？」（CAST 竟然能用，需更多数据）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
