import json
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cfg = json.load(open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
for k, v in cfg.items():
    print("  %-18s data=%-26s y=%-14s x=%s"
          % (k, str(v.get("data")), str(v.get("y"))[:14],
             str(v.get("x"))[:30]))