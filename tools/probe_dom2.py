import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# domain.py 怎么暴露
d = open(os.path.join(HERE, "domain.py"), encoding="utf-8").read()
for i, ln in enumerate(d.splitlines(), 1):
    if "EXTRA" in ln or "equation" in ln or "extra_eq" in ln:
        print("  domain.py:%-4d %s" % (i, ln.strip()[:88]))
print()
p = open(os.path.join(HERE, "paper.py"), encoding="utf-8").read()
print("  paper.py 里提到 equation/domain 的地方：")
for i, ln in enumerate(p.splitlines(), 1):
    if ("_domain" in ln or "domain." in ln or "equation" in ln.lower()):
        print("  paper.py:%-4d %s" % (i, ln.strip()[:88]))