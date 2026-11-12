"""rtB / results board: verify the remaining numbers of the board.

Checks: heat-sink row count (84), critical r (0.2146), and the two claimed
fixes in freeze.py (single-point rule, precision-aware equality).
Read-only. Prints only.
"""
import json
import math
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINAL = os.path.join(ROOT, "out", "final")
os.chdir(ROOT)

# ---- 1. heat sink rows ----
print("=== 84 rows: heat_sink input ===")
cands = []
for base in ["out/data", "out/runs/heat_sink", "data"]:
    p = os.path.join(ROOT, base)
    if os.path.isdir(p):
        for f in os.listdir(p):
            if "heat" in f.lower():
                cands.append(os.path.join(base, f))
print("  candidates:", cands)
for c in cands:
    full = os.path.join(ROOT, c)
    print("  %-46s %d bytes" % (c, os.path.getsize(full)))
    if c.endswith(".csv"):
        rows = open(full, encoding="utf-8", errors="replace").read().splitlines()
        print("      csv lines:", len(rows), "=> data rows:", len(rows) - 1)
    elif c.endswith((".xlsx", ".xls")):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(full, read_only=True, data_only=True)
            for ws in wb.worksheets:
                print("      sheet %-20s max_row=%s max_col=%s" %
                      (ws.title, ws.max_row, ws.max_column))
        except Exception as e:
            print("      xlsx read failed:", e)

# frozen table entry that carries 0.2146
print("\n=== 0.2146 in the frozen table ===")
fz = json.load(open(os.path.join(FINAL, "冻结数字.json"), encoding="utf-8"))
for i, it in enumerate(fz["items"]):
    if str(it.get("value")) == "0.2146":
        print("  item[%d] path=%s value=%s" % (i, it.get("path"), it.get("value")))
print("  source field of frozen table:", fz.get("source"))
print("  n field:", fz.get("n"), " y:", fz.get("y"), " x:", fz.get("x"))

# recompute two-sided critical r for alpha=.05
def rcrit(n, k):
    from math import sqrt
    # t critical via inverse survival using scipy if present, else table-free approx
    try:
        from scipy import stats
        df = n - k - 2
        t = stats.t.ppf(1 - 0.025, df)
        return df, t, t / sqrt(t * t + df)
    except Exception:
        return None

for n, k in [(84, 0), (84, 1), (84, 2), (84, 3)]:
    out = rcrit(n, k)
    print("  n=%d controls=%d -> df=%s t=%.4f r_crit=%.4f" % (n, k, out[0], out[1], out[2]))

# ---- 2. the two claimed fixes in freeze.py ----
print("\n=== freeze.py: single-point rule + tolerance ===")
fp = os.path.join(ROOT, "freeze.py")
src = open(fp, encoding="utf-8").read()
print("  file bytes:", len(src))
for pat in [r"0\.10", r"\b10\b", r"tolerance", r"tol\b", r"single_point",
            r"decimal", r"round\("]:
    hits = [(i + 1, ln.strip()) for i, ln in enumerate(src.splitlines())
            if re.search(pat, ln)]
    print("\n  pattern %-12s %d hits" % (pat, len(hits)))
    for ln, s in hits[:6]:
        print("     L%-5d %s" % (ln, s[:130]))
