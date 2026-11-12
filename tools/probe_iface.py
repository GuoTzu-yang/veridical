import os
import re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for f in ("contract.py", "orchestrate.py"):
    t = open(os.path.join(HERE, f), encoding="utf-8").read()
    print("  === %s 的公开函数 ===" % f)
    for m in re.finditer(r"^def (\w+)\(([^)]*)\)", t, re.M):
        print("    %s(%s)" % (m.group(1), " ".join(m.group(2).split())[:70]))
    print()