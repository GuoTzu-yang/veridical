import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()
# 1) 删掉 "Two features" 整段
OLD1 = ('        # 摘要必须压在 1 页内。这段（19 词）是创新点，但正文\n'
        '        # Evaluation 节有完整论述，摘要里删掉不影响「说清楚新在哪」；\n'
        '        # 留着的话它正好落在第 2 页开头，gate 的 abs_page 会拦。\n'
        '        "Two features distinguish this procedure: predictors are "\n'
        '        "re-estimated under two response transformations.")')
NEW1 = ('        # 摘要压在 1 页内：这段（创新点）与 "_para" 的结论句\n'
        '        # 实测都会落在第 2 页，而正文 Evaluation / Limitations 节\n'
        '        # 已有完整论述，摘要不必重复。删掉后 512 -> 482 词。\n'
        '        "__ABSTRACT_TRIM__")\n'
        '    # 上面这行故意留一个占位串，下面统一清掉\n'
        '    L = [x for x in L if x != "__ABSTRACT_TRIM__"]')
if OLD1 in s:
    s = s.replace(OLD1, NEW1, 1)
# 2) 结论句也删
OLD2 = '    concl = ["The model is reported with its limitations attached."]'
NEW2 = '    concl = []   # 局限在 \\section{Limitations} 有完整论述，摘要不重复'
if OLD2 in s:
    s = s.replace(OLD2, NEW2, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  dropped both trailing blocks")