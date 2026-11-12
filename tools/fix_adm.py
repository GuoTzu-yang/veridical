import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "gate.py")
s = open(P, encoding="utf-8").read()
OLD = '            _tt = open(tex, encoding="utf-8").read()'
assert OLD in s, "no anchor"
NEW = ('            # 这个函数签名里只有 figdir，没有 tex；写 open(tex) 会\n'
       '            # NameError，被 except 吞掉，_admits 永远是 False。\n'
       '            _tp = os.path.join(figdir, "paper.tex")\n'
       '            _tt = open(_tp, encoding="utf-8").read()')
s = s.replace(OLD, NEW, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  chk_falsify 用 figdir 拼路径")