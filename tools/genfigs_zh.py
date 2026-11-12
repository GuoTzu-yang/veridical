import os
import subprocess
import sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
KINDS = ("hist", "box", "corr", "resid", "qq", "pred", "sens",
         "cand", "tornado", "surfaces", "pareto", "flow")
figd = os.path.join(HERE, "out", "lang_zh", "fig")
os.makedirs(figd, exist_ok=True)
ok = 0
for k in KINDS:
    out = os.path.join(figd, k)
    subprocess.run([PY, "mmkit.py", "plot", "--kind", k,
                    "--data", os.path.join(HERE, "out", "data",
                                          "scope_test.xlsx"),
                    "--y", "产量", "--x", "反应温度,操作压力",
                    "--min", "产量,能耗,次品率", "--out-png", out],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
    if os.path.exists(out + ".pdf") and os.path.getsize(out + ".pdf") > 1000:
        ok += 1
print("  图 %d/%d" % (ok, len(KINDS)))