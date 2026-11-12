import json
import os
import sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import aitaste

cfg = json.load(open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
rows = []
for name, c in cfg.items():
    p = os.path.join(HERE, c["out"], "paper.tex")
    if not os.path.exists(p):
        continue
    r = aitaste.analyze(open(p, encoding="utf-8").read())
    rows.append((r["score"], name, r["grade"]))
rows.sort()
print("  AI 味指数（越低越好）—— 22 道题：")
for sc, n, g in rows:
    bar = "#" * max(1, sc // 5)
    print("    %-18s %3d  %-4s %s" % (n, sc, g, bar[:20]))
print()
ok = sum(1 for r in rows if r[0] < 50)
print("  及格（< 50）: %d/%d" % (ok, len(rows)))
print("  优秀（< 20）: %d/%d" % (sum(1 for r in rows if r[0] < 20), len(rows)))