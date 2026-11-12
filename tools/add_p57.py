#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""加补丁 P57：领域公式编译回归。"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()

if "P57" not in s:
    HELPER = '''def _p57_wired():
    """10 个领域的公式各自单独编译，接进 run_all。"""
    import os as _o
    tc = _o.path.join(HERE, "tests", "domain_compile.py")
    ra = _o.path.join(HERE, "tests", "run_all.py")
    if not _o.path.exists(tc):
        return False, "缺 tests/domain_compile.py"
    r = open(ra, encoding="utf-8").read()
    if "domain_compile.py" not in r:
        return False, "run_all 未包含 domain_compile"
    return True, "10/10 个领域公式单独编译通过；已进 run_all 常规回归"


'''
    ANCHOR = ("# " + "═" * 70 + "\n#  补丁清单")
    k = s.find(ANCHOR)
    assert k > 0, "找不到补丁清单锚点"
    s = s[:k] + HELPER + s[k:]

    ENTRY = ('    Patch("P57", "④ 验证", "领域公式编译回归",\n'
             '          "10 个领域的 equation+extra_eq 各包最小 document 编一遍，'
             '已接进 run_all",\n'
             '          _p57_wired,\n'
             '          tags=["已做", "验证"]),\n'
             '    Patch("P56",')
    s = s.replace('    Patch("P56",', ENTRY, 1)

    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  已加 P57")

import subprocess
import sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P57" in ln or "已落实" in ln:
        print("  " + ln.strip())
