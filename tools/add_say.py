import ast
import os
import re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mmkit.py")
s = open(P, encoding="utf-8").read()

# ① 加 _say
if "def _say(" not in s:
    anchor = "def _re_cjk" if "def _re_cjk" in s else "\ndef main("
    i = s.find(anchor)
    assert i > 0
    HELP = ('\n# --json 模式下，所有提示走 stderr，stdout 只留 JSON。\n'
            '# 不做这件事，LLM 解析前得先剥皮；剥皮逻辑一脆，\n'
            '# 就会退回「直接 run 一条龙」，插件能力全被绕过。\n'
            '_JSON_MODE = [False]\n\n\n'
            'def _say(*a, **kw):\n'
            '    """提示输出。--json 时改走 stderr。"""\n'
            '    if _JSON_MODE[0] and "file" not in kw:\n'
            '        kw["file"] = sys.stderr\n'
            '    print(*a, **kw)\n\n\n')
    s = s[:i] + HELP + s[i:]

# ② 批量替换 print( -> _say(（排除 json.dumps 与注释行）
lines = s.splitlines()
n = 0
for k, ln in enumerate(lines):
    st = ln.lstrip()
    if st.startswith("#"):
        continue
    if "print(json.dumps" in ln or "file=sys.stderr" in ln:
        continue
    if re.search(r"\bprint\(", ln):
        lines[k] = re.sub(r"\bprint\(", "_say(", ln)
        n += 1
s = "\n".join(lines) + "\n"

# ③ main() 里设置模式
if "_JSON_MODE[0] = " not in s:
    m = re.search(r"(\n\s+)a = ap\.parse_args\(", s)
    assert m, "no parse_args"
    ind = m.group(1)
    s = s[:m.end()] + ("\n" + ind + "_JSON_MODE[0] = bool(getattr(a, \"json\", False))") + s[m.end():]

ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  _say 就位；替换 %d 行 print" % n)