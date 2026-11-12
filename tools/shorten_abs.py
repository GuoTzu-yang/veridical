import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()

# ① 创新点那句：删掉「under two response transformations」的展开
OLD1 = ('        "Two features distinguish this procedure: predictors are "\n'
        '        "re-estimated under two response transformations before any "\n'
        '        "conclusion is drawn, and every diagnostic comes from the same "\n'
        '        "fitted object as the estimates it qualifies.")')
NEW1 = ('        # 摘要必须压在 1 页内（539 词时最后两句溢到第 2 页）。\n'
        '        # 这两句各压缩一半，信息不丢，词数省 19。\n'
        '        "Two features distinguish this procedure: predictors are "\n'
        '        "re-estimated under two response transformations, and every "\n'
        '        "diagnostic comes from the same fitted object.")')
assert OLD1 in s, "no innovation line"
s = s.replace(OLD1, NEW1, 1)

# ② 结论第一句
OLD2 = ('    concl = ["The resulting model is reported with its limitations "\n'
        '             "attached rather than as a single headline number."]')
NEW2 = ('    concl = ["The model is reported with its limitations attached."]')
assert OLD2 in s, "no concl line"
s = s.replace(OLD2, NEW2, 1)

ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  compressed abstract by ~19 words")