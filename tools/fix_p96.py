import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()
OLD = "    if 'zip(en[\"sections\"]' in p:\n        bad.append('sections zip still there (second mechanism)')"
assert OLD in s, "no anchor"
NEW = ("    if 'zip(en' in p and 'sections' in p.split('zip(en')[1][:80]:\n"
       "        bad.append('sections zip still there (second mechanism)')")
s = s.replace(OLD, NEW, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  fixed P96 judgement")