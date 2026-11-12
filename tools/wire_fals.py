import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mmkit.py")
s = open(P, encoding="utf-8").read()

# 找 ctx = dict( ... ) 的结束（下一行是 tex = _paper.build 之前的 _ov 块）
anchor = "        # LLM 写的正文：按「原文前 40 字」注入"
assert anchor in s, "no anchor"
INS = '''        # ── 主动证伪：每条「X 与 y 同向」的主张，局部站不站得住 ──
        # falsify.counterexamples 会滑窗找区间内符号相反的反例；
        # 论文据此决定这条结论该写成结论还是写成局限。
        # 原来 paper.py 完全不知道 falsify（0 次引用），
        # 于是 gate 报「3 组边际反例仍矛盾」，论文照旧把它写成结论。
        _fal = {}
        try:
            import falsify as _fl
            _yv = ds.col(ycol)
            for _x in xs:
                try:
                    _xv = ds.col(_x)
                    _rho = mm.pearson(_xv, _yv)
                    _sg = 1 if (_rho or 0) >= 0 else -1
                    _r = _fl.counterexamples(_xv, _yv, sign=_sg)
                    _fal[_x] = dict(
                        ok=bool(_r.get("ok")),
                        n=int(_r.get("n") or 0),
                        n_violating=int(_r.get("n_violating") or 0),
                        sign=_sg,
                        segs=[(round(s2.get("start"), 2),
                               round(s2.get("end"), 2),
                               round(s2.get("rho"), 3))
                              for s2 in (_r.get("segments") or [])[:3]])
                except Exception:                   # noqa: BLE001
                    continue
        except Exception:                           # noqa: BLE001
            _fal = {}
        ctx["falsify"] = _fal

'''
s = s.replace(anchor, INS + anchor, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  falsify 结果已进 ctx")