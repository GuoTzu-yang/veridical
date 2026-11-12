import ast
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()

# 摘要里所有 $R^2$ 改成文字。CUMCM 摘要要求「无公式」，
# 而 R² < 0.10 时会多输出一句，$R^2$ 就从 1 个变 2 个，
# 刚好越过 abstract.py 的阈值 —— 真赛题（R²=2.7%）就是这样红的。
n1 = s.count('f"$R^2 = {pct(r2)}$."')
s = s.replace('f"$R^2 = {pct(r2)}$."',
              'f"an R-squared of {pct(r2)}."')
n2 = s.count('f"With $R^2 = {pct(r2)}$ the explanatory power is "')
s = s.replace('f"With $R^2 = {pct(r2)}$ the explanatory power is "',
              'f"With an R-squared of {pct(r2)} the explanatory power is "')
ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  abstract: $R^2$ -> R-squared  (%d + %d 处)" % (n1, n2))

# 确认摘要里已无 $
t = open(os.path.join(HERE, "out", "real", "paper.tex"), encoding="utf-8").read()
m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", t, re.S)
if m:
    left = re.findall(r"\$[^$]{1,60}\$", m.group(1))
    print("  旧 tex 里还剩 %d 个公式（需重跑）" % len(left))