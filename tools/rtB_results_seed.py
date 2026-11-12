"""rtB / results board: _close fix shape, test pins, and whether 30/30 is the
first run or the post-fix run. Read-only."""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

print("=== freeze.py _close() ===")
L = open("freeze.py", encoding="utf-8").read().splitlines()
for i in range(303, 332):
    print("%4d %s" % (i + 1, L[i]))

print("\n=== tests/ directory present? ===")
print("  exists:", os.path.isdir("tests"))
if os.path.isdir("tests"):
    print("  files:", os.listdir("tests")[:20])

print("\n=== does the optimisation record say when the seeded benchmark first ran? ===")
rec = open("OPTIMIZATION-优化记录.md", encoding="utf-8").read()
parts = re.split(r"^# 优化记录（第 (\d+) 轮）", rec, flags=re.M)
rounds = [(parts[i], parts[i + 1]) for i in range(1, len(parts), 2)]
KEY = ["种子", "seed", "30/30", "30 个", "首跑", "第一次跑", "基准"]
for rn, body in rounds:
    hits = [k for k in KEY if k in body]
    if hits:
        print("\n  --- round %s  keywords=%s" % (rn, hits))
        for ln in body.splitlines():
            if any(k in ln for k in KEY):
                print("      ", ln.strip()[:170])

print("\n=== any artifact recording a PRE-fix seeded run? ===")
for f in sorted(os.listdir("out/final")):
    if not f.endswith(".json"):
        continue
    t = open(os.path.join("out/final", f), encoding="utf-8", errors="replace").read()
    if re.search(r"first.?run|pre.?fix|before.?fix|30/30", t, re.I):
        print("  ", f, "mentions a first/pre-fix run")

print("\n=== seeded_defects.json: is there a run timestamp / config? ===")
sd = json.load(open("out/final/seeded_defects.json", encoding="utf-8"))
print("  keys:", list(sd.keys()))
print("  any 'when'/'run'/'config' key:", [k for k in sd if k in ("when", "run", "config", "generated_from")])
