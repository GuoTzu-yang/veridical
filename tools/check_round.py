#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""核实用户这轮反馈的三个前提。"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

print("  === 1. scienceplots 装了没 ===")
for mod in ("scienceplots", "matplotlib", "pygments"):
    r = subprocess.run([sys.executable, "-c", f"import {mod}; print({mod}.__version__ if hasattr({mod},'__version__') else 'ok')"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    print(f"    {mod:<16}{r.stdout.strip() or '未安装: ' + (r.stderr or '').strip().splitlines()[-1][:50]}")

print()
print("  === 2. 第 20 页那段到底断在哪 ===")
from pypdf import PdfReader
r = PdfReader(os.path.join(HERE, "out", "fig", "paper.pdf"))
for n in (19, 20):
    t = r.pages[n - 1].extract_text() or ""
    if "shift of" in t:
        i = t.find("shift of")
        print(f"    第 {n} 页:")
        seg = t[max(0, i - 200):i + 400]
        print("      " + seg.replace("\n", " "))
        print()
print("  tex 源里这一整段:")
tex = open(os.path.join(HERE, "out", "fig", "paper.tex"), encoding="utf-8").read()
for m in re.finditer(r"Moving it from.{0,600}", tex, re.S):
    print("    " + m.group(0).replace("\n", " ")[:520])
    print()

print()
print("  === 3. 附录代码现在是什么 ===")
m = re.search(r"\\section\{Core Code\}(.*?)(?:\\end\{document\}|\\bibliography)", tex, re.S)
if m:
    body = m.group(1)
    print(f"    长度 {len(body)} 字符")
    print(f"    含 verbatim: {'verbatim' in body}")
    print(f"    含 lstlisting: {'lstlisting' in body}")
    print(f"    def 出现 {body.count('def ')} 次")
    print("    前 400 字符:")
    print("      " + body[:400].replace("\n", " "))
else:
    print("    没有 Core Code 节")

print()
print("  === 4. 语言风格样本：口语化句子 ===")
for pat in (r"floor any real model must beat", r"It is the floor",
            r"The main model is the specification reported in this section"):
    for m2 in re.finditer(pat, tex):
        i = m2.start()
        print(f"    ...{tex[max(0,i-60):i+110].replace(chr(10),' ')}...")
        break
