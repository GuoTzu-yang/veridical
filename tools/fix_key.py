import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FIX_MAP = (
 'place = dict(zip(W.celebrity_name, W.placement))\n'
 'exitw = dict(zip(W.celebrity_name, np.where(W.eliminated_week > 0,\n'
 '                                            W.eliminated_week, W.last_week)))',
 'W["_k"] = list(zip(W.season, W.celebrity_name))\n'
 'place = dict(zip(W["_k"], W.placement))\n'
 'exitw = dict(zip(W["_k"], np.where(W.eliminated_week > 0,\n'
 '                                     W.eliminated_week, W.last_week)))\n'
 'L["_k"] = list(zip(L.season, L.celebrity_name))'
)
FIX_USE = (
 'g["plc"] = g.celebrity_name.map(place)\n'
 '    g["exw"] = g.celebrity_name.map(exitw)',
 'g["plc"] = g["_k"].map(place)\n'
 '    g["exw"] = g["_k"].map(exitw)'
)
FIX_USE2 = (
 'gg["plc"] = gg.celebrity_name.map(place)\n'
 '    gg["exw"] = gg.celebrity_name.map(exitw)',
 'gg["plc"] = gg["_k"].map(place)\n'
 '    gg["exw"] = gg["_k"].map(exitw)'
)

for fn in ("tools/final_bounds.py", "tools/feas_closed.py"):
    p = os.path.join(HERE, fn)
    if not os.path.exists(p):
        continue
    s = open(p, encoding="utf-8").read()
    ch = 0
    for a, b in (FIX_MAP, FIX_USE, FIX_USE2):
        if a in s:
            s = s.replace(a, b); ch += 1
    ast.parse(s); compile(s, p, "exec")
    open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("  %s: 改 %d 处" % (fn, ch))