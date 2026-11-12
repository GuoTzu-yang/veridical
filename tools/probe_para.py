import os
import re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(HERE, "paper.py"), encoding="utf-8").read()
print("  === _para 定义 ===")
i = s.find("def _para(")
print(s[i:i + 400] if i > 0 else "没找到")
print()
print("  === _para 调用次数 ===")
print("    _para( 出现 %d 次" % s.count("_para("))
print("    L.append( 出现 %d 次" % s.count("L.append("))