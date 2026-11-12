# -*- coding: utf-8 -*-
"""Read-only probe: what did the author record for section == self_correction?

Prints the existing redteam.json records so the auditor can compare per-probe.
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RT = os.path.join(ROOT, "out", "final", "redteam.json")

with open(RT, "r", encoding="utf-8") as f:
    data = json.load(f)

print("top-level type:", type(data).__name__)
if isinstance(data, dict):
    print("top-level keys:", list(data.keys()))

records = []
if isinstance(data, dict):
    for k in ("records", "sections", "results", "items", "probes"):
        if isinstance(data.get(k), list):
            records = data[k]
            print("using list under key:", k)
            break
    if not records:
        # fall back: any list of dicts
        for k, v in data.items():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                records = v
                print("using first list-of-dicts under key:", k)
                break
elif isinstance(data, list):
    records = data

print("candidate record count:", len(records))

def sect(rec):
    for k in ("section", "board", "key", "name", "id"):
        if isinstance(rec, dict) and k in rec:
            return rec.get(k)
    return None

hits = [r for r in records if isinstance(r, dict) and str(sect(r)).strip().lower() == "self_correction"]
print("records with section==self_correction:", len(hits))
for i, r in enumerate(hits):
    print("=" * 70)
    print("HIT", i)
    print(json.dumps(r, ensure_ascii=False, indent=2))

print("=" * 70)
print("ALL SECTION LABELS SEEN:")
labels = []
for r in records:
    s = sect(r)
    if s is not None:
        labels.append(str(s))
print(sorted(set(labels)))
