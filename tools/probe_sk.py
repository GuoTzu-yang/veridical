import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(HERE, "mmkit.py"), encoding="utf-8").read()
for kw in ("_SKELETON_ONLY", 'a.cmd = "run"', "def set_overrides"):
    i = 0
    while True:
        i = s.find(kw, i)
        if i < 0:
            break
        ln = s[:i].count("\n") + 1
        print("  %-16s :%-5d %s" % (kw, ln, s[i:].splitlines()[0].strip()[:60]))
        i += len(kw)