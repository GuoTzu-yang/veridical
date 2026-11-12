import json
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(HERE, "schema.json"), encoding="utf-8"))
print("  顶层键: %s" % list(d.keys()))
cmds = d.get("commands") or d.get("subcommands") or {}
if isinstance(cmds, dict):
    print("  共 %d 个子命令：" % len(cmds))
    for k, v in cmds.items():
        desc = ""
        if isinstance(v, dict):
            desc = str(v.get("summary") or v.get("help") or v.get("desc") or "")[:56]
        print("    %-12s %s" % (k, desc))