import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mmkit.py")
s = open(P, encoding="utf-8").read()
OLD = ('            _paras = [p.strip() for p in _t.split("\\n\\n")\n'
       '                      if p.strip() and not p.strip().startswith("\\\\")\n'
       '                      and len(p.strip()) > 120]')
assert OLD in s, "no anchor"
NEW = ('            _paras = [p.strip() for p in _t.split("\\n\\n")\n'
       '                      if p.strip()\n'
       '                      and not p.strip().startswith(("\\\\", "%"))\n'
       '                      and "\\\\begin{" not in p and "\\\\end{" not in p\n'
       '                      and len(p.strip()) > 120]')
s = s.replace(OLD, NEW, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  过滤注释/环境块")