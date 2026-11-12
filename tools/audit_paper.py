#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盘点：离「直通论文」还差什么。"""
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

KEYS = {
    "LaTeX 生成": [r"\\documentclass", r"\\begin\{document\}", r"\\section\{"],
    "Mermaid 流程图": [r"mermaid", r"graph TD", r"flowchart"],
    "PDF 导出": [r"pdflatex", r"xelatex", r"latexmk", r"libreoffice"],
    "符号表（Notation）": [r"notation", r"符号说明", r"三线表"],
    "假设（Assumptions）": [r"assumption", r"模型假设"],
    "摘要（Summary）": [r"\\begin\{abstract\}", r"summary"],
    "参考文献": [r"\\bibliography", r"\\bibitem", r"thebibliography"],
    "目标函数/约束公式化": [r"\\min\s", r"\\max\s", r"\\text\{s\.t\.\}",
                            r"objective"],
}

print("现状盘点（在 model1-arch/*.py 里找）")
print("=" * 70)
files = [f for f in os.listdir(HERE) if f.endswith(".py")]
cache = {}
for f in files:
    try:
        cache[f] = open(os.path.join(HERE, f), encoding="utf-8",
                        errors="replace").read()
    except OSError:
        pass

for label, pats in KEYS.items():
    hits = []
    for f, src in cache.items():
        for p in pats:
            if re.search(p, src):
                hits.append(f)
                break
    status = "有" if hits else "**没有**"
    print(f"  {label:<22}{status:<8}{hits if hits else ''}")

print()
print("现有子命令:")
import ast
src = cache.get("mmkit.py", "")
if src:
    t = ast.parse(src)
    for node in ast.walk(t):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "add_argument":
            for a in node.args:
                if isinstance(a, ast.Constant) and a.value == "choices":
                    pass
    m = re.search(r'choices=\[([^\]]+)\]', src)
    if m:
        print("  " + m.group(1).replace('"', "").replace("\n", " "))

print()
print("数据列名 → 英文化难度（列名里有没有中文）:")
for f in ("mm.py", "mmkit.py"):
    s = cache.get(f, "")
    n_cn = len(re.findall(r"[\u4e00-\u9fff]", s))
    print(f"  {f:<12} 含 {n_cn} 个中文字符（注释与字符串里）")
