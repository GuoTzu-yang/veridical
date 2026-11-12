import os
import re

P = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "out", "arch", "paper.tex")
t = open(P, encoding="utf-8").read()
lines = t.split("\n")

print("== 所有 caption 及所在行 ==")
for i, l in enumerate(lines):
    if "\\caption" in l:
        seg = "\n".join(lines[i:i + 4])
        print("\n  L%d: %s" % (i + 1, l.strip()[:100]))
        if "$[" in seg:
            print("       !! 含 $[")
        if "%" in seg:
            for j in range(i, min(len(lines), i + 4)):
                if re.search(r"(?<!\\)%", lines[j]) and "\\%" not in lines[j]:
                    print("       !! L%d 裸 %%: %s" % (j + 1, lines[j].strip()[:90]))

print("\n== figure/table 环境配对 ==")
print("  \\begin{figure}  :", t.count("\\begin{figure}"))
print("  \\end{figure}    :", t.count("\\end{figure}"))
print("  \\begin{table}   :", t.count("\\begin{table}"))
print("  \\end{table}     :", t.count("\\end{table}"))
print("  \\begin{tabular} :", t.count("\\begin{tabular}"))
print("  \\end{tabular}   :", t.count("\\end{tabular}"))
print("  \\caption       :", t.count("\\caption"))
