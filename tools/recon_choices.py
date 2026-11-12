import json
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(HERE, "schema.json"), encoding="utf-8"))
print("  === 带 choices 的参数（这就是可选能力）===")
seen = set()
for name, c in d["commands"].items():
    for an, spec in (c.get("args") or {}).items():
        ch = spec.get("choices")
        if ch and an not in seen:
            seen.add(an)
            print("    %-14s %s" % (an, ch))
print()
print("  === 全局参数里的 choices ===")
for an, spec in (d.get("global_args") or {}).items():
    ch = spec.get("choices")
    if ch:
        print("    %-14s %s" % (an, ch))