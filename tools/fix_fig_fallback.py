import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mmkit.py")
s = open(P, encoding="utf-8").read()
OLD = ('    for d in (os.path.join(base, "fig"), base,\n'
       '              os.path.join(os.path.dirname(os.path.abspath(__file__)),\n'
       '                           "out", "fig")):')
NEW = ('    # 只在本题自己的目录里找图。原来还有第三个兜底\n'
       '    # out/fig —— 那是仓库里默认那道题的图，结果别的题会引用\n'
       '    # ../../fig/box.pdf 这种路径：图是热沉的箱线图，论文讲的是\n'
       '    # 销量预测。缺图就不显示那一节，比放错图好。\n'
       '    for d in (os.path.join(base, "fig"), base):')
assert OLD in s, "no fallback block"
s = s.replace(OLD, NEW, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  removed cross-problem figure fallback")