#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""加补丁 P66：gate 新增 chk_claims。"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()

if "P66" not in s:
    HELPER = '''def _p66_wired():
    """gate 检查「声明-证据」节：0 条无支撑要 WARN。"""
    import os as _o
    g = open(_o.path.join(HERE, "gate.py"), encoding="utf-8").read()
    miss = []
    if "def chk_claims" not in g:
        miss.append("缺 chk_claims")
    if "chk_claims(figdir)" not in g:
        miss.append("未进 checks 列表")
    if '"claims": "decay"' not in g:
        miss.append("未归入衰减项")
    if miss:
        return False, "; ".join(miss)
    return True, ("三态实测：缺节→FAIL；0 条无支撑→WARN"
                  "（「要么真的完整，要么没逐条查」）；正常→PASS 2/3")


'''
    ANCHOR = ("# " + "═" * 70 + "\n#  补丁清单")
    k = s.find(ANCHOR)
    assert k > 0, "找不到补丁清单锚点"
    s = s[:k] + HELPER + s[k:]

    ENTRY = ('    Patch("P66", "④ 验证", "gate 检查声明-证据节",\n'
             '          "缺节→FAIL；0 条无支撑→WARN（声称全有证据比承认不足更可疑）"\n'
             '          "；归入衰减项",\n'
             '          _p66_wired,\n'
             '          tags=["已做", "验证"]),\n'
             '    Patch("P65",')
    s = s.replace('    Patch("P65",', ENTRY, 1)

    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  已加 P66")

import subprocess
import sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P66" in ln or "已落实" in ln:
        print("  " + ln.strip())
