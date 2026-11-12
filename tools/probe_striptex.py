import os
import re
import sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import aitaste
t = open(os.path.join(HERE, "out", "runs", "age_struct", "paper.tex"),
         encoding="utf-8").read()
st = aitaste.strip_tex(t)
print("  strip_tex 后长度: %d" % len(st))
for m in list(re.finditer(r"not supported the sign", st, re.I))[:3]:
    print("    ...%s..." % st[max(0, m.start() - 120):m.start() + 150]
          .replace("\n", " "))
print()
print("  strip_tex 里 tabular 还在吗:", "tabular" in st)