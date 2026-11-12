import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
KINDS = ("hist", "box", "corr", "resid", "qq", "pred", "sens",
         "cand", "tornado", "surfaces", "pareto", "flow")

name = "real"
xl = os.path.join(HERE, "out", "real_hs.xlsx")
ys = "CBTS"
xs = "母亲年龄,妊娠时间（周数）,睡醒次数"
mins = "CBTS,EPDS,HADS"
figd = os.path.join(HERE, "out", name, "fig")
os.makedirs(figd, exist_ok=True)
ok = 0
for k in KINDS:
    out = os.path.join(figd, k)
    subprocess.run([PY, "mmkit.py", "plot", "--kind", k, "--data", xl,
                    "--y", ys, "--x", xs, "--min", mins,
                    "--out-png", out],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
    if os.path.exists(out + ".pdf") and os.path.getsize(out + ".pdf") > 1000:
        ok += 1
print("  图 %d/%d" % (ok, len(KINDS)))