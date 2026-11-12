import json, os
root = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
d = json.load(open(os.path.join(root, "out", "final", "冻结数字.json"), encoding="utf-8"))
items = d["items"]
print("n items:", len(items))
print("item0 keys:", list(items[0].keys()))
for it in items[:6]:
    print(json.dumps(it, ensure_ascii=False))
print("...")
# search for 1027
print("has 1027:", [it for it in items if "1027" in json.dumps(it, ensure_ascii=False)][:3])
print("has 5:", [it for it in items if it.get("value") in (5,"5")][:3])