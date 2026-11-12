import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mmkit.py")
s = open(P, encoding="utf-8").read()
OLD = ('                        if _rp.get("converged"):\n'
       '                            print(f"    收敛：{_rp.get(\'reason\')}")\n'
       '                        # 冷启动实测：出稿成功但一张图都没有，\n'
       '                        # 而输出里不提这事。给一条能直接复制的命令。\n'
       '                        _fh = _fig_hint(ctx, data_path, yname,\n'
       '                                         xnames, mins)\n'
       '                        if _fh:\n'
       '                            print(_fh)')
assert OLD in s, "no anchor"
NEW = ('                        if _rp.get("converged"):\n'
       '                            print(f"    收敛：{_rp.get(\'reason\')}")\n'
       '                    # 冷启动实测：出稿成功但一张图都没有，而输出里不提。\n'
       '                    # 给一条能直接复制的命令。注意缩进 —— 它不属于\n'
       '                    # 「收敛」分支，否则没收敛时就不提示了。\n'
       '                    _fh = _fig_hint(ctx, data_path, yname,\n'
       '                                    xnames, mins)\n'
       '                    if _fh:\n'
       '                        print(_fh)')
s = s.replace(OLD, NEW, 1)
ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  hint moved out of the converged branch")