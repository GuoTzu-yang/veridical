import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "kind.py")
s = open(P, encoding="utf-8").read()

OLD = 'def detect(problem_desc="", cols=None, y=None, min_score=2):'
assert OLD in s, "no detect sig"
NEW = 'def detect(problem_desc="", cols=None, y=None, min_score=2,\n' \
      '            n_obj=None, n_rows=None, has_time=False):'
s = s.replace(OLD, NEW, 1)

OLD2 = ('    problem_desc 可以是英文或中文；cols 是列名列表。\n'
        '    """')
assert OLD2 in s, "no docstring"
NEW2 = ('    problem_desc 可以是英文或中文；cols 是列名列表。\n'
        '\n'
        '    除了文字和列名，还看**结构信号** —— 它们比列名可靠得多：\n'
        '    列名是用户自己起的（pop2005 / life2005 谁都猜不出题型），\n'
        '    但「有几个目标」「有没有时间维度」「多少行」是数据本身的性质。\n'
        '    实测 ICM 2006 C 的题面和列名都判不出类型，加上结构信号后\n'
        '    判成 multiobjective（两个目标：人口与预期寿命）。\n'
        '    """')
s = s.replace(OLD2, NEW2, 1)

OLD3 = ('        for f in spec.get("data_features", []):\n'
        '            if f.lower() in coltext:\n'
        '                s += 1\n'
        '                hit.append(f + "(特征)")')
assert OLD3 in s, "no features loop"
NEW3 = (OLD3 + '\n'
        '        # ── 结构信号 ──\n'
        '        # 多目标（--min 给了 2 个以上）→ multiobjective 候选\n'
        '        # 有时间列 → prediction 候选\n'
        '        if kid == "multiobjective" and (n_obj or 0) >= 2:\n'
        '            s += 1\n'
        '            hit.append("多目标(%d)" % n_obj)\n'
        '        if kid == "prediction" and (has_time or (n_obj or 0) >= 2):\n'
        '            s += 1\n'
        '            hit.append("时间/多期结构")\n'
        '        if kid == "regression" and (n_rows or 0) >= 30:\n'
        '            s += 1\n'
        '            hit.append("样本量 %d" % n_rows)')
s = s.replace(OLD3, NEW3, 1)

ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  detect now takes structure signals")