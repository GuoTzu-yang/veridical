import os
import re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
t = open(os.path.join(HERE, "out", "real", "paper.tex"), encoding="utf-8").read()
m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", t, re.S)
ab = m.group(1) if m else ""
print("  摘要里的 $...$ 片段:")
for x in re.findall(r"\$[^$]{1,60}\$", ab):
    print("    " + x)
print()
# 找 abstract.py 的公式判据
s = open(os.path.join(HERE, "abstract.py"), encoding="utf-8").read()
i = s.find("无公式")
j = s.rfind("def ", 0, i)
print("  abstract.py 的判据函数:")
print("  " + s[j:j + 900].replace("\n", "\n  "))