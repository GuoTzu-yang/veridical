import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mmkit.py")
s = open(P, encoding="utf-8").read()

# 在 gate 调用之后（或 run 末尾）插入出图提示
NEEDLE = "def _collect_figures("
assert NEEDLE in s, "no anchor"

FUNC = '''

def _fig_hint(ctx, data_path="", yname="", xnames=(), mins=()):
    """没有图时给一条可直接复制执行的命令。

    冷启动实测：run --compile 会生成一篇 400 KB 的 PDF，里面一张图都没有，
    而输出里完全不提出图 —— 用户以为交稿了。图要单独跑 plot。
    """
    if ctx.get("figures"):
        return ""
    xl = data_path or "<数据文件>"
    xs = ",".join(xnames) if xnames else "<x1,x2>"
    ms = ",".join(mins) if mins else "<m1,m2>"
    return ("\\n  提示：还没有图，PDF 里只有正文。生成一套（12 张）：\\n"
            "    python mmkit.py plot --kind hist --data %s --y %s "
            "--x %s --min %s --out-png out/fig/hist\\n"
            "  其余 kind：box corr resid qq pred sens cand tornado "
            "surfaces pareto flow（同样参数，换 --kind 与输出名）"
            % (xl, yname or "<y>", xs, ms))


'''
s = s.replace(NEEDLE, FUNC.lstrip("\n") + NEEDLE, 1)

# 调用点：在 run 打印结束时
CALL = "    return 0"
if "from __future__" in s:
    pass
ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  added _fig_hint")