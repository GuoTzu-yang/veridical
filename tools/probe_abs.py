import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(HERE, "paper.py"), encoding="utf-8").read()

# 摘要区间
i = s.find(r'L += [r"\begin{abstract}"')
j = s.find(r'\end{abstract}', i)
if j < 0:
    j = s.find("def _localize", i)
seg = s[i:j]
print("  摘要区间 %d 字符 / %d 行" % (j - i, seg.count("\n")))
# 摘要里面向读者的英文句子（带引号的字符串字面量）
lits = re.findall(r'"((?:[^"\\]|\\.){20,})"', seg)
print("  摘要里长字符串字面量 %d 条" % len(lits))
# 哪些含 f-string（带数字）
fixed = [x for x in lits if "{" not in x]
dyn = [x for x in lits if "{" in x]
print("  其中固定句 %d 条 / 带插值 %d 条" % (len(fixed), len(dyn)))
print()
print("  --- 固定句（前 14 条）---")
for x in fixed[:14]:
    print("    %s" % x[:96])