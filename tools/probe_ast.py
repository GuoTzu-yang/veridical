import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tree = ast.parse(open(os.path.join(HERE, "paper.py"), encoding="utf-8").read())

func = None
for n in ast.walk(tree):
    if isinstance(n, ast.FunctionDef) and n.name == "build":
        func = n
        break
print("  build() 行数:", func.end_lineno - func.lineno)

lits = []
for node in ast.walk(func):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        v = node.value
        if len(v) >= 25 and v.isascii() and not v.startswith("\\"):
            lits.append((node.lineno, v))
print("  固定英文长句: %d 条" % len(lits))
print()
for ln, v in sorted(lits)[:20]:
    print("  %5d  %s" % (ln, v[:92]))