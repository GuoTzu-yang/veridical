# -*- coding: utf-8 -*-
"""scope-auditor / probe 3b: does the gate's own tracer certify the 0.94?

Read-only. Runs verify.trace on the restatement block with the same pool the
gate would load (verify.load_outputs('out/final')) and names the frozen entries
that made 0.94 pass.
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINAL = os.path.join(ROOT, "out", "final")
PAPER = os.path.join(FINAL, "paper.tex")
sys.path.insert(0, ROOT)
import verify  # noqa: E402

lines = open(PAPER, "r", encoding="utf-8", errors="replace").read().splitlines()
block = "\n".join(lines[74:170])

pool = verify.load_outputs(FINAL)
flat = verify.collect_output_numbers(pool)
print("pool documents from verify.load_outputs('out/final'): %d" % len(pool))
print("flattened numbers in that pool: %d" % len(flat))
res = verify.trace(block, pool)
print("verify.trace(block) -> ok=%r n_numbers=%d n_untraced=%d traced_ratio=%r"
      % (res["ok"], res["n_numbers"], res["n_untraced"], res["traced_ratio"]))
print("untraced list: %r" % (res["untraced"],))

print()
print("== which pool values explain 0.94? ==")
hits = sorted({p for p in flat if verify._near(0.94, p, 2)})
print("distinct matching pool values: %r" % (hits,))

print()
print("== frozen table: identity of the matching entries ==")
fz = json.loads(open(os.path.join(FINAL, "冻结数字.json"), "r", encoding="utf-8").read())
print("source=%r generated_from=%r n=%r"
      % (fz.get("source"), fz.get("generated_from"), fz.get("n")))
items = fz.get("items") or []
print("items: %d" % len(items))
for idx in (17, 157, 630):
    if idx < len(items):
        it = items[idx]
        print("  items[%d] = %s" % (idx, json.dumps(it, ensure_ascii=False)))

print()
print("== any item whose value is exactly 0.94 (i.e. a real R^2)? ==")
real = [i for i, it in enumerate(items)
        if isinstance(it, dict) and abs(float(it.get("value", -1)) - 0.94) < 1e-12]
print("count=%d %s" % (len(real), real[:10]))

print()
print("== how many items are r2-like at all? ==")
r2 = [it for it in items if isinstance(it, dict) and "r2" in json.dumps(it).lower()]
print("items mentioning r2: %d" % len(r2))
for it in r2[:6]:
    print("   %s" % json.dumps(it, ensure_ascii=False)[:200])
