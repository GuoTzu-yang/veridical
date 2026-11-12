import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()
OLD = "        return _r.search(r\"\\b\" + _r.escape(pr) + r\"\\b\", tex) is not None"
assert OLD in s, "no boundary line"
NEW = ("        # 左边界 + 前缀：既让词干 probe（feasib -> feasible）能命中，\n"
       "        # 又挡住假阳性（\\bward 不匹配 towards，\\bdual 不匹配 residual）。\n"
       "        # 两端都加 \\b 会把词干匹配废掉 —— 实测 15 条一下全变不命中。\n"
       "        return _r.search(r\"\\b\" + _r.escape(pr), tex) is not None")
s = s.replace(OLD, NEW, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  left-boundary prefix wired")