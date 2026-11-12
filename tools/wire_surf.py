#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把三联响应面接进论文。

放在「One specification per indicator」表之后 —— 那张表说「三个指标
选了不同的模型」，这张图说「为什么」：映射本身的形状就不同。
"""
import ast
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()

# 锚点：三指标表那段结束之后
ANCHOR = ('        L.append(\n'
          '            "The consequence for the rest of the report is that no single "')
if ANCHOR not in s:
    # 退回：找那句唯一文本
    m = re.search(r'\n(\s*)L\.append\(\n\s*"The consequence for the rest of '
                  r'the report is that no single "', s)
    if not m:
        raise SystemExit("! 找不到锚点")
    ind = m.group(1)
    ANCHOR = s[m.start():m.start() + 60]

FIG = '''        # 响应面：三联图把「映射形状不同」变成看得见的东西
        _sp = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "out", "fig", "surfaces.pdf")
        if os.path.exists(_sp):
            L += [r"\\begin{figure}[H]", r"\\centering",
                  r"\\includegraphics[width=\\textwidth]{surfaces.pdf}",
                  r"\\caption{Response surface of each indicator over the two "
                  r"factors that matter most for it, with the third factor "
                  r"held at its sample median. The measured points are "
                  r"overlaid. The thermal-resistance surface is a plane, "
                  r"which is what its linear specification implies; the "
                  r"other two are visibly curved, each with an interior "
                  r"minimum region, which is what their quadratic "
                  r"specifications capture.}",
                  r"\\label{fig:surfaces}", r"\\end{figure}"]
            L.append("")
            L.append(
                "The three panels are the reason a single specification "
                "could not be used for all three indicators. The thermal "
                "resistance surface is close to a plane: no curvature and "
                "no interior optimum, so a linear form loses nothing. The "
                "pressure-drop surface bends, and so does the "
                "temperature surface, each with a region where the "
                "response is jointly best. A linear model fitted to "
                "either would report a gradient everywhere and would "
                "therefore miss the very feature that makes those two "
                "indicators worth optimising against each other.")
            L.append("")

'''

if "fig:surfaces" not in s:
    i = s.find(ANCHOR)
    if i > 0:
        s = s[:i] + FIG + s[i:]
        print("① 三联图已插入")

ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)

import subprocess
import sys
subprocess.run([sys.executable, "mmkit.py", "run", "--y", "热阻",
                "--x", "宽度,深高,排数", "--min", "热阻,压降,温度",
                "--tex", "out/fig/paper.tex", "--team", "2612345",
                "--problem", "heat sink", "--compile", "--no-gate"],
               capture_output=True, text=True, encoding="utf-8",
               errors="replace", cwd=HERE)
t = open(os.path.join(HERE, "out", "fig", "paper.tex"),
         encoding="utf-8").read()
print()
print("  fig:surfaces:", "fig:surfaces" in t)
print("  surfaces.pdf:", "surfaces.pdf" in t)
errs = re.findall(r"^! (.+)$",
                  open(os.path.join(HERE, "out", "fig", "paper.log"),
                       encoding="utf-8", errors="replace").read(), re.M)
print(f"  编译错误 {len(errs)}: {errs[:2]}")
