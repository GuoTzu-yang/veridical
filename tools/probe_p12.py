import os
import re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(HERE, "patches.py"), encoding="utf-8").read()
i = s.find('"P12"')
print("  P12 条目上下文：")
print(s[max(0, i - 200):i + 420])