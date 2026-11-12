"""rtB / results board: fig8 (figure density) reproducibility + the 'fivefold' claim,
and the semantic source of the '22' denominator. Read-only."""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

d = json.load(open("out/final/data.json", encoding="utf-8"))
probs = d["problems"]

print("=== does data.json carry the field fig8 needs? ===")
keys = set(probs[0].keys())
print("  problem keys:", sorted(keys))
print("  has n_fig_env:", "n_fig_env" in keys)
rows = [r for r in probs if r.get("pages") and r.get("n_fig_env") is not None]
print("  rows fig8 producer would keep:", len(rows), "-> skip" if not rows else "")

print("\n=== does collect_paper_data.py ever write n_fig_env? ===")
src = open("tools/collect_paper_data.py", encoding="utf-8").read()
print("  'n_fig_env' occurrences:", src.count("n_fig_env"))

print("\n=== the 'fivefold' claim in fig8's caption ===")
tf = sum(r["n_figs"] for r in probs if r.get("n_figs") is not None)
ti = sum(r["n_emb_imgs"] for r in probs if r.get("n_emb_imgs") is not None)
print("  sum n_figs (source figure envs): %s" % tf)
print("  sum n_emb_imgs (PDF embedded)  : %s" % ti)
if ti:
    print("  ratio n_figs / n_emb_imgs      : %.2f x" % (tf / ti))
print("  caption says: 'a PDF-level count under-reports them fivefold'")

print("\n=== per-problem figures: any with zero embedded images but source figs? ===")
z = [r["name"] for r in probs if r.get("n_figs") and not r.get("n_emb_imgs")]
print("  ", z[:10], "count=%d" % len(z))

print("\n=== where does the '22' come from (type_coverage filter)? ===")
print("  type_coverage len:", len(d["type_coverage"]), " problems len:", len(probs))
print("  filter in collect_paper_data.py: needs 冻结数字.json AND 题型.json")
print("  prose says: 'Twenty-two of 23 problems carried objective columns'")
inboth = sorted(set(r["name"] for r in d["type_coverage"]))
missing = sorted(set(r["name"] for r in probs) - set(inboth))
print("  problems absent from type_coverage:", missing)
