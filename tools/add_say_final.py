import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mmkit.py")
s = open(P, encoding="utf-8").read()
if "def _say(" not in s:
    OLD = "def _emit(obj):"
    assert OLD in s
    NEW = ('def _say(*a, **kw):\n'
           '    """提示输出。\n'
           '\n'
           '    --json 时 main() 已经把 sys.stdout 指到 stderr，所以这里\n'
           '    只要普通 print 就会走 stderr；JSON 另由 _emit 写真 stdout。\n'
           '    """\n'
           '    print(*a, **kw)\n'
           '\n'
           '\n'
           'def _emit(obj):')
    s = s.replace(OLD, NEW, 1)
    ast.parse(s); compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  _say 已补")
else:
    print("  _say 已存在")