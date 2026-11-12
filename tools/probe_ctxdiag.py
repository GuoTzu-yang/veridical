import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(HERE, "mmkit.py"), encoding="utf-8").read()
i = s.find("diag=_diag_ctx")
if i < 0:
    i = s.find("diag=")
print("  ctx 里 diag= 的构造：")
print(s[max(0, i - 700):i + 260])