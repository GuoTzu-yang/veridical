import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "orchestrate.py")
s = open(P, encoding="utf-8").read()

OLD = '''            method_args={"--data": data, "--y": y, "--x": xj,
                         "--no-gate": True},
            success_criteria={"n_rows_min": 1},'''
assert OLD in s, "no B anchor"
NEW = '''            method_args={"--data": data, "--y": y, "--x": xj,
                         "--json": True, "--no-gate": True},
            # 判据只表达「算出了有效数值」，不表达「质量好不好」——
            # 质量由循环里的最优比较决定。_flatten_metrics 只拍平数值
            # 字段，n_rows 提不出来，所以判据必须落在 rmse 上。
            success_criteria={"cv_rmse_max": 1e9},'''
s = s.replace(OLD, NEW, 1)

s = s.replace('''                         "--maximize": True, "--json": True},
            success_criteria={"n_rows_min": 1},''',
              '''                         "--maximize": True, "--json": True},
            success_criteria={"cv_rmse_max": 1e9},''', 1)

s = s.replace('''                         "--horizon": 5, "--json": True},
            success_criteria={"n_rows_min": 1},''',
              '''                         "--horizon": 5, "--json": True},
            success_criteria={"cv_rmse_max": 1e9},''', 1)

ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  判据已统一到 cv_rmse_max")