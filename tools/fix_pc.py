import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "falsify.py")
s = open(P, encoding="utf-8").read()
OLD = ('            pc = mm.partial_corr(ds, a.y, a.x, [o])\n'
       '            if pc.get("r") is not None:\n'
       '                pcs.append((o, pc["r"]))')
assert OLD in s, "no anchor"
NEW = ('            pc = mm.partial_corr(ds, a.y, a.x, [o])\n'
       '            # partial_corr 可能返回 dict，也可能是带属性的对象；\n'
       '            # 只写 pc.get(...) 会 AttributeError，整段对照静默失效。\n'
       '            _r = (pc.get("r") if isinstance(pc, dict)\n'
       '                  else getattr(pc, "r", None))\n'
       '            if _r is not None:\n'
       '                pcs.append((o, _r))')
s = s.replace(OLD, NEW, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  偏相关对照修好")