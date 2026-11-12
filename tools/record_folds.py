import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mm.py")
s = open(P, encoding="utf-8").read()
OLD = "    cv_rmse = float(np.sqrt(np.concatenate(errs) ** 2 .mean()))"
if OLD not in s:
    OLD = "    cv_rmse = float(np.sqrt(np.concatenate(errs) ** 2 .mean()))".replace(" 2 .", " ** 2).")
# 找到实际那行
import re
m = re.search(r"^\s*cv_rmse = .*$", s, re.M)
assert m, "no cv_rmse line"
line = m.group(0)
NEW = (line + "\n"
       "    # 每折 RMSE：仿真题要报「重复次数与收敛」，而交叉验证的每一折\n"
       "    # 就是一次重复。不记下来的话 paper.py 只能编标准误 —— 那不行。\n"
       "    _fold_rmse = [float(np.sqrt((e ** 2).mean())) for e in errs]\n"
       "    _fold_cv = float(np.std(_fold_rmse, ddof=1) / max(\n"
       "        np.mean(_fold_rmse), 1e-12)) if len(_fold_rmse) > 1 else 0.0")
s = s.replace(line, NEW, 1)
ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  recorded per-fold rmse")
print("  cv_k:", "cv_k" in s, " _fold_rmse:", "_fold_rmse" in s)