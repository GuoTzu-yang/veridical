import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()
OLD = ('    xs = ctx.get("xs") or []\n'
       '    sens = ctx.get("sens") or {}\n'
       '    if len(xs) != 1 or (sens.get("rows") or []):\n'
       '        return []')
NEW = ('    # sens 的结构是 {"rmse":..,"base":..,"delta":..,"items":[{shift,..}]}，\n'
       '    # 不是 rows。单因子时 items 只有 1 项。\n'
       '    sens = ctx.get("sens") or {}\n'
       '    items = sens.get("items") or []\n'
       '    if len(items) > 1:\n'
       '        return []          # 多因子：真做得了灵敏度，走正文章节')
assert OLD in s, "no old block"
s = s.replace(OLD, NEW, 1)
ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  judge by sens.items")