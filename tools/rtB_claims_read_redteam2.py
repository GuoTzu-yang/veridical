import json, os
root = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
p = os.path.join(root, "out", "final", "redteam.json")
with open(p, encoding="utf-8") as f:
    d = json.load(f)
rev = d["reviews"]
print("reviews type:", type(rev).__name__, "len:", len(rev))
if isinstance(rev, dict):
    print("keys:", list(rev.keys()))
    for k, v in rev.items():
        print("---", k, "->", json.dumps(v, ensure_ascii=False)[:400])
else:
    for i, it in enumerate(rev):
        print("---", i, json.dumps(it, ensure_ascii=False)[:600])