import io, os
root = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
pat = ("冻结数字", "freeze_paper_numbers")
skip = ("\\external\\", "\\_backup", "\\out\\runs\\")
hits = []
for dp, dn, fn in os.walk(root):
    if any(s in dp + "\\" for s in skip):
        continue
    for f in fn:
        if not f.endswith(".py"):
            continue
        p = os.path.join(dp, f)
        try:
            t = io.open(p, encoding="utf-8").read()
        except Exception:
            continue
        for k in pat:
            if k in t:
                rel = os.path.relpath(p, root)
                for i, ln in enumerate(t.splitlines(), 1):
                    if k in ln:
                        hits.append((rel, i, k, ln.strip()[:150]))
for h in hits:
    print(f"{h[0]}:{h[1]} [{h[2]}] {h[3]}")
print("total", len(hits))
# 是否 verify_all / gate 触发
for name in ("tools/verify_all.py", "gate.py"):
    p = os.path.join(root, name)
    t = io.open(p, encoding="utf-8").read()
    print("=====", name, "mentions:", [k for k in pat if k in t])
    for i, ln in enumerate(t.splitlines(), 1):
        if "freeze" in ln or "numbers" in ln:
            print(f"  {i}: {ln.strip()[:160]}")