import json
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(HERE, "schema.json"), encoding="utf-8"))
print("  每个命令实际读取的参数（前 8 个）：")
for name, c in d["commands"].items():
    args = list((c.get("args") or {}).keys())
    print("    %-10s (%2d) %s" % (name, len(args), ", ".join(args[:8])))