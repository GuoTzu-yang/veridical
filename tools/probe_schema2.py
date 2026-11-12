import json
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(HERE, "schema.json"), encoding="utf-8"))
print("  n_commands=%s  n_declared_args=%s" % (d.get("n_commands"),
                                               d.get("n_declared_args")))
print("  note: %s" % str(d.get("note"))[:120])
print("  metrics: %s" % str(d.get("metrics"))[:160])
print()
for name in ("race", "solve", "forecast"):
    c = d["commands"].get(name) or {}
    print("  === %s ===" % name)
    print("    键: %s" % list(c.keys()))
    print("    内容: %s" % json.dumps(c, ensure_ascii=False)[:340])
    print()