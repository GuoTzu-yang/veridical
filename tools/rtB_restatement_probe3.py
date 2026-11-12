# -*- coding: utf-8 -*-
"""scope-auditor / probe 3: are the brief's constants carried over verbatim and sourced?

Read-only. Checks the only numeric token in L75-L170 ($R^2=0.94$) against
  - the project's own tokenizer (verify.extract_numbers)
  - the frozen-number table out/final/冻结数字.json (715 entries claimed)
  - out/final/context_metrics.json (per-section metric record)
and prints where any near-match value actually lives, so the matching rule is visible.
"""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.join(ROOT, "out", "final", "paper.tex")
FROZEN = os.path.join(ROOT, "out", "final", "冻结数字.json")
CTX = os.path.join(ROOT, "out", "final", "context_metrics.json")

sys.path.insert(0, ROOT)
import verify  # noqa: E402

lines = open(PAPER, "r", encoding="utf-8", errors="replace").read().splitlines()
block = "\n".join(lines[74:170])

print("== 1. tokens in the restatement block (project tokenizer) ==")
toks = verify.extract_numbers(block)
print("count=%d" % len(toks))
for t in toks:
    raw, where = t[0], t[1]
    print("   raw=%r  line=%r  written_decimals=%r" % (
        raw, where, verify._written_decimals(raw)))

print()
print("== 2. any unit / dimension symbol in the block? ==")
DIM = re.compile(r"(\\,\\mathrm\{|\\mathrm\{|\\text\{m\}|\\text\{kg\}|\\text\{s\}|"
                 r"\\si\{|\\SI\{|\\unit\{|metre|meter|kilogram|joule|watt|"
                 r"newton|pascal|kelvin|celsius|\bkg\b|\bkW\b|\bMPa\b|\bN\\cdot)")
hits = [(i + 1, ln) for i, ln in enumerate(lines[74:170], start=74) if DIM.search(ln)]
print("dimension hits: %d %s" % (len(hits), hits[:6]))

print()
print("== 3. frozen table: how many entries, does 0.94 exist exactly? ==")
fz = json.loads(open(FROZEN, "r", encoding="utf-8").read())
entries = fz if isinstance(fz, list) else (fz.get("numbers") or fz.get("entries") or [])
print("type=%s  n=%d" % (type(fz).__name__, len(entries) if hasattr(entries, "__len__") else -1))
if isinstance(fz, dict):
    print("top-level keys: %s" % list(fz.keys())[:12])

flat = []


def walk(obj, path):
    if isinstance(obj, dict):
        for k, v in obj.items():
            walk(v, path + "." + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk(v, path + "[%d]" % i)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        flat.append((path, float(obj)))


walk(fz, "$")
print("numeric leaves: %d" % len(flat))
exact = [(p, v) for p, v in flat if abs(v - 0.94) < 1e-12]
print("leaves exactly equal to 0.94: %d %s" % (len(exact), exact[:5]))
near = [(p, v) for p, v in flat if 0.93 <= v <= 0.95]
print("leaves in [0.93,0.95]: %d" % len(near))
for p, v in near[:20]:
    print("   %-70s %.6f" % (p, v))

print()
print("== 4. values near 94 (percent scale) anywhere in the frozen table ==")
pct = [(p, v) for p, v in flat if 93.5 <= v <= 94.5]
print("count=%d" % len(pct))
for p, v in pct[:12]:
    print("   %-70s %s" % (p, v))

print()
print("== 5. restatement entry in context_metrics.json ==")
try:
    ctx = json.loads(open(CTX, "r", encoding="utf-8").read())
    def find(o, depth=0):
        if isinstance(o, dict):
            for k, v in o.items():
                if "restat" in str(k).lower() or (isinstance(v, str) and "restat" in v.lower()):
                    print("   key=%r -> %s" % (k, json.dumps(v, ensure_ascii=False)[:300]))
                find(v, depth + 1)
        elif isinstance(o, list):
            for v in o[:60]:
                find(v, depth + 1)
    find(ctx)
except Exception as exc:  # noqa: BLE001
    print("context_metrics unreadable: %r" % (exc,))

print()
print("== 6. verify.py matching rule: the 0.01 rescale branch ==")
src = open(os.path.join(ROOT, "verify.py"), "r", encoding="utf-8").read().splitlines()
for i, ln in enumerate(src, 1):
    if "_near" in ln or "0.01" in ln or "* 0.01" in ln:
        lo = max(0, i - 2)
        hi = min(len(src), i + 1)
        for j in range(lo, hi):
            print("  verify.py L%-5d %s" % (j + 1, src[j]))
        print("  ---")
