import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "gate.py")
s = open(P, encoding="utf-8").read()
OLD = '        r = figcheck.audit_dir(figdir, stext, only=only)'
assert OLD in s, "no audit_dir"
NEW = ('        # 图可能在 figdir 根（默认题）也可能在 figdir/fig（别的题）。\n'
       '        # 只扫根目录会让后者的 figures 检查报「没有 PNG」。\n'
       '        _fd = figdir\n'
       '        _sub = os.path.join(figdir, "fig")\n'
       '        if os.path.isdir(_sub) and any(\n'
       '                x.lower().endswith((".png", ".pdf"))\n'
       '                for x in os.listdir(_sub)):\n'
       '            _fd = _sub\n'
       '        r = figcheck.audit_dir(_fd, stext, only=only)')
s = s.replace(OLD, NEW, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  chk_figures now looks in fig/ subdir too")