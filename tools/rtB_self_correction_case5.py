# -*- coding: utf-8 -*-
"""Read-only probe 3: the number in Case 5.

Case 5 (paper.tex L945-959) asserts: an earlier abstract said "128 recorded
rounds of repair" and "The log contains 29".  This probe recomputes the round
count from the ledger and prints every place the paper states a round count.
Writes nothing.
"""
import json, os, re, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, "ledger.jsonl")
TEX = os.path.join(ROOT, "out", "final", "paper.tex")
FROZEN = os.path.join(ROOT, "out", "final", "冻结数字.json")

# ---- 1. ledger structure -------------------------------------------------
rows = []
bad = 0
with open(LEDGER, "r", encoding="utf-8") as f:
    for ln in f:
        ln = ln.strip()
        if not ln:
            continue
        try:
            rows.append(json.loads(ln))
        except Exception:
            bad += 1
print("ledger.jsonl: parsable rows =", len(rows), " unparsable =", bad)
if rows:
    keys = collections.Counter()
    for r in rows:
        keys.update(r.keys())
    print("row keys (count of rows containing key):")
    for k, v in keys.most_common():
        print("   %-22s %d" % (k, v))

def distinct(field):
    vals = []
    for r in rows:
        if field in r:
            vals.append(str(r[field]))
    return vals

for cand in ("round", "rounds", "n_round", "r"):
    if cand in (rows[0] if rows else {}):
        vs = distinct(cand)
        print("field %r: distinct=%d max=%s" % (cand, len(set(vs)), max(vs) if vs else "?"))
        print("   sample:", vs[:5], "...", vs[-3:] if len(vs) > 5 else "")

print()
print("round-like fields present:", [k for k in (rows[0] if rows else {})
                                    if "round" in k.lower()])

# ---- 2. where does the paper state a round count? -----------------------
with open(TEX, "r", encoding="utf-8") as f:
    lines = f.read().split("\n")
print()
print("paper.tex lines mentioning 'round':")
for i, ln in enumerate(lines, 1):
    if re.search(r"\bround", ln, re.I):
        print("  L%d: %s" % (i, ln.strip()[:200]))

# ---- 3. frozen numbers --------------------------------------------------
print()
print("冻结数字.json entries whose name mentions round/repair:")
try:
    with open(FROZEN, "r", encoding="utf-8") as f:
        fz = json.load(f)
    def walk(o, path=""):
        if isinstance(o, dict):
            nm = str(o.get("name") or o.get("label") or o.get("key") or "")
            if re.search(r"round|repair|轮", nm, re.I):
                print("   ", path, "->", json.dumps(o, ensure_ascii=False)[:300])
            for k, v in o.items():
                walk(v, path + "/" + str(k))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, path + "[%d]" % i)
    walk(fz)
except Exception as e:
    print("  could not read frozen numbers:", e)
