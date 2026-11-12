import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "gate.py")
s = open(P, encoding="utf-8").read()
OLD = ('    if not os.path.exists(p):\n'
       '        return _r("pdf", HARD, "N/A", "没有 paper.pdf")')
assert OLD in s, "no pdf N/A block"
NEW = ('    if not os.path.exists(p):\n'
       '        # PDF 是硬门：没有 PDF 就是没出稿。原来报 N/A，于是\n'
       '        # 只生成 tex 的题也显示「通过」—— 硬门形同虚设。\n'
       '        return _r("pdf", HARD, "FAIL", "没有 paper.pdf，只有 tex 不算出稿")')
s = s.replace(OLD, NEW, 1)
ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  chk_pdf: N/A -> FAIL")