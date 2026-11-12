import re
for f in ("out/lang_zh/paper.tex", "out/fig/paper.tex"):
    t = open(f, encoding="utf-8").read()
    print("  === %s ===" % f)
    for m in re.finditer(r"\\section\*?\{([^}]*)\}", t):
        print("    " + m.group(1)[:52])
    print("  summary 段存在:", "\\begin{abstract}" in t)
    print()