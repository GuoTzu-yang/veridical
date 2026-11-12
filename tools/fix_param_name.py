import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mmkit.py")
s = open(P, encoding="utf-8").read()
OLD = ("                    _fh = _fig_hint(ctx, data_path, yname,\n"
       "                                    xnames, mins)")
assert OLD in s, "no anchor"
NEW = ("                    # run 的参数名是 data，不是 data_path。\n"
       "                    # 写错名字会抛 NameError，然后被外面那层\n"
       "                    # try/except 吞掉 —— 提示静默消失，很难查。\n"
       "                    _fh = _fig_hint(ctx, data, yname,\n"
       "                                    xnames, mins)")
s = s.replace(OLD, NEW, 1)
ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  data_path -> data")