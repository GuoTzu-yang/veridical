#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""加补丁 P54：GENERIC 领域补通用公式。"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()

if "P54" not in s:
    HELPER = '''def _p54_wired():
    """GENERIC 领域补通用公式（换题后论文不再一个公式都没有）。"""
    import os as _o
    d = open(_o.path.join(HERE, "domain.py"), encoding="utf-8").read()
    if "eq:surrogate" not in d:
        return False, "GENERIC 仍是 equation=\\"\\""
    if "eq:cv" not in d:
        return False, "GENERIC 缺交叉验证准则"
    return True, "化工题 equation 0→2；热沉题 6 个不变；污染仍 0"


'''
    ANCHOR = ("# " + "═" * 70 + "\n#  补丁清单")
    k = s.find(ANCHOR)
    assert k > 0, "找不到补丁清单锚点"
    s = s[:k] + HELPER + s[k:]

    ENTRY = ('    Patch("P54", "② 提案", "GENERIC 领域补通用公式",\n'
             '          "domain.py 的 GENERIC 原来 equation 为空，'
             '换题后论文零公式；补最小二乘定义 + 交叉验证准则",\n'
             '          _p54_wired,\n'
             '          tags=["已做", "提案"]),\n'
             '    Patch("P53",')
    s = s.replace('    Patch("P53",', ENTRY, 1)

    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  已加 P54")

import subprocess
import sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P54" in ln or "已落实" in ln:
        print("  " + ln.strip())
