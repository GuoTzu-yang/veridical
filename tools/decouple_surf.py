import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()

OLD = ('        _sp = (ctx.get("figures") or {}).get("surfaces")\n'
       '        if _sp:\n'
       '            L += [r"\\begin{figure}[H]", r"\\centering",\n'
       '                  r"\\includegraphics[width=\\textwidth]{" + _sp + "}",')
assert OLD in s, "no anchor"
NEW = ('        _sp = (ctx.get("figures") or {}).get("surfaces")\n'
       '        # 响应面图是可选内容：单因子题画不出响应面，所以没有这张图。\n'
       '        # 但原来这一层条件把**整节残差诊断**都包在里面 —— 图缺失就\n'
       '        # 连 diag 表格一起消失，required 检查报「缺残差诊断」。\n'
       '        # 实测 real_c2024（单因子）就是这样少了一节。\n'
       '        # 现在只让图自己受 _sp 约束。\n'
       '        if _sp:\n'
       '            L += [r"\\begin{figure}[H]", r"\\centering",\n'
       '                  r"\\includegraphics[width=\\textwidth]{" + _sp + "}",')
s = s.replace(OLD, NEW, 1)

# 把图之后那段的缩进减 4（从 if _sp: 里拉出来）
OLD2 = ('                  r"\\label{fig:surfaces}", r"\\end{figure}"]\n'
        '            L.append("")\n'
        '            # 残差诊断：题目的「评估拟合效果」在残差层面的结论\n'
        '            _dg = ctx.get("diag") or {}')
assert OLD2 in s, "no anchor2"
NEW2 = ('                  r"\\label{fig:surfaces}", r"\\end{figure}"]\n'
        '            L.append("")\n'
        '        # 残差诊断：题目的「评估拟合效果」在残差层面的结论\n'
        '        # （外面这层不再依赖 surfaces 图）\n'
        '        _dg = ctx.get("diag") or {}')
s = s.replace(OLD2, NEW2, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  surfaces 图与残差节解耦")