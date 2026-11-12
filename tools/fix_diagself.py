import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mmkit.py")
s = open(P, encoding="utf-8").read()

OLD = ('        rows = []\n'
       '        for yc in ys:\n'
       '            r = mm.diag_report(ds, yc, _xs)')
assert OLD in s, "no anchor"
NEW = ('        rows = []\n'
       '        for yc in ys:\n'
       '            # y 若同时出现在 --x 里（用户把目标也当解释变量），\n'
       '            # 设计矩阵共线，diag_report 返回空 —— 整节残差诊断\n'
       '            # 就静默消失。剔除自身再算。实测 review_microwave\n'
       '            # 的 --min 含 star_rating 而 --x 也有它，一行都没出。\n'
       '            _xs_y = [c for c in _xs if c != yc]\n'
       '            if not _xs_y:\n'
       '                continue\n'
       '            r = mm.diag_report(ds, yc, _xs_y)')
s = s.replace(OLD, NEW, 1)
s = s.replace('                r["x_en"] = [_paper.describe(c)[0] if _paper.describe(c) else c\n'
              '                             for c in _xs]',
              '                r["x_en"] = [_paper.describe(c)[0] if _paper.describe(c) else c\n'
              '                             for c in _xs_y]')
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  _diag_ctx 剔除 y 自身")