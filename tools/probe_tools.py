import os
import re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for f in ("schema.py", "contract.py", "verify.py", "falsify.py", "lanes.py"):
    p = os.path.join(HERE, f)
    if not os.path.exists(p):
        print("  %-12s 不存在" % f)
        continue
    t = open(p, encoding="utf-8").read()
    doc = t.split('"""')[1].strip().splitlines()[:6] if '"""' in t else []
    print("  === %s (%d 行) ===" % (f, len(t.splitlines())))
    for ln in doc:
        print("      %s" % ln[:86])
    print()