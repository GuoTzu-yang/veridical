import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for f in sorted(os.listdir(HERE)):
    if not f.endswith(".py"):
        continue
    p = os.path.join(HERE, f)
    lines = open(p, encoding="utf-8", errors="replace").read().splitlines()
    for no, ln in enumerate(lines, 1):
        if "--lang" in ln or "a.lang" in ln:
            print("  %-16s:%-5d%s" % (f, no, ln.strip()[:88]))