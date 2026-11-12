"""rtB / results board: locate where each Results-section claim comes from.

Read-only. Prints only. Never writes to paper.tex or sources.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINAL = os.path.join(ROOT, "out", "final")
PAPER = os.path.join(FINAL, "paper.tex")

# ---- 1. Results section text ----
lines = open(PAPER, encoding="utf-8").read().splitlines()
start = None
end = None
for i, ln in enumerate(lines, start=1):
    if ln.startswith(r"\section{Results}"):
        start = i
    elif start and ln.startswith(r"\section{") and i > start:
        end = i
        break
print("RESULTS SPAN:", start, "-", end, " (check task says 677-863)")
body = "\n".join(lines[start - 1:end - 1])

# ---- 2. every JSON artifact, flattened ----
def walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(v, path + "/" + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, path + "/[%d]" % i)
    else:
        yield path, obj

artifacts = {}
for f in sorted(os.listdir(FINAL)):
    if not f.endswith(".json"):
        continue
    p = os.path.join(FINAL, f)
    try:
        d = json.load(open(p, encoding="utf-8"))
    except Exception as e:
        artifacts[f] = ("PARSE-ERROR", str(e))
        continue
    artifacts[f] = list(walk(d))

print("\n=== artifact inventory ===")
for f, rows in artifacts.items():
    if isinstance(rows, tuple):
        print("  %-24s %s" % (f, rows[1]))
    else:
        print("  %-24s %d leaf values" % (f, len(rows)))

# ---- 3. numeric claims in this section, searched across artifacts ----
# (claim label, literal as printed, candidate probe values)
CLAIMS = [
    ("#problems in corpus", "23", ["23"]),
    ("problems with objective columns", "22", ["22"]),
    ("called explain", "21", ["21"]),
    ("optimisation over-reported vs curated", "21 vs 6", ["21", "6"]),
    ("evaluation under-reported", "1 vs 6", ["1", "6"]),
    ("fully classified", "15 of 22", ["15", "22"]),
    ("labels reachable", "7", ["7"]),
    ("log size", "129 kB", ["129", "129000", "129024"]),
    ("recorded rounds", "30", ["30"]),
    ("taxonomy rounds", "14/13/7/6/5/2", ["14", "13", "7", "6", "5", "2"]),
    ("selftest coverage before", "20 of 46", ["20", "46"]),
    ("selftest coverage after", "51 of 51", ["51"]),
    ("heat sink rows", "84", ["84"]),
    ("critical r at n=84", "0.2146", ["0.2146"]),
    ("fabricated share of tokens", "0.4 %", ["0.4"]),
    ("provenance threshold", "10 %", ["10"]),
    ("tolerance", "2 %", ["2"]),
    ("seeded cases", "30 of 30", ["30"]),
]

print("\n=== claim -> artifact hits (exact string match on leaf values) ===")
for label, printed, probes in CLAIMS:
    hits = []
    for f, rows in artifacts.items():
        if isinstance(rows, tuple):
            continue
        for path, val in rows:
            sv = str(val)
            if any(sv == pr or sv.replace(",", "") == pr for pr in probes):
                hits.append("%s%s=%s" % (f, path, sv))
    print("\n[%s] printed=%s" % (label, printed))
    if hits:
        for h in hits[:6]:
            print("    HIT", h)
        if len(hits) > 6:
            print("    ... %d more" % (len(hits) - 6))
    else:
        print("    NO exact leaf match (values may be derived/hand-computed)")

# ---- 4. seeded_defects clean side ----
print("\n=== seeded_defects.json: detection vs clean side ===")
sd = json.load(open(os.path.join(FINAL, "seeded_defects.json"), encoding="utf-8"))
print("n_cases=%s detected=%s rate=%s" % (sd["n_cases"], sd["detected"], sd["detection_rate"]))
print("clean_nonpass=%s  (clean rows=%d)" % (sd["clean_nonpass"], len(sd["clean"])))
tot = 0
for row in sd["clean"]:
    prob, checks, n = row[0], row[1], row[2]
    tot += n
    print("   clean %-16s nonpass=%-3s checks_involved=%d" % (prob, n, len(checks)))
print("sum of clean per-problem nonpass =", tot)

# ---- 5. does the section ever mention the clean side? ----
print("\n=== does Results text mention false positives / clean papers? ===")
for kw in ["false positive", "clean", "false alarm", "over-detect", "46"]:
    print("  %-14s occurrences in Results: %d" % (kw, body.lower().count(kw.lower())))
