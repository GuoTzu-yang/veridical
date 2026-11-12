import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for f in ("mmkit.py", "mm.py"):
    s = open(os.path.join(HERE, f), encoding="utf-8").read()
    i = 0
    while True:
        i = s.find("diag_report", i)
        if i < 0:
            break
        ln = s[:i].count("\n") + 1
        print("  %s:%d" % (f, ln))
        print("    " + s[max(0, i - 240):i + 90].splitlines()[-3:][0][:84])
        i += 11