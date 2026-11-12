import os, re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(HERE, "mmkit.py"), encoding="utf-8").read()
# 找矩阵解析函数
for kw in ("矩阵解析失败", "输入解析失败"):
    i = s.find(kw)
    if i > 0:
        print("  === %s 附近的解析 ===" % kw)
        print(s[max(0, i-700):i+120])
        print()