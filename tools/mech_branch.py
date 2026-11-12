#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""机理节按题型分支：热沉专用区间（三小节 + Why these three indicators）
只在 _mech == "full" 时输出，否则输出通用的「方向级」版。

区间定位（实测）：
    1018  L.append(r"\\subsection{Thermal resistance}")
    1103  L.append("")                      ← 三指标小节之后
"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
L = open(P, encoding="utf-8").read().splitlines(keepends=True)

# 定位热沉专用区间的起止
a = None
b = None
for i, ln in enumerate(L):
    if a is None and 'L.append(r"\\subsection{Thermal resistance}")' in ln:
        a = i
    if a is not None and 'L.append(r"\\subsection{' in ln and \
            "Why these three indicators" in ln:
        # 从这个小节找到它结束（连续的 L.append 之后遇到的空行）
        j = i
        while j < len(L) and not L[j].strip() == "":
            j += 1
        b = j
        break

assert a is not None and b is not None, f"定位失败 a={a} b={b}"
print(f"  热沉专用区间：{a + 1} - {b} 行（{b - a} 行）")

if "_mech == \"full\"" in "".join(L):
    print("  已经改造过，跳过")
    raise SystemExit(0)

# 给区间每行加 4 空格（保留空行原样）
body = []
for ln in L[a:b]:
    if ln.strip() == "":
        body.append(ln)
    else:
        body.append("    " + ln)

GUARD = ('    # ── 以下三小节与「Why these three indicators」是本题（热沉）专用的 ──\n'
         '    # 它们含 R_th/Nu、thermal/cost/durability 三轴等具体内容，\n'
         '    # 换一道题会变成污染（实测化工题里出现 33 处热沉术语）。\n'
         '    # 所以只在识别为机理工题（mechanism_needed=True）或显式 --mechanism full 时输出。\n'
         '    if _mech == "full":\n')

BRIEF = (
    '    else:\n'
    '        # brief 版：保留「守恒律给方向 + 数据检验方向」这个论证骨架，\n'
    '        # 去掉具体公式与题目专有名词。这版对任何题都成立。\n'
    '        L.append(r"\\subsection{What the conservation laws fix}")\n'
    '        L.append(\n'
    '            "The indicators enter through conservation of energy and "\n'
    '            "momentum, and those laws fix the direction in which each "\n'
    '            "structural factor should move them. The directions are "\n'
    '            "testable, and they are tested below rather than asserted.")\n'
    '        L.append("")\n'
    '        L.append(\n'
    '            "No closed-form mechanism is carried into the model itself. "\n'
    '            "The functional form is chosen by cross-validated error, and "\n'
    '            "the conservation laws supply only the signs that the data "\n'
    '            "then confirm or contradict. This is deliberate: a mechanism "\n'
    '            "that fixes directions is testable, while one that also fixes "\n'
    '            "coefficients would need a calibration this sample cannot "\n'
    '            "supply, and asserting it would make the two roles "\n'
    '            "indistinguishable.")\n'
    '        L.append("")\n'
)

L2 = L[:a] + [GUARD] + body + [BRIEF] + L[b:]
s = "".join(L2)
ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print(f"  已改造，paper.py {len(s.splitlines())} 行")
