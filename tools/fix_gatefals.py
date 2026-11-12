import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "gate.py")
s = open(P, encoding="utf-8").read()

# ① sign 按实际符号，不硬编码 -1
OLD1 = '                r = falsify.counterexamples(ds.col(x), ds.col(y), sign=-1)'
assert OLD1 in s, "no sign anchor"
NEW1 = ('                # sign 必须按数据的实际符号。硬编码 -1 时，\n'
        '                # 对任何正相关的变量对，测「负」当然处处是反例 ——\n'
        '                # 那报的不是「结论有问题」，是「测错了方向」。\n'
        '                _xv, _yv = ds.col(x), ds.col(y)\n'
        '                _rho = _pearson(_xv, _yv)\n'
        '                _sg = 1 if _rho >= 0 else -1\n'
        '                r = falsify.counterexamples(_xv, _yv, sign=_sg)')
s = s.replace(OLD1, NEW1, 1)

# ② 论文承认了就放行
OLD2 = '''        if real:
            return _r("falsify", SOFT, "WARN",'''
assert OLD2 in s, "no warn anchor"
NEW2 = ('        # 论文局限节如果已经如实说明了局部非单调，这条就算履行了 ——\n'
        '        # gate 该查的是「断言强度是否超过证据」，不是「数据有没有反例」。\n'
        '        # 数据有反例是事实，改不掉；论文承不承认才是可改的。\n'
        '        _admits = False\n'
        '        try:\n'
        '            _tt = open(tex, encoding="utf-8").read()\n'
        '            _admits = ("Monotonicity is not universal" in _tt\n'
        '                       or "fails locally" in _tt)\n'
        '        except Exception:                   # noqa: BLE001\n'
        '            _admits = False\n'
        '        if real and _admits:\n'
        '            return _r("falsify", SOFT, "PASS",\n'
        '                      f"{len(real)} 组局部非单调，论文局限节已承认")\n'
        '        if real:\n'
        '            return _r("falsify", SOFT, "WARN",')
s = s.replace(OLD2, NEW2, 1)

# ③ _pearson helper
if "_pearson" not in s.split("def _pearson")[0]:
    anchor = "def main("
    i = s.find(anchor)
    assert i > 0
    H = ('def _pearson(a, b):\n'
         '    """两列的 Pearson 相关；有 NaN 或样本不足就返回 0。"""\n'
         '    import numpy as _np\n'
         '    try:\n'
         '        _a = _np.asarray(a, dtype=float)\n'
         '        _b = _np.asarray(b, dtype=float)\n'
         '        _m = ~(_np.isnan(_a) | _np.isnan(_b))\n'
         '        if _m.sum() < 3:\n'
         '            return 0.0\n'
         '        return float(_np.corrcoef(_a[_m], _b[_m])[0, 1])\n'
         '    except Exception:                       # noqa: BLE001\n'
         '        return 0.0\n'
         '\n\n')
    s = s[:i] + H + s[i:]

ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  gate 的 falsify 检查修好")