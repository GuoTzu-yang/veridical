import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
idx = json.load(open(os.path.join(HERE, "kb", "methods", "index.json"),
                     encoding="utf-8"))["kinds"]
chk = json.load(open(os.path.join(HERE, "kb", "methods", "checks.json"),
                     encoding="utf-8"))["kinds"]

print("  题型          required  checks  对不上的 required")
print("  " + "-" * 66)
bad_total = 0
for k in idx:
    req = idx[k].get("required") or []
    names = [it["name"] for it in (chk.get(k) or [])]
    # 用关键词粗对齐
    miss = []
    for r in req:
        rl = str(r).lower()
        if not any(any(w in n.lower() for w in rl.split())
                   for n in names):
            miss.append(r)
    bad_total += len(miss)
    flag = "  ←" if miss else ""
    print(f"  {k:<14}{len(req):>2}       {len(names):>2}    {miss}{flag}")
print()
print(f"  合计对不上 {bad_total} 条")