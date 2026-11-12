import ast
import os
import re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mmkit.py")
s = open(P, encoding="utf-8").read()

# ① 把 print(json.dumps( ... )) 整段换成 _emit( ... )（括号计数，支持跨行）
out = []
i = 0
n = 0
while True:
    j = s.find("print(json.dumps(", i)
    if j < 0:
        out.append(s[i:])
        break
    out.append(s[i:j])
    # 定位 print( 的配对右括号
    k = j + len("print(")
    depth = 1
    while k < len(s) and depth:
        if s[k] == "(":
            depth += 1
        elif s[k] == ")":
            depth -= 1
        k += 1
    inner = s[j + len("print("):k - 1]          # json.dumps(...) 全部
    out.append("_emit(" + inner + ")")
    n += 1
    i = k
s = "".join(out)
print("  改写 %d 处 JSON 输出" % n)

# ② 加 _emit
if "def _emit(" not in s:
    lines = s.splitlines()
    last_imp = 0
    for k, ln in enumerate(lines):
        if re.match(r"^(import |from \S+ import )", ln):
            last_imp = k
    HELP = ["",
            "def _emit(obj):",
            '    """JSON 输出：始终写真正的 stdout，不受 --json 重定向影响。"""',
            "    print(json.dumps(obj, ensure_ascii=False, indent=2,",
            '                      default=str), file=sys.__stdout__)',
            ""]
    lines[last_imp + 1:last_imp + 1] = HELP
    s = "\n".join(lines) + "\n"

ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  _emit 就位")