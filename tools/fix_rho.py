import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mmkit.py")
s = open(P, encoding="utf-8").read()
OLD = '                    _rho = mm.pearson(_xv, _yv)'
assert OLD in s, "no anchor"
NEW = ('                    _a = np.asarray(_xv, dtype=float)\n'
       '                    _b = np.asarray(_yv, dtype=float)\n'
       '                    _m2 = ~(np.isnan(_a) | np.isnan(_b))\n'
       '                    _rho = (float(np.corrcoef(_a[_m2], _b[_m2])[0, 1])\n'
       '                            if _m2.sum() > 2 else 0.0)')
s = s.replace(OLD, NEW, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  sign 改用 np.corrcoef")