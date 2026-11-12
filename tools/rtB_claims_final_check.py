# -*- coding: utf-8 -*-
import io, json, os, time
root = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
print("=== 只读自证：paper.tex 与源码 mtime/size 未变 ===")
for rel in ("out/final/paper.tex", "freeze.py", "gate.py", "tools/freeze_paper_numbers.py",
            "tools/make_final_figs2.py"):
    p = os.path.join(root, rel)
    st = os.stat(p)
    print(f"  {rel:<34} {st.st_size:>7} B  {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime))}")
print()
print("=== 我的产物 ===")
for rel in ("out/红队七板/claims-overclaim-auditor.json", "out/红队七板/claims-overclaim-auditor.md"):
    p = os.path.join(root, rel)
    print(f"  {rel}  {os.path.getsize(p)} B")
print("  tools/rtB_claims_*.py:")
for f in sorted(os.listdir(os.path.join(root, "tools"))):
    if f.startswith("rtB_claims_"):
        print("   ", f)
print()
print("=== JSON 结构自检 ===")
d = json.load(io.open(os.path.join(root, "out/红队七板/claims-overclaim-auditor.json"), encoding="utf-8"))
assert d["section"] == "claims" and d["role"] == "overclaim-auditor"
assert d["verdict"] in ("pass", "revise")
print("  section/role:", d["section"], "/", d["role"], "| verdict:", d["verdict"])
for i, x in enumerate(d["probes"], 1):
    ok_where = os.path.exists(os.path.join(root, x["where"]))
    ok_ev = x["evidence"] in io.open(os.path.join(root, x["where"]), encoding="utf-8").read()
    print(f"  [{i}] {x['verdict']:<8} where={x['where']:<32} exists={ok_where} evidence_exists={ok_ev} note={len(x['note'])}字 tried={len(x['tried'])}字")
print("  resolved:", d["resolved"][:80], "...")
print("  顶层键:", list(d.keys()))