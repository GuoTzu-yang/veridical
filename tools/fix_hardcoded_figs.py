import ast
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()

# 三处硬编码 out/fig/<name>.pdf 改成用 ctx["figures"]
for kind in ("surfaces", "tornado", "cand"):
    pat = re.compile(
        r'(\n\s*)_sp = os\.path\.join\(os\.path\.dirname\(os\.path\.abspath\(__file__\)\),\s*\n'
        r'\s*"out", "fig", "' + kind + r'\.pdf"\)\s*\n'
        r'(\s*)if os\.path\.exists\(_sp\):')
    m = pat.search(s)
    if not m:
        print("  [skip] %s: pattern not found" % kind)
        continue
    indent = m.group(1)[1:]
    body_indent = m.group(2)
    repl = (m.group(1)
            + '# 用当前题的图，不用仓库默认题的。原来这里硬编码了\n'
            + indent + '# <repo>/out/fig/' + kind + '.pdf —— workspace 里有，\n'
            + indent + '# 换个目录跑就没有，于是整节静默消失（残差诊断表\n'
            + indent + '# 就埋在这个分支里）。\n'
            + indent + '_sp = (ctx.get("figures") or {}).get("' + kind + '")\n'
            + body_indent + 'if _sp:')
    s = s[:m.start()] + repl + s[m.end():]

# 把三处 includegraphics{<name>.pdf} 改成用 _sp
for kind in ("surfaces", "tornado", "cand"):
    s = s.replace('\\includegraphics[width=\\textwidth]{' + kind + '.pdf}',
                  '\\includegraphics[width=\\textwidth]{' + '" + _sp + "}')
    s = s.replace('\\includegraphics[width=0.62\\textwidth]{' + kind + '.pdf}',
                  '\\includegraphics[width=0.62\\textwidth]{' + '" + _sp + "}')

ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  patched 3 hardcoded figure paths")

# 检查是否真的改了
for kind in ("surfaces", "tornado", "cand"):
    if 'out", "fig", "' + kind in s:
        print("  [WARN] %s still hardcoded" % kind)