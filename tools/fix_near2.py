import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "verify.py")
s = open(P, encoding="utf-8").read()
OLD = '    if _decimals(b) < _decimals(a) - 2:\n        return False'
assert OLD in s, "no anchor"
NEW = ('    _da, _db = _decimals(a), _decimals(b)\n'
       '    if _db < _da - 2:\n'
       '        return False\n'
       '    # 同精度（或输出更高精度）：必须精确相等。\n'
       '    # 0.9999 与 0.9975 都是 4 位，差 0.24% —— 那是改数，不是舍入。\n'
       '    # 只有「输出精度更低」时，近似才算舍入（0.0074342 -> 0.00743）。\n'
       '    if _db >= _da:\n'
       '        return abs(a - b) / max(abs(a), abs(b), 1e-12) <= 1e-9')
s = s.replace(OLD, NEW, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  _near：同精度必须精确")