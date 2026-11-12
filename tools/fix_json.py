import ast
import os
import re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mmkit.py")
s = open(P, encoding="utf-8").read()

# ① 所有 print(json.dumps(...)) 显式写 sys.__stdout__
n = 0
def _fix(m):
    global n
    n += 1
    return m.group(0)[:-1] + ", file=sys.__stdout__)"
s2 = re.sub(r"print\(json\.dumps\([^\n]*\)\)", _fix, s)
print("  JSON 输出加固 %d 处" % n)
s = s2

# ② main 里：--json 时把 stdout 指到 stderr
if "sys.stdout = sys.stderr" not in s:
    m = re.search(r"(\n\s+)(\w+) = ap\.parse_args\(", s)
    assert m, "no parse_args"
    ins = (m.group(1) + "_JSON = bool(getattr(" + m.group(2) + ', "json", False))'
           + "\n" + m.group(1)
           + "# --json 时提示全部走 stderr；JSON 本身显式写 sys.__stdout__。"
           + "\n" + m.group(1)
           + "if _JSON:\n" + m.group(1) + "    sys.stdout = sys.stderr")
    s = s[:m.end()] + ins + s[m.end():]

ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  main 已接 --json 重定向")