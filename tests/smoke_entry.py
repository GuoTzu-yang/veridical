#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对外入口冒烟：judge 在 file 域跑通 + --record 的账本隔离

上一轮只测了 judge 读静态 SQL 任务。这条补两件：
  1. `verify` 按 domain 分发到 file 域（file/file 不存在/目录 三种）
  2. `--record` 写到临时账本，正式账本一条不动

为什么要单独测 --record：它是唯一会改账本的入口，
不隔离就测等于拿正式账本做实验（这个坑已经踩过五次）。

跑法：python tests/smoke_entry.py
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable


def run_judge(task_path: str, extra: list[str], env_extra: dict | None = None):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    if env_extra:
        env.update(env_extra)
    p = subprocess.run([PY, os.path.join(ROOT, "extend.py"), "judge", task_path] + extra,
                       capture_output=True, cwd=ROOT, timeout=300, env=env)
    out = (p.stdout or b"").decode("utf-8", "replace") + \
          (p.stderr or b"").decode("utf-8", "replace")
    return p.returncode, out


def ledger_lines(path: str) -> int:
    if not os.path.exists(path):
        return 0
    with io.open(path, encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def main() -> int:
    fails = []

    def check(name, cond, detail=""):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))
        if not cond:
            fails.append(name)

    tmp = tempfile.mkdtemp(prefix="m1_smoke_")
    real = os.path.join(tmp, "real.txt")
    with open(real, "w", encoding="utf-8") as f:
        f.write("x")
    missing = os.path.join(tmp, "missing.txt")

    spec = {
        "name": "file 域三态",
        "relation": "and",
        "claims": [
            {"cid": "F1", "text": "读存在的文件", "e1": 2, "e2": 0, "e3": 2,
             "kind": "procedure",
             "verify": {"domain": "file", "task": {"path": real, "op": "read"}}},
            {"cid": "F2", "text": "读不存在的文件", "e1": 2, "e2": 0, "e3": 2,
             "kind": "procedure",
             "verify": {"domain": "file", "task": {"path": missing, "op": "read"}}},
            {"cid": "F3", "text": "列目录", "e1": 2, "e2": 0, "e3": 2,
             "kind": "procedure",
             "verify": {"domain": "file", "task": {"path": tmp, "op": "dir"}}},
        ],
    }
    task_path = os.path.join(tmp, "task.json")
    with open(task_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False)

    print("=" * 70)
    print("1) judge 在 file 域跑通")
    print("=" * 70)
    code, out = run_judge(task_path, [])
    print("  " + "\n  ".join(out.splitlines()[:14]))
    check("退出码 0", code == 0, str(code))
    check("F1 前置通过", "input_valid=True" in out)
    check("F2 前置失败", "input_valid=False" in out)
    check("报告覆盖率", "覆盖率" in out)
    check("报告最弱一环", "最弱一环" in out)
    check("F1 判 pass", any(("F1" in ln and "pass" in ln) for ln in out.splitlines()))
    check("F2 判 reject", any(("F2" in ln and "reject" in ln) for ln in out.splitlines()))

    print()
    print("=" * 70)
    print("2) --record 只写临时账本")
    print("=" * 70)
    prod = os.path.join(ROOT, "ledger.jsonl")
    prod_before = ledger_lines(prod)
    tmpledger = os.path.join(tmp, "ledger.jsonl")

    code2, out2 = run_judge(task_path, ["--record"],
                            {"MODEL1_LEDGER": tmpledger})
    prod_after = ledger_lines(prod)
    tmp_after = ledger_lines(tmpledger)

    print(f"  正式账本 {prod_before} → {prod_after} 行")
    print(f"  临时账本 0 → {tmp_after} 行")
    check("退出码 0", code2 == 0, str(code2))
    check("临时账本写入了 3 条", tmp_after == 3, str(tmp_after))
    check("正式账本一行没多", prod_after == prod_before,
          f"{prod_before} → {prod_after}")
    check("输出提到已记账", "已记账本" in out2)

    print()
    print("=" * 70)
    print(f"{'ALL PASS' if not fails else 'FAILED: ' + str(fails)}")
    print("=" * 70)
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
