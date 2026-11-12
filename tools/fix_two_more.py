import ast
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()

PAIRS = [
    ("_tpath", "tornado", "0.70\\textwidth"),
    ("_cp", "cand", "0.70\\textwidth"),
]
for var, kind, width in PAIRS:
    # 老式：_tpath = os.path.join(...); if os.path.exists(_tpath):
    old_assign = re.compile(
        r'\n(\s*)' + var + r' = os\.path\.join\(os\.path\.dirname\('
        r'os\.path\.abspath\(__file__\)\),\s*\n\s*"out", "fig", "'
        + kind + r'\.pdf"\)\s*\n')
    m = old_assign.search(s)
    if m:
        ind = m.group(1)
        new = (m.group(0).rstrip("\n") .replace(
            'os.path.join(os.path.dirname(os.path.abspath(__file__)),',
            '(ctx.get("figures") or {}).get("' + kind + '") or "" #')
            + "\n")
        # 更简单：直接替换整段赋值
        simple = ("\n" + ind + "# 用当前题的图。原来硬编码 <repo>/out/fig/"
                  + kind + ".pdf，\n"
                  + ind + "# 换个目录跑就没有这一节。\n"
                  + ind + var + ' = (ctx.get("figures") or {}).get("'
                  + kind + '")\n')
        s = s[:m.start()] + simple + s[m.end():]
    # 条件
    s = s.replace("if os.path.exists(" + var + "):",
                  "if " + var + ":")
    # includegraphics
    s = re.sub(r'\\includegraphics\[width=0\.70\\textwidth\]\{'
               + kind + r'\.pdf\}',
               '\\\\includegraphics[width=0.70\\\\textwidth]{" + '
               + var + ' + "}', s)

ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  patched tornado + cand")
for kind in ("surfaces", "tornado", "cand"):
    still = 'out", "fig", "' + kind in s
    print("  %-10s hardcoded=%s" % (kind, still))