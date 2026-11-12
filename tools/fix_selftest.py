import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "verify.py")
s = open(P, encoding="utf-8").read()
OLD = ('    ck("0.0074342 与 0.00743 视为同源",\n'
       '       _near(0.0074342, 0.00743), "精度差异")')
assert OLD in s, "no anchor"
NEW = ('    # 方向很重要：论文里的数是输出里的数的**舍入**才算同源。\n'
       '    # 反过来（论文比输出多写几位）不算 —— 输出不足以确认那几位。\n'
       '    ck("论文是输出的舍入（0.00743 <- 0.0074342）",\n'
       '       _near(0.00743, 0.0074342), "精度差异")')
s = s.replace(OLD, NEW, 1)

# 追加两条反向用例
OLD2 = '    ck("0.5918 与 0.8500 不视为同源", not _near(0.5918, 0.85))'
assert OLD2 in s, "no anchor2"
NEW2 = (OLD2 + '\n'
        '    # 防编造：输出精度比论文低，或同精度但数不同，都不能算同源\n'
        '    ck("论文精度高于输出时不算同源（1.0 不足以确认 0.9999）",\n'
        '       not _near(0.9999, 1.0))\n'
        '    ck("同精度但数不同不算同源（0.9999 vs 0.9975）",\n'
        '       not _near(0.9999, 0.9975))')
s = s.replace(OLD2, NEW2, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  自测已修正 + 加两条防编造用例")