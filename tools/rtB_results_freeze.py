"""rtB / results board: the two claimed freeze.py fixes, and the heat-sink inputs.

Read-only. Prints only.
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

print("=== freeze.py: does it implement the two fixes the paper claims? ===")
src = open("freeze.py", encoding="utf-8").read()
print("  bytes:", len(src))
for pat, label in [
    (r"single_point", "single-point rule name"),
    (r"0\.10|0\.1\b|10\s*/\s*100|\bten percent\b", "10% threshold"),
    (r"tol", "tolerance"),
    (r"decimals|decimal|dp\b|places", "decimal places"),
    (r"round\(", "rounding"),
]:
    hits = [(i + 1, ln.strip()) for i, ln in enumerate(src.splitlines())
            if re.search(pat, ln)]
    print("\n  [%s] %d hits" % (label, len(hits)))
    for ln, s in hits[:10]:
        print("     L%-5d %s" % (ln, s[:150]))

print("\n=== grep whole repo for the exact strings the paper cites ===")
for s in ["single_point", "single-point", "above 10", "two-percent", "2 percent",
          "0.4", "r_crit_84"]:
    hits = []
    for base in [".", "tools"]:
        for f in os.listdir(base):
            if not f.endswith((".py", ".json", ".md", ".tex")):
                continue
            p = os.path.join(base, f)
            if not os.path.isfile(p):
                continue
            try:
                t = open(p, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            if s in t:
                hits.append(p)
    print("  %-14r in %s" % (s, hits[:6]))

print("\n=== heat_sink run: what did the detector actually receive? ===")
for cand in ["out/runs/heat_sink/冻结数字.json", "out/runs/heat_sink/题型.json"]:
    if not os.path.exists(cand):
        print("  missing:", cand)
        continue
    d = json.load(open(cand, encoding="utf-8"))
    print("\n  ", cand)
    if "items" in d:
        for k in ("source", "y", "x", "n", "generated_from"):
            if k in d:
                print("     %-14s %s" % (k, d[k]))
    else:
        print("     ", json.dumps(d, ensure_ascii=False)[:400])
