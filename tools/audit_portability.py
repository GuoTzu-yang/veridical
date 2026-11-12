#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计「依赖 workspace 相对位置」的代码。

同一类病已经发作三次：
  44 轮  mmkit._collect_figures 的兜底目录是仓库默认题的 out/fig
  54 轮  paper.py 三处硬编码 <repo>/out/fig/{surfaces,tornado,cand}.pdf
  54 轮  mmkit._auto_figs 传给 plot 的列名被翻译过

共同点：在 model1-arch/ 里跑没事，换个目录跑就静默丢内容。
所以一次性扫出来，而不是一次次踩。
"""
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RULES = [
    ("HARD_FIG", re.compile(r'"out"\s*,\s*"fig"'),
     "硬编码仓库默认题的 out/fig —— 换目录跑就丢"),
    ("FILE_REL", re.compile(r'os\.path\.dirname\(os\.path\.abspath\(__file__\)\)'),
     "以本文件位置为锚（多数用法是对的，但配合 out/ 就是错的）"),
    ("CWD", re.compile(r'os\.getcwd\(\)'),
     "依赖当前工作目录"),
    ("OPEN_REL", re.compile(r'open\(\s*"(?!/)([A-Za-z0-9_./-]+)"'),
     "相对路径 open() —— 取决于从哪运行"),
    ("ENV", re.compile(r'os\.environ(?:\.get)?\[?\s*["\']?(MMKIT_[A-Z_]+)'),
     "环境变量依赖（要有默认值才安全）"),
]

def main():
    hits = {}
    for f in sorted(os.listdir(HERE)):
        if not f.endswith(".py"):
            continue
        p = os.path.join(HERE, f)
        try:
            lines = open(p, encoding="utf-8").read().splitlines()
        except Exception:
            continue
        for no, ln in enumerate(lines, 1):
            for rid, rx, why in RULES:
                if rx.search(ln):
                    if rid == "OPEN_REL" and ln.lstrip().startswith("#"):
                        continue
                    hits.setdefault(rid, []).append((f, no, ln.strip()[:96], why))

    for rid, rx, why in RULES:
        rows = hits.get(rid) or []
        print("=" * 74)
        print("%s  (%d 处)  —— %s" % (rid, len(rows), why))
        print("=" * 74)
        if not rows:
            print("  无")
        for f, no, ln, _ in rows[:14]:
            print("  %-14s:%-5d %s" % (f, no, ln))
        if len(rows) > 14:
            print("  ... 还有 %d 处" % (len(rows) - 14))
        print()


if __name__ == "__main__":
    main()