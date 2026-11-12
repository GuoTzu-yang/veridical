import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()

OLD = ('    for f in ("clustering.xlsx", "multiobjective.xlsx"):\n'
       '        if not _o.path.exists(_o.path.join(HERE, "out", "kinds", f)):\n'
       '            bad.append("missing " + f)')
assert OLD in s, "no old block"
NEW = ('    # 数据集归到 out/data/ 了（out/kinds/ 已删除）\n'
       '    for f in ("clustering.xlsx", "multiobjective.xlsx",\n'
       '              "simulation.xlsx"):\n'
       '        if not _o.path.exists(_o.path.join(HERE, "out", "data", f)):\n'
       '            bad.append("missing " + f)')
s = s.replace(OLD, NEW, 1)
ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  patched P76 judgement")