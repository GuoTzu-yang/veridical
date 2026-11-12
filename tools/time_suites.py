#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给每个回归套件计时，找出真正慢的。

用法：python tools/time_suites.py [--top N]

路径解析必须与 run_all.run() 完全一致：
    CORE        → <ROOT>/<script>
    SUITE/ENTRY → <TESTS>/<script>

第一版没照这个来，而是"先找 tests/ 再找根目录"，
结果 `probe.py` 跑的是 tests/probe.py（另一个脚本），
耗时归属整个错位（报 39.2s，真值是 0.22s）。
测量脚本本身也要先被验证。
"""
from __future__ import annotations

import io
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TESTS = os.path.join(ROOT, "tests")
PY = sys.executable


def _args_of(el):
    """取出套件的参数列表。

    CORE/SUITE 里是字面量列表；ENTRY 里是 os.path.join(TESTS, "x.json")
    这种调用，得从它的第二个实参里取文件名。
    """
    import ast
    node = el.elts[1]
    if isinstance(node, ast.List):
        return [e.value for e in node.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    if isinstance(node, ast.Call):
        for a in node.args[1:]:
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                return [a.value]
    return []


def suites():
    """从 run_all.py 读出 CORE/SUITE/ENTRY，保持单一来源。

    返回 [(script, args, 基准目录, 分组名)]。
    """
    import ast
    src = open(os.path.join(TESTS, "run_all.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    base = {"CORE": ROOT, "SUITE": TESTS, "ENTRY": TESTS}
    out = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        name = getattr(node.targets[0], "id", "")
        if name not in base:
            continue
        for el in node.value.elts:
            out.append((el.elts[0].value, _args_of(el), base[name], name))
    return out


def main() -> int:
    top = 15
    if "--top" in sys.argv:
        top = int(sys.argv[sys.argv.index("--top") + 1])

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    rows = []
    total = 0.0
    for name, args, cwd, group in suites():
        script = os.path.join(cwd, name)
        if not os.path.exists(script):
            rows.append((0.0, name, "缺文件", False, group))
            continue
        t0 = time.perf_counter()
        try:
            r = subprocess.run([PY, script] + args, capture_output=True,
                               cwd=ROOT, env=env, timeout=900, input="")
            el = time.perf_counter() - t0
            code = r.returncode
        except subprocess.TimeoutExpired:
            el = time.perf_counter() - t0
            code = "超时"
        total += el
        rows.append((el, name, code, code == 0, group))

    rows.sort(key=lambda r: -r[0])
    print(f"总计 {len(rows)} 个套件，耗时 {total:.1f}s")
    print()
    print(f"  {'耗时':>8}  {'分组':<6} {'退出':>6}  套件")
    for el, name, code, good, group in rows[:top]:
        flag = "" if good else "  ← 非零退出"
        print(f"  {el:>7.2f}s  {group:<6} {str(code):>6}  {name}{flag}")
    if len(rows) > top:
        print(f"  ... 其余 {len(rows) - top} 个")
    slow = [r for r in rows if r[0] > 5.0]
    print()
    print(f"超过 5 秒的：{len(slow)} 个，合计 {sum(r[0] for r in slow):.1f}s"
          f"（占总时间 {sum(r[0] for r in slow) / total * 100:.0f}%）")
    # ENTRY 只看退出码不够 —— run_all 还查输出里必须出现的字串，
    # 所以 ENTRY 非零退出不一定是真失败，单独标出来避免误判。
    failed = [r for r in rows if not r[3] and r[4] != "ENTRY"]
    entry_bad = [r for r in rows if not r[3] and r[4] == "ENTRY"]
    if failed:
        print(f"真失败：{len(failed)} 个 —— {[r[1] for r in failed]}")
    if entry_bad:
        print(f"ENTRY 非零退出（run_all 另查输出字串，未必是失败）："
              f"{[r[1] for r in entry_bad]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
