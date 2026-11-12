import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(HERE, "falsify.py"), encoding="utf-8").read()
i = s.find("偏相关对照失败")
print("  上下文：")
print(s[max(0, i-900):i+150])