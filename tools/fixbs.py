#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把新插的 }\\% 双写成 }\\\\%（源码两个反斜杠），消除 SyntaxWarning。"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()

BS = chr(92)
NEEDLE = "}" + BS + "%"          # 单反斜杠
REPL = "}" + BS + BS + "%"       # 双反斜杠

out = []
i = 0
n = 0
while i < len(s):
    if s[i:i + 3] == NEEDLE:
        # 已经双写过的跳过（前一个字符是反斜杠）
        prev = s[i - 1] if i > 0 else ""
        if prev != BS:
            out.append(REPL)
            i += 3
            n += 1
            continue
    out.append(s[i])
    i += 1

s2 = "".join(out)
ast.parse(s2)
compile(s2, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s2)
print("  修了 " + str(n) + " 处 单反斜杠 -> 双反斜杠")
