#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""加补丁 P59：重试报告加时间窗口。"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()

if "P59" not in s:
    HELPER = '''def _p59_wired():
    """重试报告加 12 小时时间窗口（旧失败不再永久报「不稳」）。"""
    import os as _o
    r = open(_o.path.join(HERE, "tests", "run_all.py"),
             encoding="utf-8").read()
    if "_WINDOW" not in r:
        return False, "retry_summary 仍无时间窗口"
    if "_now - r.get" not in r:
        return False, "窗口未生效"
    return True, ("日志 append-only 且只 5 条 → 昨天 18:24 的失败 13 小时后"
                  "仍在报；两个脚本实测 15/15 与 ALL PASS")


'''
    ANCHOR = ("# " + "═" * 70 + "\n#  补丁清单")
    k = s.find(ANCHOR)
    assert k > 0, "找不到补丁清单锚点"
    s = s[:k] + HELPER + s[k:]

    ENTRY = ('    Patch("P59", "④ 验证", "重试报告加时间窗口",\n'
             '          "append-only 日志凑不满 6 条 → 13 小时前的失败永久报「不稳」；'
             '加 12 小时窗口",\n'
             '          _p59_wired,\n'
             '          tags=["已做", "验证"]),\n'
             '    Patch("P58",')
    s = s.replace('    Patch("P58",', ENTRY, 1)

    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  已加 P59")

import subprocess
import sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P59" in ln or "已落实" in ln:
        print("  " + ln.strip())
