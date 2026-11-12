import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()

OLD = ('    L.append(r"  \\item The structural choice reported in "\n'
       '             r"Section~\\ref{sec:selection} was checked against the "\n'
       '             r"cross-validated errors, not against a preference.")')
assert OLD in s, "no anchor"
NEW = ('    # \\label{sec:selection} 只在 multimodel 非空时生成（那节讲\n'
       '    # 「一个指标一种形式」）。列数太少时那节不存在，这里再写\n'
       '    # Section~\\ref 就编成 "Section??" —— 实测 review_microwave\n'
       '    # 只有 3 个可用数值列，就踩了这个。\n'
       '    _has_sel = bool((ctx.get("multimodel") or {}).get("rows"))\n'
       '    L.append(r"  \\item The structural choice reported in "\n'
       '             + (r"Section~\\ref{sec:selection}" if _has_sel\n'
       '                else "the alternative specifications")\n'
       '             + r" was checked against the cross-validated errors, "\n'
       '             r"not against a preference.")')
s = s.replace(OLD, NEW, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  sec:selection ref now conditional")