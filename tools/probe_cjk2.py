import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(HERE, "mmkit.py")
lines = open(p, encoding="utf-8").read().splitlines()
for no, ln in enumerate(lines, 1):
    if "_re_cjk" in ln and "compile" not in ln:
        print("  :%-5d%s" % (no, ln.strip()[:88]))
        for k in range(max(0, no - 7), min(len(lines), no + 4)):
            mark = ">>" if k + 1 == no else "  "
            print("    %s %4d  %s" % (mark, k + 1, lines[k][:86]))
        print()