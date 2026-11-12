import os
import sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import aitaste
for name in ("age_struct", "heat_sink", "prediction"):
    p = os.path.join(HERE, "out", "runs", name, "paper.tex")
    if not os.path.exists(p):
        continue
    r = aitaste.analyze(open(p, encoding="utf-8").read())
    print("  === %s: %s 分 / %s / %s 词 ==="
          % (name, r.get("score"), r.get("grade"), r.get("body_words")))
    for c in (r.get("checks") or []):
        if isinstance(c, dict):
            print("    %-26s %s  %s"
                  % (str(c.get("name"))[:26], c.get("score"),
                     str(c.get("note"))[:40]))
    print()