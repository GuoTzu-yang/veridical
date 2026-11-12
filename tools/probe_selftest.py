import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "verify.py")
s = open(P, encoding="utf-8").read()
i = s.find("0.0074342 与 0.00743 视为同源")
if i < 0:
    print("  找不到该用例")
else:
    ln = s[:i].count("\n") + 1
    print("  原用例在第 %d 行" % ln)
    print("  上下文：")
    print(s[max(0, i - 200):i + 200])