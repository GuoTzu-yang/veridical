#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""核实用户提出的 10 个 PDF 问题（逐条给证据，不猜）。"""
import os
import re

from pypdf import PdfReader

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = os.path.join(HERE, "out", "fig", "paper.pdf")
TEX = os.path.join(HERE, "out", "fig", "paper.tex")
tex = open(TEX, encoding="utf-8").read()
rd = PdfReader(PDF)
pages = [(p.extract_text() or "") for p in rd.pages]
print(f"  PDF {len(pages)} 页\n")


def page(n):
    return pages[n - 1] if 1 <= n <= len(pages) else ""


print("  ═══ 1. 交叉引用失效 Section ?? ═══")
q = [(i + 1, m.group(0)) for i, t in enumerate(pages)
     for m in re.finditer(r".{50}\?\?.{30}", t)]
print(f"    PDF 里出现 ?? 的页: {sorted({p for p, _ in q})}")
for p, s in q[:4]:
    print(f"      第 {p} 页: ...{s.strip()[:90]}...")
# tex 里的 \ref 和 \label 配对
refs = set(re.findall(r"\\ref\{([^}]+)\}", tex))
labels = set(re.findall(r"\\label\{([^}]+)\}", tex))
print(f"    \\ref {len(refs)} 个，\\label {len(labels)} 个")
print(f"    !! 指向不存在 label 的 ref: {sorted(refs - labels)}")

print()
print("  ═══ 2. 重复段落 Figure 4 correlation matrix ═══")
n = tex.count("pairwise correlation matrix")
print(f"    tex 里 'pairwise correlation matrix' 出现 {n} 次")
for i, t in enumerate(pages):
    c = t.count("pairwise correlation matrix")
    if c:
        print(f"      第 {i + 1} 页 {c} 次")

print()
print("  ═══ 3. 重复标题 Human verification ═══")
n = tex.count("Human verification")
print(f"    tex 里 'Human verification' 出现 {n} 次")
for m in re.finditer(r"\\subsection\{([^}]*[Hh]uman[^}]*)\}", tex):
    print(f"      \\subsection{{{m.group(1)}}}")
for i, t in enumerate(pages):
    c = len(re.findall(r"Human verification", t))
    if c:
        print(f"      第 {i + 1} 页 {c} 次")

print()
print("  ═══ 4. Page 20 断句 'shift of -1.7' ═══")
for i, t in enumerate(pages):
    for m in re.finditer(r".{80}shift of[^.]{0,80}", t):
        print(f"      第 {i + 1} 页: ...{m.group(0)[-140:]}")
print("    tex 里 'a shift of' 附近:")
for m in re.finditer(r"a shift of.{0,120}", tex, re.S):
    print(f"      {m.group(0)[:130]!r}")

print()
print("  ═══ 5. Figure 2 X 轴标签重叠 ═══")
figs = re.findall(r"\\includegraphics[^{]*\{([^}]+)\}", tex)
print(f"    tex 引用图 {len(figs)} 个: {figs}")
for f in figs:
    p = os.path.join(HERE, "out", "fig", os.path.basename(f))
    if not os.path.exists(p):
        # 试 pdf
        p = p[:-4] + ".pdf"
    print(f"      {f:<22}{'存在' if os.path.exists(p) else '!! 缺失'}")

print()
print("  ═══ 6. Figure 11 是否真的插入 ═══")
m = re.search(r"Figure~?\\ref\{fig:([^}]+)\}", tex)
labels_fig = re.findall(r"\\label\{(fig:[^}]+)\}", tex)
print(f"    图 label: {labels_fig}")
for i, t in enumerate(pages):
    if "Figure 11" in t:
        print(f"      第 {i + 1} 页提到 Figure 11")
print(f"    tex 里 'fig:surface' 出现的 ref: "
      f"{re.findall(r'\\ref\{(fig:surface[^}]*)\}', tex)}")

print()
print("  ═══ 7-8. 代码附录拼写 ═══")
for bad, good in (("kfold_rmsc", "kfold_rmse"),
                  ("setdiffidx", "setdiff1d"),
                  ("setdiffld", "setdiff1d")):
    nb = tex.count(bad)
    ng = tex.count(good)
    print(f"    {bad:<14}{nb} 次（应为 {good}，正确写法出现 {ng} 次）")
