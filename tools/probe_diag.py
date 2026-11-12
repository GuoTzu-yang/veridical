import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(HERE, "mm.py"), encoding="utf-8").read()
i = s.find("def diag")
if i < 0:
    i = s.find("def _diag")
print("  === mm.py 的 diag 函数 ===")
print(s[i:i + 900] if i > 0 else "没找到")