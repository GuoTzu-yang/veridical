import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()
OLD = "    if 'print(json.dumps(' in m:\n        bad.append('raw print(json.dumps) still present')"
assert OLD in s, "no anchor"
NEW = ("    # _emit 自己内部就是 print(json.dumps(..., file=sys.__stdout__))，\n"
       "    # 那是唯一正确的一处。判据要看「除 _emit 外还有没有残留」。\n"
       "    _body = m.split('def _emit(', 1)[-1]\n"
       "    _rest = _body.split('\\n\\n\\n', 1)[-1] if '\\n\\n\\n' in _body else ''\n"
       "    if 'print(json.dumps(' in _rest:\n"
       "        bad.append('raw print(json.dumps) outside _emit')")
s = s.replace(OLD, NEW, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  P106 判据已精确化")