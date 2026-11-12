import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mmkit.py")
s = open(P, encoding="utf-8").read()
OLD = ('def _emit(obj):\n'
       '    """JSON 输出：始终写真正的 stdout，不受 --json 重定向影响。"""\n'
       '    print(json.dumps(obj, ensure_ascii=False, indent=2,\n'
       '                      default=str), file=sys.__stdout__)')
assert OLD in s, "no _emit"
NEW = ('def _emit(obj):\n'
       '    """JSON 输出：始终写真正的 stdout，不受 --json 重定向影响。\n'
       '\n'
       '    入参可能是对象，也可能是已经 dumps 过的字符串（调用点两种都有）；\n'
       '    对字符串再 dumps 一次会得到转义后的一长串，所以先判类型。\n'
       '    """\n'
       '    if isinstance(obj, str):\n'
       '        print(obj, file=sys.__stdout__)\n'
       '    else:\n'
       '        print(json.dumps(obj, ensure_ascii=False, indent=2,\n'
       '                         default=str), file=sys.__stdout__)')
s = s.replace(OLD, NEW, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  _emit 已兼容字符串")