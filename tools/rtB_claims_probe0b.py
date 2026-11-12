import io, json, os
root = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
F = os.path.join(root, "out", "final")
for fn in ("data.json","data2.json","classifier_audit.json","ablation.json","gate-report.json","declaration.json"):
    d = json.load(io.open(os.path.join(F, fn), encoding="utf-8"))
    print("=====", fn, type(d).__name__, len(d))
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, (int,float,str,bool)) or v is None:
                print("   ", k, "=", v)
            elif isinstance(v, list):
                print("   ", k, f"[list n={len(v)}]")
            elif isinstance(v, dict):
                print("   ", k, f"{{dict keys={list(v.keys())[:12]}}}")