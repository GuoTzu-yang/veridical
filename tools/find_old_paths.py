import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATS = [
    (re.compile(r"out[/\\]kinds[/\\]"), "out/data/"),
    (re.compile(r"out[/\\]real_hs2024\.xlsx"), "out/data/real_hs2024.xlsx"),
    (re.compile(r"out[/\\]real_hs\.xlsx"), "out/data/real_hs.xlsx"),
    (re.compile(r"out[/\\]scope_test\.xlsx"), "out/data/scope_test.xlsx"),
    (re.compile(r"out[/\\]domains[/\\](\w+)\.xlsx"), r"out/data/\1.xlsx"),
]
for f in sorted(os.listdir(HERE)):
    if not f.endswith(".py"):
        continue
    p = os.path.join(HERE, f)
    s = open(p, encoding="utf-8", errors="replace").read()
    hits = []
    for rx, _ in PATS:
        for m in rx.finditer(s):
            hits.append((s[:m.start()].count("\n") + 1, m.group(0)))
    if hits:
        print("  %s:" % f)
        for no, t in hits:
            print("    :%-5d%s" % (no, t))