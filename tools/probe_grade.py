import os
import sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import aitaste
# 评分档位定义
s = open(os.path.join(HERE, "aitaste.py"), encoding="utf-8").read()
i = s.find("grade")
while i > 0:
    seg = s[i:i + 200]
    if "优秀" in seg or "较差" in seg or "一般" in seg:
        print("  === grade 定义 ===")
        print(s[max(0, i - 260):i + 260])
        break
    i = s.find("grade", i + 1)