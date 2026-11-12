import ast
import os
import re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mmkit.py")
s = open(P, encoding="utf-8").read()

if "def _say(" not in s:
    # 锚点：最后一个顶层 import 之后
    lines = s.splitlines()
    last_imp = 0
    for k, ln in enumerate(lines):
        if re.match(r"^(import |from \S+ import )", ln):
            last_imp = k
    HELP = ["",
            "# --json 模式下所有提示走 stderr，stdout 只留 JSON。",
            "# 不做这件事，LLM 解析前得先剥皮；剥皮逻辑一脆就会退回",
            "# 「直接 run 一条龙」，插件能力全被绕过。",
            "_JSON_MODE = [False]",
            "",
            "",
            "def _say(*a, **kw):",
            '    """提示输出。--json 时改走 stderr。"""',
            '    if _JSON_MODE[0] and "file" not in kw:',
            '        kw["file"] = sys.stderr',
            "    print(*a, **kw)",
            ""]
    lines[last_imp + 1:last_imp + 1] = HELP
    s = "\n".join(lines) + "\n"

# 只替换标题栏/项目符号类提示
lines = s.splitlines()
n = 0
PAT = re.compile(r'print\((?=f?["\'](?:\s|=|-|\u00b7))')
for k, ln in enumerate(lines):
    if ln.lstrip().startswith("#") or "print(json.dumps" in ln:
        continue
    new = PAT.sub("_say(", ln)
    if new != ln:
        lines[k] = new
        n += 1
s = "\n".join(lines) + "\n"

if "_JSON_MODE[0] = " not in s:
    m = re.search(r"(\n\s+)(\w+) = ap\.parse_args\(", s)
    assert m, "no parse_args"
    s = (s[:m.end()] + "\n" + m.group(1) + "_JSON_MODE[0] = bool(getattr("
         + m.group(2) + ', "json", False))' + s[m.end():])

ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  _say 在 import 之后；替换 %d 行" % n)