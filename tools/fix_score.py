import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "aitaste.py")
s = open(P, encoding="utf-8").read()
OLD = "        score += _WG_SEV.get(r.get(\"severity\", \"low\"), 2)"
assert OLD in s, "no score line"
NEW = ("        # maxHits 是原作者设的容忍线：没超过就不该扣分。\n"
       "        # 原来只看 severity，于是 rather-than 63 处（容忍线 99）\n"
       "        # 也照样扣 4 分 —— 那不是诊断，是误报。\n"
       "        _cap = r.get(\"maxHits\", 99)\n"
       "        if n > _cap:\n"
       "            score += _WG_SEV.get(r.get(\"severity\", \"low\"), 2)")
s = s.replace(OLD, NEW, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  score now respects maxHits")