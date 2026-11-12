import os
import sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import aitaste
t = open(os.path.join(HERE, "out", "runs", "age_struct", "paper.tex"),
         encoding="utf-8").read()
r = aitaste.score(t)
print("  总分: %s/100" % r.get("score"))
items = r.get("items") or []
print("  条目 %d 个：" % len(items))
for it in sorted(items, key=lambda x: -(x.get("penalty") or 0))[:10]:
    print("    [%s] %-30s 扣 %-4s %s"
          % (it.get("level", "?"), str(it.get("rule"))[:30],
             it.get("penalty"), str(it.get("detail"))[:50]))