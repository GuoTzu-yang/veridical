import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
m = open(os.path.join(HERE, "mmkit.py"), encoding="utf-8").read()
for i, ln in enumerate(m.splitlines(), 1):
    if "domain" in ln.lower() and ("ctx" in ln or "=" in ln):
        if "domain=" in ln or "_dom" in ln or "import domain" in ln:
            print("  mmkit.py:%-4d %s" % (i, ln.strip()[:88]))
print()
p = open(os.path.join(HERE, "paper.py"), encoding="utf-8").read()
for i, ln in enumerate(p.splitlines(), 1):
    if '"domain"' in ln or "'domain'" in ln or "dom_det" in ln:
        print("  paper.py:%-4d %s" % (i, ln.strip()[:88]))