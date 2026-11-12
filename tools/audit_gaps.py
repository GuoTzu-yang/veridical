#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查摘要/正文还差什么（一次查完，避免多次编译）。"""
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
t = open(os.path.join(HERE, "out", "fig", "paper.tex"),
         encoding="utf-8").read()

print("  === 1. 优点/缺点 ===")
for sec in ("Strengths", "Limitations"):
    m = re.search(r"\\subsection\{" + sec + r"\}(.*?)"
                  r"(?:\\subsection|\\section)", t, re.S)
    if m:
        items = re.findall(r"\\item", m.group(1))
        print(f"    {sec}: {len(items)} 条")
        for x in re.findall(r"\\item\s+(.{0,70})", m.group(1)):
            print(f"      - {x}")
    else:
        print(f"    {sec}: 小节不存在")

print()
print("  === 2. 参数来源标注 ===")
for kw in ("from the statement", "from the data", "parameter source",
           "literature value", "given in the statement"):
    print(f"    {kw:<26}{len(re.findall(re.escape(kw), t, re.I))} 次")

print()
print("  === 3. 引言文献综述 ===")
m = re.search(r"\\section\{Introduction\}(.*?)\\section", t, re.S)
if m:
    body = m.group(1)
    print(f"    引言 {len(body)} 字符，\\cite 出现 {body.count(chr(92) + 'cite')} 次")
    print(f"    含 'literature'/'previous work': "
          f"{'literature' in body.lower() or 'previous' in body.lower()}")
else:
    print("    没找到 Introduction 节")

print()
print("  === 4. 影响规律小结 ===")
for kw in ("strongest influence", "most influential", "dominant factor",
           "largest coefficient", "ordering of the factors"):
    print(f"    {kw:<24}{len(re.findall(kw, t, re.I))} 次")

print()
print("  === 5. 摘要 ===")
m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", t, re.S)
b = m.group(1) if m else ""
w = len(re.findall(r"[A-Za-z][A-Za-z'-]*", b))
print(f"    {w} 词（上限 600），Problem 锚点 "
      f"{len(re.findall(r'Problem [0-9]', b))} 个")
for kw in ("prediction interval spans", "Residual diagnostics",
           "response surface of", "minimax", "tolerance"):
    print(f"    {kw:<28}{kw in b}")

print()
print("  === 6. 全文章节 ===")
for m in re.finditer(r"\\section\{([^}]+)\}", t):
    print(f"    {m.group(1)[:64]}")
