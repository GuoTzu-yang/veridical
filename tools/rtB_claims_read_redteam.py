import json, os, sys
root = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
p = os.path.join(root, "out", "final", "redteam.json")
print("exists:", os.path.exists(p), "size:", os.path.getsize(p) if os.path.exists(p) else None)
with open(p, encoding="utf-8") as f:
    d = json.load(f)
print("top type:", type(d).__name__)
if isinstance(d, dict):
    print("top keys:", list(d.keys())[:30])
    items = d.get("sections") or d.get("records") or d.get("items") or []
else:
    items = d
print("n items:", len(items) if hasattr(items,'__len__') else '?')
if isinstance(items, list):
    keys = []
    for it in items:
        if isinstance(it, dict):
            keys.append(it.get("section"))
    print("sections present:", keys)
    for it in items:
        if isinstance(it, dict) and it.get("section") == "claims":
            print("=== CLAIMS RECORD ===")
            print(json.dumps(it, ensure_ascii=False, indent=2))