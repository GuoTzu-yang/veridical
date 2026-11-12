import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()
OLD = ('    ctx["_tex_lower"] = tex.lower()\n'
       '    tex = tex + "\\n" + "\\n".join(_claim_ledger(ctx))\n')
assert OLD in s, "no old block"
NEW = ('    ctx["_tex_lower"] = tex.lower()\n'
       '    _led = "\\n".join(_claim_ledger(ctx))\n'
       '    # 必须插在 \\end{document} **之前** —— 直接追加到 tex 末尾会落在\n'
       '    # \\end{document} 之后，pdflatex 不渲染（实测：tex 里有、PDF 里没有）。\n'
       '    if "\\\\end{document}" in tex:\n'
       '        tex = tex.replace("\\\\end{document}",\n'
       '                          _led + "\\n\\\\end{document}", 1)\n'
       '    else:\n'
       '        tex = tex + "\\n" + _led\n')
s = s.replace(OLD, NEW, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  fixed end{document}")