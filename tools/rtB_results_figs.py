"""rtB / results board: figure/table label-vs-reference audit + caption-vs-plotted-value.

Read-only. Prints only.
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.join(ROOT, "out", "final", "paper.tex")
lines = open(PAPER, encoding="utf-8").read().splitlines()
text = "\n".join(lines)

# board span
start = next(i for i, l in enumerate(lines, 1) if l.startswith(r"\section{Results}"))
end = next(i for i, l in enumerate(lines, 1)
           if i > start and l.startswith(r"\section{"))
body = "\n".join(lines[start - 1:end - 1])
print("board span L%d-L%d" % (start, end - 1))

labels = {m.group(1): i for i, l in enumerate(lines, 1)
          for m in [re.match(r"\s*\\label\{((?:fig|tab):[^}]+)\}", l)] if m}
refs = {}
for i, l in enumerate(lines, 1):
    for m in re.finditer(r"\\(?:ref|autoref|cref)\{((?:fig|tab):[^}]+)\}", l):
        refs.setdefault(m.group(1), []).append(i)

print("\n=== labels defined in/around this board ===")
board_labels = [k for k, v in labels.items() if start - 20 <= v < end]
for k in board_labels:
    where = refs.get(k, [])
    inboard = [w for w in where if start <= w < end]
    status = "OK" if where else "ORPHAN (never referenced)"
    print("  %-22s label@L%-5d refs=%-22s inboard=%s  %s" %
          (k, labels[k], where if where else "-", inboard if inboard else "-", status))

print("\n=== every fig label in the whole paper: referenced? ===")
for k in sorted(labels):
    if not k.startswith("fig:"):
        continue
    if k not in refs:
        print("  ORPHAN  %-24s defined L%d" % (k, labels[k]))

print("\n=== tables in this board ===")
for k in board_labels:
    if k.startswith("tab:"):
        print("  %-22s refs=%s" % (k, refs.get(k, "NONE")))

# ---- caption vs plotted value for fig6 (vacuous-check) and fig7 (endpoint) ----
print("\n=== caption-vs-content: fig6_taxonomy ===")
d = json.load(open(os.path.join(ROOT, "out", "final", "data.json"), encoding="utf-8"))
tax = d["defect_taxonomy"]
plotted = {k: v["n_rounds"] for k, v in tax.items()}
print("  plotted by tools/make_final_figs.py from D['defect_taxonomy']:", plotted)
cap6 = re.search(r"\\caption\{The same counts, ordered\.[^}]*\}", text)
print("  caption text:", cap6.group(0)[:160] if cap6 else "NOT FOUND")
print("  table row for vacuous check prints: 7")
print("  figure/artifact value for vacuous check:", plotted["vacuous-check"])
print("  => caption asserts 'the same counts'; table 7 vs figure %d" % plotted["vacuous-check"])

print("\n=== caption-vs-content: fig7_growth ===")
src = open(os.path.join(ROOT, "tools", "make_final_figs.py"), encoding="utf-8").read()
m = re.search(r"pts = \[\(94, 20, 46\).*?\]", src, re.S)
print("  hardcoded points in figure script:", " ".join(m.group(0).split()) if m else "NOT FOUND")
print("  figure endpoint (on/total): 48/48 at round 109")
print("  paper text says: 'Coverage went from 20 of 46 to 51 of 51'")
print("  data.json n_modules_with_selftest:", d["n_modules_with_selftest"])

print("\n=== does Results body ever name the false-positive side? ===")
for kw in ["clean", "false", "alarm", "over-detect", "unmodified", "unchanged"]:
    n = len(re.findall(kw, body, re.I))
    print("  %-12s %d" % (kw, n))
