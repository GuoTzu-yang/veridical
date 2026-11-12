import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "kind.py")
s = open(P, encoding="utf-8").read()

OLD = ('        if kid == "multiobjective" and (n_obj or 0) >= 2:\n'
       '            s += 1\n'
       '            hit.append("多目标(%d)" % n_obj)\n'
       '        if kid == "prediction" and (has_time or (n_obj or 0) >= 2):\n'
       '            s += 1\n'
       '            hit.append("时间/多期结构")\n'
       '        if kid == "regression" and (n_rows or 0) >= 30:\n'
       '            s += 1\n'
       '            hit.append("样本量 %d" % n_rows)')
assert OLD in s, "no struct block"
NEW = ('        # 结构信号给 2 分（和题面触发词同权）：它是数据本身的性质，\n'
       '        # 比列名可靠。给 1 分的话永远够不到 min_score=2 ——\n'
       '        # ICM 2006 C 就是三个信号各 1 分、一个都不成立。\n'
       '        if kid == "multiobjective" and (n_obj or 0) >= 2:\n'
       '            s += 2\n'
       '            hit.append("多目标(%d)" % n_obj)\n'
       '        if kid == "prediction" and has_time:\n'
       '            s += 2\n'
       '            hit.append("时间维度")\n'
       '        if kid == "regression" and (n_rows or 0) >= 30:\n'
       '            s += 2\n'
       '            hit.append("样本量 %d" % n_rows)')
s = s.replace(OLD, NEW, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  struct signals now weight 2")