import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
KINDS = ("hist", "box", "corr", "resid", "qq", "pred", "sens",
         "cand", "tornado", "surfaces", "pareto", "flow")
xl = os.path.join(HERE, "out", "real_hs2024.xlsx")
figd = os.path.join(HERE, "out", "hs2024", "fig")
os.makedirs(figd, exist_ok=True)
ok = 0
for k in KINDS:
    out = os.path.join(figd, k)
    subprocess.run([PY, "mmkit.py", "plot", "--kind", k, "--data", xl,
                    "--y", "yield_per_mu", "--x", "cost_per_mu",
                    "--min", "yield_per_mu,cost_per_mu",
                    "--out-png", out],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
    if os.path.exists(out + ".pdf") and os.path.getsize(out + ".pdf") > 1000:
        ok += 1
print("  hs2024 图 %d/%d" % (ok, len(KINDS)))