import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(HERE, "paper.py"), encoding="utf-8").read()
i = s.find("not supported the sign")
print("  引用处（%d）：" % i)
print(s[max(0, i - 1400):i + 300])