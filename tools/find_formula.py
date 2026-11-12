import os
import re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
needle = "无公式"
for f in sorted(os.listdir(HERE)):
    if not f.endswith(".py"):
        continue
    p = os.path.join(HERE, f)
    try:
        s = open(p, encoding="utf-8").read()
    except Exception:
        continue
    if needle in s:
        i = s.find(needle)
        print("  === %s ===" % f)
        print("  " + s[max(0, i - 400):i + 160].replace("\n", "\n  "))
        print()