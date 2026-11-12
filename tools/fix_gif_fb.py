import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mmkit.py")
s = open(P, encoding="utf-8").read()
OLD = ('        fig_dirs = [outdir, os.path.join(outdir, "fig"),\n'
       '                    os.path.join(os.path.dirname(os.path.abspath(__file__)),\n'
       '                                 "out", "fig")]')
assert OLD in s, "no gif fallback"
NEW = ('        # 第三个目录原本是仓库默认题的 out/fig —— 和 _collect_figures\n'
       '        # 第 44 轮删掉的那个兜底一模一样：换目录跑就从别处借图，\n'
       '        # 而 GIF 里是别人题的图，不报错。\n'
       '        fig_dirs = [outdir, os.path.join(outdir, "fig")]')
s = s.replace(OLD, NEW, 1)
ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  gif fallback removed")