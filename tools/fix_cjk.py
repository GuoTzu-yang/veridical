import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mmkit.py")
s = open(P, encoding="utf-8").read()
OLD = ('        if _lang_now.startswith("en"):\n'
       '            if _re_cjk.search(tex):\n'
       '                tex = _re_cjk.sub("variable", tex)')
assert OLD in s, "no anchor"
NEW = ('        if _lang_now.startswith("en"):\n'
       '            if _re_cjk.search(tex):\n'
       '                tex = _re_cjk.sub("variable", tex)\n'
       '            # 全角标点也必须换掉：把中文列名「针肋宽度比（m）」替成\n'
       '            # variable 之后，括号还是全角 U+FF08 —— pdfLaTeX 直接报\n'
       '            # "Unicode character （ not set up"（实测 4 处错误）。\n'
       '            for _a, _b in (("（", "("), ("）", ")"), ("，", ", "),\n'
       '                           ("：", ": "), ("；", "; "), ("、", ", "),\n'
       '                           ("～", "~"), ("－", "-"), ("　", " ")):\n'
       '                if _a in tex:\n'
       '                    tex = tex.replace(_a, _b)')
s = s.replace(OLD, NEW, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  全角标点已加入总闸")