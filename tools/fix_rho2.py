import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "gate.py")
s = open(P, encoding="utf-8").read()

OLD = ('                _aa = np.asarray(_xv, dtype=float)\n'
       '                _bb = np.asarray(_yv, dtype=float)\n'
       '                _mm = ~(np.isnan(_aa) | np.isnan(_bb))\n'
       '                _rho = (float(np.corrcoef(_aa[_mm], _bb[_mm])[0, 1])\n'
       '                        if _mm.sum() > 2 else 0.0)')
assert OLD in s, "no anchor"
NEW = ('                _rho = _rho2(_xv, _yv)')
s = s.replace(OLD, NEW, 1)

# 模块级加纯 Python 的 _rho2
if "def _rho2(" not in s:
    m = __import__("re").search(r"\ndef main\(", s)
    assert m, "no main"
    H = ('\n\ndef _rho2(a, b):\n'
         '    """Pearson 相关，纯 Python（gate 不依赖 numpy）。"""\n'
         '    pr = [(x, y) for x, y in zip(a, b)\n'
         '          if x is not None and y is not None]\n'
         '    n = len(pr)\n'
         '    if n < 3:\n'
         '        return 0.0\n'
         '    mx = sum(p[0] for p in pr) / n\n'
         '    my = sum(p[1] for p in pr) / n\n'
         '    sxx = sum((p[0] - mx) ** 2 for p in pr)\n'
         '    syy = sum((p[1] - my) ** 2 for p in pr)\n'
         '    sxy = sum((p[0] - mx) * (p[1] - my) for p in pr)\n'
         '    if sxx <= 0 or syy <= 0:\n'
         '        return 0.0\n'
         '    return sxy / (sxx * syy) ** 0.5\n')
    s = s[:m.start()] + H + s[m.start():]

ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  改用纯 Python _rho2")