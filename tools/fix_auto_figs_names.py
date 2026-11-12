import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mmkit.py")
s = open(P, encoding="utf-8").read()
OLD = ('    ys = _paper.describe(ycol)[0]\n'
       '    xnames = ",".join(_paper.describe(c)[0] for c in xs)\n'
       '    mins = ",".join(_paper.describe(c)[0] for c in (min_cols or []))')
assert OLD in s, "no anchor"
NEW = ('    # 必须用**原始列名**：plot 是按列名去读数据文件的，而\n'
       '    # describe() 会把中文翻译成英文（热阻 -> thermal resistance），\n'
       '    # 数据里没有那一列，于是 12 张里只有 3 张不需要列名的能出来。\n'
       '    ys = str(ycol)\n'
       '    xnames = ",".join(str(c) for c in xs)\n'
       '    mins = ",".join(str(c) for c in (min_cols or []))')
s = s.replace(OLD, NEW, 1)
ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  use raw column names")