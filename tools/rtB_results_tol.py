"""rtB / results board: is the 'two-percent tolerance' anywhere, and are the two
fixes pinned by tests? Read-only."""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

print("=== search for a 2% / 0.02 tolerance anywhere in the verification layer ===")
targets = ["freeze.py", "verify.py", "gate.py", "unfreeze.py"]
for f in targets:
    if not os.path.exists(f):
        print("  missing", f)
        continue
    src = open(f, encoding="utf-8").read()
    hits = [(i + 1, ln.strip()) for i, ln in enumerate(src.splitlines())
            if re.search(r"0\.02\b|\b2\s*%|two.percent|percent.*tol|tol.*percent", ln)]
    print("\n  %-14s %d hits" % (f, len(hits)))
    for ln, s in hits[:8]:
        print("     L%-5d %s" % (ln, s[:140]))

print("\n=== what does the freeze.py docstring say the OLD tolerance was? ===")
src = open("freeze.py", encoding="utf-8").read()
m = re.search(r"`tol` 原来带.*?\"\"\"", src, re.S)
print(m.group(0) if m else "NOT FOUND")

print("\n=== tests pinning single_point / precision-aware equality ===")
for base in ["tests", "tools"]:
    if not os.path.isdir(base):
        continue
    for f in sorted(os.listdir(base)):
        if not f.endswith(".py"):
            continue
        p = os.path.join(base, f)
        t = open(p, encoding="utf-8", errors="replace").read()
        if "single_point" in t or "high_precision" in t or "_match_written" in t:
            rel = [ln.strip() for ln in t.splitlines()
                   if "single_point" in ln or "high_precision" in ln or "_match_written" in ln]
            print("  %-40s %d refs" % (p, len(rel)))
            for r in rel[:4]:
                print("      ", r[:130])

print("\n=== does anything record the 0.4% share of numeric tokens? ===")
sd = open("out/final/seeded_defects.json", encoding="utf-8").read()
for s in ["0.4", "share", "ratio", "fraction", "token"]:
    print("  %-10r in seeded_defects.json: %s" % (s, s in sd))
print("  invented_number case planted value:",
      [c for c in __import__("json").load(open("out/final/seeded_defects.json", encoding="utf-8"))["cases"]
       if c["defect"] == "invented_number"][0])
