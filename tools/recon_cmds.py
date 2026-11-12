import os
import re
import subprocess
import sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
CMDS = ["run", "solve", "race", "ode", "dim", "forecast", "cluster",
        "plot", "profile", "ahp", "grey", "graph", "greyrel", "fuzzy",
        "video", "clean", "merge", "advise", "hints", "cand", "surface",
        "selftest"]
out = []
for c in CMDS:
    r = subprocess.run([PY, "mmkit.py", c, "--help"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       cwd=HERE)
    t = (r.stdout or "") + (r.stderr or "")
    args = re.findall(r"^\s+(--[a-z0-9-]+)", t, re.M)
    # 第一段说明（usage 之后、第一次出现选项之前）
    body = t.split("options:", 1)[0]
    lines = [x.strip() for x in body.splitlines()
             if x.strip() and not x.strip().startswith("usage:")]
    desc = " ".join(lines)[:110]
    has_help = "--help" in t
    out.append((c, len(args), desc, has_help))

print("  %-10s %-4s %s" % ("命令", "参数", "说明（--help 首段）"))
print("  " + "-" * 84)
for c, n, d, ok in out:
    print("  %-10s %-4d %s" % (c, n, d[:88] if d else "（无说明）"))