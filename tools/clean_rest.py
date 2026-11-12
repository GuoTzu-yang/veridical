#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清掉最后两类污染：我上一轮加的「影响规律」和「文献综述」。

它们含写死的热沉术语（pin-fin width / manifold depth / thermal resistance），
换一道化工题就全文矛盾。

处理：
  影响规律  → 包进 if _mech == "full"（它本来就是热沉题的影响规律）
  文献综述  → 改成通用表述（去掉 microchannel / manifold 具体例子）
"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
L = open(P, encoding="utf-8").read().splitlines(keepends=True)

# ── ① 影响规律：整段包进 if _mech == "full" ──
a = b = None
for i, ln in enumerate(L):
    if 'L.append(r"\\subsection{The ordering of the factors}")' in ln:
        a = i
    if a is not None and i > a and ln.strip() == "":
        b = i
        break
if a is not None and b is not None:
    body = []
    for ln in L[a:b]:
        body.append(ln if ln.strip() == "" else "    " + ln)
    GUARD = ('    # 影响规律是热沉题专有的（pin-fin width / manifold depth /\n'
             '    # thermal resistance 都是写死的名字），换题必须不输出。\n'
             '    if _mech == "full":\n')
    L = L[:a] + [GUARD] + body + L[b:]
    print(f"① 影响规律已包进 _mech == full（{b - a} 行）")
else:
    print("! ① 定位失败")

s = "".join(L)

# ── ② 文献综述改成通用 ──
OLD = ('        "Previous work on this class of problem falls into three lines. "\n'
       '        "Microchannel heat sinks are established to raise the convective "\n'
       '        "coefficient through boundary-layer disruption, and the pressure "\n'
       '        "penalty of doing so is quantified in the same literature. "\n'
       '        "Manifold-based distribution was proposed to shorten the effective "\n'
       '        "channel length, and its effect on flow uniformity is documented "\n'
       '        "for embedded microchannel cooling. On the statistical side, the "')
NEW = ('        "Previous work on this class of problem falls into three lines. "\n'
       '        "The physical line establishes which structural factors can move "\n'
       '        "each performance indicator, and quantifies the cost that the "\n'
       '        "favourable direction imposes on the other objectives. The "\n'
       '        "design line treats the resulting trade-off as a programme over "\n'
       '        "a feasible set rather than as a search over a scored list. On "\n'
       '        "the statistical side, the "')
if OLD in s:
    s = s.replace(OLD, NEW, 1)
    print("② 文献综述已改成通用")
else:
    print("! ② 文献综述锚点未匹配")

ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print(f"  paper.py {len(s.splitlines())} 行")
