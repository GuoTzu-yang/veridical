import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(HERE, "gate.py"), encoding="utf-8").read()
# gate 里 tex 变量叫什么
for kw in ("tex =", "tex_path", "def check_falsify", "def _falsify"):
    i = 0
    while True:
        i = s.find(kw, i)
        if i < 0: break
        ln = s[:i].count("\n")+1
        print("  %-18s :%-5d %s" % (kw, ln, s[i:].splitlines()[0].strip()[:70]))
        i += len(kw)