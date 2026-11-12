"""rtB / results board: recompute r_crit for n=84 without scipy, and inspect the
heat-sink sheet's real row structure. Read-only."""
import math
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- Student t survival function via regularized incomplete beta ----
def betacf(a, b, x):
    MAXIT, EPS, FPMIN = 200, 3e-16, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < EPS:
            break
    return h

def betai(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    bt = math.exp(lbeta + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return bt * betacf(a, b, x) / a
    return 1.0 - bt * betacf(b, a, 1 - x) / b

def t_sf_two(t, df):
    """two-sided p for Student t"""
    return betai(df / 2.0, 0.5, df / (df + t * t))

def t_crit(df, alpha=0.05):
    lo, hi = 0.0, 100.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if t_sf_two(mid, df) > alpha:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2

print("=== sanity check t_crit against textbook values ===")
for df, expect in [(1, 12.706), (2, 4.303), (10, 2.228), (30, 2.042), (82, 1.989)]:
    got = t_crit(df)
    print("  df=%-3d got=%.4f expected=%.4f  %s" %
          (df, got, expect, "OK" if abs(got - expect) < 0.002 else "MISMATCH"))

print("\n=== r_crit for n=84, two-sided alpha=.05 ===")
for k in (0, 1, 2, 3):
    df = 84 - k - 2
    t = t_crit(df)
    r = t / math.sqrt(t * t + df)
    print("  controls=%d df=%d t=%.4f r_crit=%.4f" % (k, df, t, r))
print("  frozen table: derived.r_crit_84 = 0.2146")
print("  paper says: 'about 0.2146' for n=84")
print("  reading 0.30 significant / 0.19 not, given 0.2146:",
      0.30 > 0.2146, 0.19 < 0.2146)

# ---- heat sink row structure ----
print("\n=== out/data/heat_sink.xlsx real rows ===")
import openpyxl
wb = openpyxl.load_workbook(os.path.join(ROOT, "out", "data", "heat_sink.xlsx"),
                            read_only=True, data_only=True)
ws = wb.worksheets[0]
rows = list(ws.iter_rows(values_only=True))
print("  total sheet rows:", len(rows))
for i, r in enumerate(rows[:6]):
    print("   [%d] %s" % (i, r))
print("   ...")
for i, r in enumerate(rows[-3:]):
    print("   [%d] %s" % (len(rows) - 3 + i, r))
nonempty = sum(1 for r in rows if any(c is not None for c in r))
numeric_rows = sum(1 for r in rows
                   if r and isinstance(r[0], (int, float)))
print("  non-empty rows:", nonempty)
print("  rows whose first cell is numeric:", numeric_rows)
