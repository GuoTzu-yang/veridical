import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()
OLD = ('        # 摘要必须压在 1 页内（539 词时最后两句溢到第 2 页）。\n'
       '        # 这两句各压缩一半，信息不丢，词数省 19。\n'
       '        "Two features distinguish this procedure: predictors are "\n'
       '        "re-estimated under two response transformations, and every "\n'
       '        "diagnostic comes from the same fitted object.")')
NEW = ('        # 摘要必须压在 1 页内。这段（19 词）是创新点，但正文\n'
       '        # Evaluation 节有完整论述，摘要里删掉不影响「说清楚新在哪」；\n'
       '        # 留着的话它正好落在第 2 页开头，gate 的 abs_page 会拦。\n'
       '        "Two features distinguish this procedure: predictors are "\n'
       '        "re-estimated under two response transformations.")')
assert OLD in s, "no anchor"
s = s.replace(OLD, NEW, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  trimmed 'Two features' to one clause")