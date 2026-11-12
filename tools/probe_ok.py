import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(HERE, "orchestrate.py"), encoding="utf-8").read()
for kw in ("质量不达标", "def exec_one", "ok =", "Attempt"):
    i = 0
    while True:
        i = s.find(kw, i)
        if i < 0:
            break
        ln = s[:i].count("\n") + 1
        line = s[i:].splitlines()[0]
        print("  %-10s :%-5d %s" % (kw, ln, line.strip()[:88]))
        i += len(kw)