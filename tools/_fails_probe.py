"""逐题列出 gate 的非 PASS 项（给 meta_eval 调用；独立成文件，避免嵌套转义）。"""
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.chdir(HERE)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import gate  # noqa: E402

cfg = json.load(open("runs.json", encoding="utf-8"))
out = {}
for name, it in cfg.items():
    d = it["out"]
    if not os.path.exists(os.path.join(d, "paper.tex")):
        continue
    r = gate.run_all(d)
    out[name] = [[c["id"], c["status"], c.get("na_kind")]
                 for c in r["checks"] if c["status"] != "PASS"]
print(json.dumps(out, ensure_ascii=False))
