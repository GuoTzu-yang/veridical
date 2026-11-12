import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYS = ("domains", "kinds", "real_hs", "scope_test.xlsx")
for f in sorted(os.listdir(HERE)):
    if not f.endswith(".py"):
        continue
    p = os.path.join(HERE, f)
    lines = open(p, encoding="utf-8", errors="replace").read().splitlines()
    for no, ln in enumerate(lines, 1):
        if any(k in ln for k in KEYS):
            if ln.lstrip().startswith("#"):
                continue
            print("  %-26s:%-5d%s" % (f, no, ln.strip()[:88]))