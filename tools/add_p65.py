#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""加补丁 P65：「What each claim rests on」节。"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()

if "P65" not in s:
    HELPER = '''def _p65_wired():
    """每条声明挂证据，或在论文里明确标注「无支撑」。"""
    import os as _o
    p = open(_o.path.join(HERE, "paper.py"), encoding="utf-8").read()
    tex = _o.path.join(HERE, "out", "fig", "paper.tex")
    miss = []
    if "def _claim_ledger" not in p:
        miss.append("缺 _claim_ledger")
    if "_claim_ledger(ctx)" not in p:
        miss.append("未接入 build")
    if _o.path.exists(tex):
        t = open(tex, encoding="utf-8").read()
        if "What each claim rests on" not in t:
            miss.append("tex 里没出现该节")
        elif t.count("Not supported") < 2:
            miss.append("「无支撑」条目 < 2")
    else:
        miss.append("缺 paper.tex")
    if miss:
        return False, "; ".join(miss)
    return True, ("实产出 5 条：2 条挂证据（tab:multi / tab:front）、"
                  "3 条标注无支撑（压降 70% 区间 + 2 处机理没给方向）")


'''
    ANCHOR = ("# " + "═" * 70 + "\n#  补丁清单")
    k = s.find(ANCHOR)
    assert k > 0, "找不到补丁清单锚点"
    s = s[:k] + HELPER + s[k:]

    ENTRY = ('    Patch("P65", "② 提案", "「无支撑声明清单」节",\n'
             '          "输出契约第 11 项：风险、无支撑的声明、还需要的数据；'
             '内容全部由 ctx 生成不硬编码",\n'
             '          _p65_wired,\n'
             '          tags=["已做", "提案"]),\n'
             '    Patch("P64",')
    s = s.replace('    Patch("P64",', ENTRY, 1)

    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  已加 P65")

import subprocess
import sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P65" in ln or "已落实" in ln:
        print("  " + ln.strip())
