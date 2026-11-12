import json
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(HERE, "runs.json")
cfg = json.load(open(p, encoding="utf-8"))
cfg["dwts2026c"] = {
    "data": "dwts2026c.xlsx",
    "y": "placement",
    "x": "judge_avg,age,n_weeks",
    "min": "",
    "problem": "2026 MCM Problem C - Dancing with the Stars fan-vote reconstruction",
    "out": "out/d2026c",
}
json.dump(cfg, open(p, "w", encoding="utf-8", newline="\n"),
          ensure_ascii=False, indent=1)
print("  runs.json 现有 %d 道题，新增 dwts2026c" % len(cfg))