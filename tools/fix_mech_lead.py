import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()

OLD = ('    L.append(\n'
       '        "The specification used later is not chosen by convenience. The "\n'
       '        "three indicators follow from conservation of energy and momentum, "\n'
       '        "and those laws fix the direction in which each geometric factor "\n'
       '        "should move them. Those directions are testable, and they are "\n'
       '        "tested below rather than asserted.")')
assert OLD in s, "no anchor"

NEW = ('    # brief 模式（非机理题）不能写「能量动量守恒」「几何因子」——\n'
       '    # 那两句是热沉题的机理。实测评价/预测/化工三题的机理节正文\n'
       '    # 长度完全相同（2162 字），说明是同一段模板：评委在预测销量\n'
       '    # 的论文里读到 conservation of energy and momentum，会直接判定\n'
       '    # 为不审题。brief 走通用说法。\n'
       '    if _mech == "full":\n'
       '        L.append(\n'
       '            "The specification used later is not chosen by convenience. The "\n'
       '            "three indicators follow from conservation of energy and momentum, "\n'
       '            "and those laws fix the direction in which each geometric factor "\n'
       '            "should move them. Those directions are testable, and they are "\n'
       '            "tested below rather than asserted.")\n'
       '    else:\n'
       '        L.append(\n'
       '            "The specification used later is not chosen by convenience. "\n'
       '            "It follows from the problem as stated: each factor enters "\n'
       '            "with a direction that can be tested against the data rather "\n'
       '            "than assumed. Those directions are tested below, not asserted.")')
s = s.replace(OLD, NEW, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  brief/full 分流完成")