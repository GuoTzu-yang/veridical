import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()
OLD = ('    s = str(name)\n'
       '    if not has_cjk(s):\n'
       '        return s, True')
assert OLD in s, "no describe non-cjk branch"
NEW = ('    s = str(name)\n'
       '    if not has_cjk(s):\n'
       '        # 英文列名直接返回，但下划线必须换掉：它进 tex 后会被当成\n'
       '        # 数学下标，编译报 "Missing $ inserted"。实测列名\n'
       '        # yield_per_mu 一次就产生 15 处编译错误。\n'
       '        return s.replace("_", " "), True')
s = s.replace(OLD, NEW, 1)
ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  describe: '_' -> ' '")