import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()

OLD = ('        # brief 版：保留「守恒律给方向 + 数据检验方向」这个论证骨架，\n'
       '        # 去掉具体公式与题目专有名词。这版对任何题都成立。\n'
       '        L.append(r"\\subsection{What the conservation laws fix}")\n'
       '        L.append(\n'
       '            "The indicators enter through conservation of energy and "\n'
       '            "momentum, and those laws fix the direction in which each "\n'
       '            "structural factor should move them. The directions are "\n'
       '            "testable, and they are tested below rather than asserted.")')
assert OLD in s, "no anchor"
NEW = ('        # brief 版：只保留「机理给方向 + 数据检验方向」这个论证骨架。\n'
       '        # 注意不要写「守恒律」「能量动量」——那是热沉题的机理，\n'
       '        # 出现在销量预测或母婴心理的论文里就是胡编。\n'
       '        L.append(r"\\subsection{What the mechanism fixes}")\n'
       '        L.append(\n'
       '            "Each indicator enters with a direction that the problem "\n'
       '            "itself implies, and that direction is fixed before any "\n'
       '            "data is consulted. Those directions are testable, and "\n'
       '            "they are tested below rather than asserted.")')
s = s.replace(OLD, NEW, 1)

# 同一段后面那句也提到 conservation laws
OLD2 = ('        L.append(\n'
        '            "No closed-form mechanism is carried into the model itself. "\n'
        '            "The functional form is chosen by cross-validated error, and "\n'
        '            "the conservation laws supply only the signs that the data "\n'
        '            "then confirm or contradict.')
assert OLD2 in s, "no anchor2"
NEW2 = ('        L.append(\n'
        '            "No closed-form mechanism is carried into the model itself. "\n'
        '            "The functional form is chosen by cross-validated error, and "\n'
        '            "the mechanism supplies only the signs that the data "\n'
        '            "then confirm or contradict.')
s = s.replace(OLD2, NEW2, 1)

ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  brief 版守恒律措辞已改")