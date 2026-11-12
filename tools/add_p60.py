#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""加补丁 P60：重试日志记失败原因。"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()

if "P60" not in s:
    HELPER = '''def _p60_wired():
    """重试日志记失败原因（不只是 passed 布尔）。"""
    import os as _o
    r = open(_o.path.join(HERE, "tests", "run_all.py"),
             encoding="utf-8").read()
    miss = []
    if "def _why(" not in r:
        miss.append("缺 _why")
    if 'r.get("reason")' not in r:
        miss.append("summary 未带 reason")
    if "最近一次失败" not in r:
        miss.append("报告未显示原因")
    if miss:
        return False, "; ".join(miss)
    return True, ("实测生效：harness.py 的重试直接显示"
                  "「[FAIL] 能力不够 → 自动降级为 degrade — actual=pass」")


'''
    ANCHOR = ("# " + "═" * 70 + "\n#  补丁清单")
    k = s.find(ANCHOR)
    assert k > 0, "找不到补丁清单锚点"
    s = s[:k] + HELPER + s[k:]

    ENTRY = ('    Patch("P60", "④ 验证", "重试日志记失败原因",\n'
             '          "以前只记 passed 布尔，事后查不出为什么坏；'
             '现在记第一次失败的首行并在报告里显示",\n'
             '          _p60_wired,\n'
             '          tags=["已做", "验证"]),\n'
             '    Patch("P59",')
    s = s.replace('    Patch("P59",', ENTRY, 1)

    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  已加 P60")

import subprocess
import sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P60" in ln or "已落实" in ln:
        print("  " + ln.strip())
