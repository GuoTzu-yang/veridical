import os, re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(HERE, "tools", "verify_all.py"), encoding="utf-8").read()
i = s.find("回归")
print(s[max(0, i-400):i+900])