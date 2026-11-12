import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for fn in ("tools/battle.py", "tools/verify_all.py"):
    P = os.path.join(HERE, fn)
    s = open(P, encoding="utf-8").read()
    n = 0
    # "通过" in x 会匹配「未通过」—— 子串陷阱
    for old, new in (
        ('ok = ok and ("通过" in g)', 'ok = ok and g.startswith("质量门：通过")'),
        ('good = ok and ("通过" in g)', 'good = ok and g.startswith("质量门：通过")'),
        ('ok = "通过" in s', 'ok = s.startswith("质量门：通过")'),
        ('okn = sum(1 for r in rows if r[1] and "通过" in r[2])',
         'okn = sum(1 for r in rows if r[1] and r[2].startswith("质量门：通过"))'),
        ('bad = [r for r in rows if not (r[1] and "通过" in r[2])]',
         'bad = [r for r in rows\n           if not (r[1] and r[2].startswith("质量门：通过"))]'),
        ('if ok and "通过" in g', 'if ok and g.startswith("质量门：通过")'),
    ):
        if old in s:
            s = s.replace(old, new)
            n += 1
    if n:
        ast.parse(s)
        open(P, "w", encoding="utf-8", newline="\n").write(s)
        print("  %s: 修 %d 处子串陷阱" % (fn, n))
    else:
        print("  %s: 没有裸 \"通过\" in ..." % fn)