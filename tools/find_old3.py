import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYS = ("out/domains", "out/kinds", "out/real_hs", "out/scope_test",
        "\"out\", \"domains\"", "\"out\", \"kinds\"",
        '"out", "domains"', '"out", "kinds"')
for sub in ("tools", "tests"):
    d = os.path.join(HERE, sub)
    if not os.path.isdir(d):
        continue
    for f in sorted(os.listdir(d)):
        if not f.endswith(".py"):
            continue
        p = os.path.join(d, f)
        lines = open(p, encoding="utf-8", errors="replace").read().splitlines()
        for no, ln in enumerate(lines, 1):
            if any(k in ln for k in KEYS):
                print("  %-14s:%-5d%s" % (sub + "/" + f, no, ln.strip()[:86]))