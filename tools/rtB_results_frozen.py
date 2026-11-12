"""rtB / results board: what did the frozen table freeze for taxonomy, and what
does fig6_taxonomy plot? Read-only."""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINAL = os.path.join(ROOT, "out", "final")

fz = json.load(open(os.path.join(FINAL, "冻结数字.json"), encoding="utf-8"))
print("冻结数字.json keys:", list(fz.keys()))
items = fz.get("items", [])
print("n items:", len(items))
print("item keys:", list(items[0].keys()) if items else None)

print("\n=== frozen items mentioning taxonomy ===")
hit = 0
for it in items:
    blob = json.dumps(it, ensure_ascii=False)
    if "defect_taxonomy" in blob or "vacuous" in blob or "n_record_rounds" in blob \
       or "record_bytes" in blob or "n_modules_with_selftest" in blob:
        print("  ", blob[:300])
        hit += 1
print("  total:", hit)

print("\n=== frozen values equal to 7 or 8 with n_rounds-ish paths ===")
for it in items:
    p = str(it.get("path", ""))
    if "taxonomy" in p or "rounds" in p:
        print("   %-60s %s" % (p, it.get("value")))

# ---- what does the figure script plot? ----
print("\n=== figure producers for this board ===")
for fn in sorted(os.listdir(os.path.join(ROOT, "tools"))):
    if not fn.endswith(".py"):
        continue
    p = os.path.join(ROOT, "tools", fn)
    t = open(p, encoding="utf-8", errors="replace").read()
    if "fig6_taxonomy" in t or "fig7_growth" in t or "fig5_types" in t \
       or "fig13_labelmatrix" in t or "fig19_timeline" in t \
       or "fig8_pages_figs" in t or "fig12_passrate" in t or "fig17_trace_pages" in t:
        print("  ", fn, "->", [m for m in re.findall(r"fig\d+_\w+", t)][:12])
