import os
import re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for f in ("mmkit.py", "mm.py", "rules.py", "judge.py"):
    p = os.path.join(HERE, f)
    if not os.path.exists(p):
        continue
    s = open(p, encoding="utf-8").read()
    if "I004" in s:
        i = s.find("I004")
        print("=== %s ===" % f)
        print(s[max(0, i - 500):i + 400])
        print()