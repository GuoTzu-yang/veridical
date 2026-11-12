import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lines = open(os.path.join(HERE, "mmkit.py"), encoding="utf-8").read().splitlines()
print("  === 3380-3500 之间的顶层 if（缩进 4/8）===")
for i in range(3379, min(3500, len(lines))):
    ln = lines[i]
    st = ln.strip()
    if not st:
        continue
    ind = len(ln) - len(ln.lstrip())
    if ind <= 8 and (st.startswith("if ") or st.startswith("elif ")
                     or st.startswith("else:") or "tex_path" in st):
        print("  %5d [%d] %s" % (i + 1, ind, st[:80]))