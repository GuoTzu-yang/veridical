import json, os
root = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
p = os.path.join(root, "out", "final", "redteam.json")
d = json.load(open(p, encoding="utf-8"))
for it in d["reviews"]:
    if it.get("section") == "claims":
        print(json.dumps(it, ensure_ascii=False, indent=2))
print("=== out/final listing ===")
fd = os.path.join(root, "out", "final")
for name in sorted(os.listdir(fd)):
    fp = os.path.join(fd, name)
    if os.path.isfile(fp):
        print(name, os.path.getsize(fp))
print("=== tools listing (*.py) ===")
td = os.path.join(root, "tools")
for name in sorted(os.listdir(td)):
    if name.endswith(".py"):
        print(name, os.path.getsize(os.path.join(td, name)))