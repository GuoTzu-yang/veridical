import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(HERE, "mmkit.py"), encoding="utf-8").read()
for kw in ("set_overrides", "_paper.build(ctx)", "--overrides"):
    i = 0
    while True:
        i = s.find(kw, i)
        if i < 0:
            break
        ln = s[:i].count("\n") + 1
        print("  %-20s :%-5d %s" % (kw, ln, s[i:].splitlines()[0].strip()[:66]))
        i += len(kw)
print()
print("  === 上下文（set_overrides 附近）===")
i = s.find("_paper.set_overrides(None)")
if i > 0:
    print(s[max(0, i - 300):i + 200])