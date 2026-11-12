#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清掉最后 2 处热沉术语。

1. 响应面结论（1630-1636）：写死「thermal resistance is a plane」，
   这是热沉题的结论，包进 _mech == "full"。
2. 正当简约里的「Curvature, for thermal resistance」（2015）：
   改成「Curvature, for this indicator」—— 论证本身通用，只是名字写死。
"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
L = open(P, encoding="utf-8").read().splitlines(keepends=True)

# ── ① 响应面结论包进门控 ──
a = None
for i, ln in enumerate(L):
    if '"The three panels are the reason a single specification "' in ln:
        a = i
        break
if a is not None:
    # 往前找到 L.append( 那行
    st = a
    while st > 0 and "L.append(" not in L[st]:
        st -= 1
    # 往后找到这段 append 结束（以 ')' 结尾的行）
    en = a
    while en < len(L) and not L[en].rstrip().endswith(")"):
        en += 1
    body = []
    for ln in L[st:en + 1]:
        body.append(ln if ln.strip() == "" else "    " + ln)
    GUARD = ('            # 这一段的具体结论（哪个指标是平面、哪个弯曲）\n'
             '            # 是热沉题的，换题不能照搬。\n'
             '            if _mech == "full":\n')
    L = L[:st] + [GUARD] + body + L[en + 1:]
    print(f"① 响应面结论已门控（{en - st + 1} 行）")

s = "".join(L)

# ── ② Curvature 改成通用措辞 ──
OLD = r'r"  \item \textbf{Curvature, for thermal resistance.} For this "'
NEW = r'r"  \item \textbf{Curvature.} For this "'
if OLD in s:
    s = s.replace(OLD, NEW, 1)
    print("② Curvature 已改成通用措辞")
else:
    print("! ② 锚点未匹配")

ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print(f"  paper.py {len(s.splitlines())} 行")
