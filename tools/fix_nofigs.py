import ast
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mmkit.py")
s = open(P, encoding="utf-8").read()

if 'add_argument("--no-figs"' not in s:
    A = '    ap.add_argument("--compile", action="store_true",'
    assert A in s, "no compile arg"
    s = s.replace(
        A,
        '    ap.add_argument("--no-figs", action="store_true",\n'
        '                    help="不要自动出图（默认会生成 12 张）")\n' + A, 1)

# 找 run( 调用并加 no_figs
if "no_figs=" not in s.split("def run(")[1].split("def ")[0]:
    m = re.search(r"(\n\s+)(rr\s*=\s*run\(|rep\s*=\s*run\()", s)
    if m:
        start = m.end()
        # 找匹配的右括号
        depth = 1
        i = s.find("(", m.start(2), start)
        i = s.find("(", m.start(2))
        j = i + 1
        while j < len(s) and depth > 0:
            if s[j] == "(":
                depth += 1
            elif s[j] == ")":
                depth -= 1
            j += 1
        seg = s[i:j]
        if "no_figs" not in seg:
            s = s[:j - 1] + ", no_figs=getattr(args, 'no_figs', False)" + s[j - 1:]
            print("  wired no_figs into run call")
    else:
        print("  run call not found by regex")

ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  done")