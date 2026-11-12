import ast
import os
import re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mmkit.py")
s = open(P, encoding="utf-8").read()

# ① 加 _say（放在 imports 之后、第一个 def 之前）
if "def _say(" not in s:
    m = re.search(r"\n(def |class )", s)
    assert m
    HELP = ('\n# --json 模式下所有提示走 stderr，stdout 只留 JSON。\n'
            '# 不做这件事，LLM 解析前得先剥皮；剥皮逻辑一脆就会退回\n'
            '# 「直接 run 一条龙」，插件能力全被绕过。\n'
            '_JSON_MODE = [False]\n\n\n'
            'def _say(*a, **kw):\n'
            '    """提示输出。--json 时改走 stderr。"""\n'
            '    if _JSON_MODE[0] and "file" not in kw:\n'
            '        kw["file"] = sys.stderr\n'
            '    print(*a, **kw)\n\n')
    s = s[:m.start()] + HELP + s[m.start():]

# ② 只替换「标题栏 / 项目符号」类提示
lines = s.splitlines()
n = 0
PAT = re.compile(r'print\((?=f?["\'](?:\s|=|-|·|\u00b7))')
for k, ln in enumerate(lines):
    if ln.lstrip().startswith("#") or "print(json.dumps" in ln:
        continue
    new = PAT.sub("_say(", ln)
    if new != ln:
        lines[k] = new
        n += 1
s = "\n".join(lines) + "\n"

# ③ main 里设置模式
if "_JSON_MODE[0] = " not in s:
    m = re.search(r"(\n\s+)(\w+) = ap\.parse_args\(", s)
    assert m, "no parse_args"
    s = (s[:m.end()] + "\n" + m.group(1) + "_JSON_MODE[0] = bool(getattr("
         + m.group(2) + ', "json", False))' + s[m.end():])

ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  _say 就位；替换 %d 行提示" % n)