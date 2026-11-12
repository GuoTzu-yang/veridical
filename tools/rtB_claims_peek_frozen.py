import json, os, re
root = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
p = os.path.join(root, "out", "final", "冻结数字.json")
d = json.load(open(p, encoding="utf-8"))
print("type:", type(d).__name__)
if isinstance(d, dict):
    print("keys:", list(d.keys())[:20])
    for k in list(d.keys())[:3]:
        v = d[k]
        print("--", k, type(v).__name__, (len(v) if hasattr(v,'__len__') else ''))
        print(json.dumps(v, ensure_ascii=False)[:800])
elif isinstance(d, list):
    print("len:", len(d))
    print(json.dumps(d[:3], ensure_ascii=False, indent=1)[:1200])