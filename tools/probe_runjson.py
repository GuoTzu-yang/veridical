import os
import subprocess
import sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
sys.path.insert(0, HERE)
import orchestrate
import json

for cmd in (["run", "--data", "out/data/scope_test.xlsx", "--y", "产量",
             "--x", "反应温度,操作压力", "--json", "--no-gate"],
            ["solve", "--data", "out/data/scope_test.xlsx", "--y", "产量",
             "--x", "反应温度,操作压力", "--maximize", "--json"]):
    r = subprocess.run([PY, "mmkit.py"] + cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=HERE)
    out = (r.stdout or "").strip()
    print("  === %s 退出码 %s，stdout %d 字符 ===" % (cmd[0], r.returncode, len(out)))
    try:
        d = json.loads(out)
        flat = orchestrate._flatten_metrics(d)
        keys = sorted(flat.keys())
        print("    顶层键 %d 个，拍平后 %d 个" % (len(d), len(keys)))
        print("    拍平样例: %s" % keys[:8])
        for k in ("n_rows", "rmse", "best_rmse", "fit.best_rmse"):
            if k in flat:
                print("    命中 %-14s = %s" % (k, flat[k]))
    except Exception as e:
        print("    解析失败:", e, "| 前 80:", repr(out[:80]))