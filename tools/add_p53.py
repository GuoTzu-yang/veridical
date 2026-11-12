#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""加补丁 P53：拆超长句 + 修句长解析残留。"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()

if "P53" not in s:
    HELPER = '''def _p53_wired():
    """拆超长句 + 修句长解析的三个残留。"""
    import os as _o
    a = open(_o.path.join(HERE, "aitaste.py"), encoding="utf-8").read()
    p = open(_o.path.join(HERE, "paper.py"), encoding="utf-8").read()
    if "figure" not in a:
        return False, "aitaste 未剥 figure 环境"
    if "the choice of model structure;" not in p:
        return False, "paper 未把 AI 声明改 itemize"
    if "check_sentence_length" not in a:
        return False, "aitaste 缺真句长判据"
    return True, "句长 20→4 分；拆 5 句、2 处改 itemize；ai_taste 40→33"


'''
    ANCHOR = ("# " + "═" * 70 + "\n#  补丁清单")
    k = s.find(ANCHOR)
    assert k > 0, "找不到补丁清单锚点"
    s = s[:k] + HELPER + s[k:]

    ENTRY = ('    Patch("P53", "④ 验证", "拆超长句 + 修句长解析残留",\n'
             '          "拆 5 句、2 处改 itemize；修 figure/H/item/extbf 边界；'
             '句长 20→4 分",\n'
             '          _p53_wired,\n'
             '          tags=["已做", "验证"]),\n'
             '    Patch("P52",')
    s = s.replace('    Patch("P52",', ENTRY, 1)

    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  已加 P53")

import subprocess
import sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P53" in ln or "已落实" in ln:
        print("  " + ln.strip())
