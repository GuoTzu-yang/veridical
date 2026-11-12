import io, json, os, re
root = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
F = os.path.join(root, "out", "final")
d = json.load(io.open(os.path.join(F,"data.json"), encoding="utf-8"))
tc = d["type_coverage"]
print("type_coverage n:", len(tc))
print("first:", json.dumps(tc[0], ensure_ascii=False))
keys = sorted({k for x in tc for k in x})
print("keys union:", keys)
for x in tc:
    print("  ", json.dumps(x, ensure_ascii=False))
print()
d2 = json.load(io.open(os.path.join(F,"data2.json"), encoding="utf-8"))
print("data2.sections =", json.dumps(d2["sections"], ensure_ascii=False), "len", len(d2["sections"]))
print("data2.paper_bytes =", d2["paper_bytes"], " actual paper.tex =", os.path.getsize(os.path.join(F,"paper.tex")))
print("data2.paper_words =", d2["paper_words"])
print("gate_ids:", json.dumps(d2["gate_ids"], ensure_ascii=False))
print()
gr = json.load(io.open(os.path.join(F,"gate-report.json"), encoding="utf-8"))
print("gate-report checks n:", len(gr["checks"]), "all_pass:", gr["all_pass"])
print("check names:", [c.get("name") or c.get("id") for c in gr["checks"]])