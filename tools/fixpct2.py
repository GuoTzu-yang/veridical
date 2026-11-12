#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量修 paper.py 里所有 `:.N%` 格式符（LaTeX 里 % 是注释符）。

gate 新加的 bare_pct 抓到 9 处。共同点：Python 的 % 格式符输出裸 %，
LaTeX 把同一行后面全部注释掉，于是「半句话消失」而编译不报错。
"""
import ast
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()

hits = list(re.finditer(r"\{([^{}]+?):([+\- ]?)(?:\.(\d))?%\}", s))
print("  找到 " + str(len(hits)) + " 处 % 格式符")
for m in hits[:16]:
    ln = s[:m.start()].count("\n") + 1
    print("    L" + str(ln) + "  " + m.group(0)[:52])


def repl(m):
    expr = m.group(1)
    sign = m.group(2) or ""
    dec = m.group(3) if m.group(3) is not None else "0"
    return "{" + expr + " * 100:" + sign + "." + dec + "f}" + chr(92) + "%"


s2 = re.sub(r"\{([^{}]+?):([+\- ]?)(?:\.(\d))?%\}", repl, s)
ast.parse(s2)
compile(s2, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s2)
print("  已替换 " + str(len(hits)) + " 处")

import subprocess
import sys
r = subprocess.run([sys.executable, "gate.py", "out/fig"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "bare_pct" in ln or "质量门" in ln:
        print("  " + ln.strip())
