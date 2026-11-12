import os
import subprocess
import sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
for cmd in (["run", "--data", "out/data/scope_test.xlsx", "--y", "产量",
             "--x", "反应温度,操作压力", "--no-gate"],
            ["run", "--data", "out/data/scope_test.xlsx", "--y", "产量",
             "--x", "反应温度,操作压力", "--json"]):
    r = subprocess.run([PY, "mmkit.py"] + cmd, capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       cwd=HERE)
    print("  %-58s 退出码 %s" % (" ".join(cmd[:2] + cmd[-1:]), r.returncode))
    if r.returncode != 0:
        print("    stderr:", (r.stderr or "")[:150].replace("\n", " "))
        print("    stdout 尾:", (r.stdout or "").strip().splitlines()[-1][:110])