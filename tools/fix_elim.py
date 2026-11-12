import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "tools", "final_bounds.py")
s = open(P, encoding="utf-8").read()
OLD = '''    g = g[g.exw >= g.week]
    if len(g) < 3 or g.plc.isna().any():
        return None
    g = g.sort_values("plc").reset_index(drop=True)
    J = g.judge_score.values.astype(float)
    n = len(J)
    Jn = (J - J.min()) / (J.max() - J.min()) if J.max() > J.min() else np.zeros(n)
    elim = int(np.where(g.eliminated.values == 1)[0][0])
    if n < 3:
        return None'''
assert OLD in s, "no anchor"
NEW = '''    # 先记下淘汰者的名字，再过滤 —— 否则 exitw 映射不到时
    # NaN 比较为 False，淘汰者会被过滤掉，索引越界。
    elim_names = g.loc[g.eliminated == 1, "celebrity_name"].tolist()
    if len(elim_names) != 1:
        return None
    elim_name = elim_names[0]
    g = g[g.exw >= g.week].copy()
    if len(g) < 3 or g.plc.isna().any() or elim_name not in set(g.celebrity_name):
        return None
    g = g.sort_values("plc").reset_index(drop=True)
    J = g.judge_score.values.astype(float)
    n = len(J)
    Jn = (J - J.min()) / (J.max() - J.min()) if J.max() > J.min() else np.zeros(n)
    elim = int(np.where(g.celebrity_name.values == elim_name)[0][0])
    if n < 3:
        return None'''
s = s.replace(OLD, NEW, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  修了 elim 索引")