"""给 13 条 finding 挂上已核实的代码/工件定位，并补两条自检（第 119 轮）。

每条 (where, evidence) 在写入前**先验证**：
  · 文件存在；
  · evidence 逐字出现在该文件里。
验证失败的会被打印出来，不写入 —— 这样"编一条 finding"必须先让那段代码存在。
"""
import io
import json
import os
import sys

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
OUT = os.path.join(HERE, "out", "final")

# 13 条 finding 对应的落地证据（按 redteam.json 里出现顺序）
CAND = [
    ("untraced.py", "n_untraced"),
    ("untraced.py", "n_untraced"),
    ("patches.py", "P42"),
    ("falsify.py", "滑动窗口"),
    ("out/final/冻结数字.json", "0.2146"),
    ("tools/seeded_defects.py", "detection_rate"),
    ("freeze.py", "single_point"),
    ("out/final/data2.json", "gate_matrix"),
    ("gate.py", "uncited"),
    ("out/final/data.json", "n_gate_checks"),
    ("gate.py", "NA_ABSENT"),
    ("paper.py", "without additional cost"),
    ("out/final/classifier_audit.json", "agreement"),
]

rec = json.load(io.open(os.path.join(OUT, "redteam.json"), encoding="utf-8"))
rows = []
for rv in rec["reviews"]:
    for p in rv.get("probes", []):
        if p.get("verdict") == "finding":
            rows.append((rv.get("section", ""), p))

print("finding %d 条 / 候选 %d 个" % (len(rows), len(CAND)))
ok = bad = 0
for (sec, p), (w, ev) in zip(rows, CAND):
    fp = os.path.join(HERE, w)
    if not os.path.exists(fp):
        print("  !! 文件不存在：%s" % w)
        bad += 1
        continue
    body = io.open(fp, encoding="utf-8", errors="replace").read()
    if ev not in body:
        print("  !! %s 里找不到 %r" % (w, ev))
        bad += 1
        continue
    p["where"] = w
    p["evidence"] = ev
    p.pop("quote", None)
    ok += 1

json.dump(rec, io.open(os.path.join(OUT, "redteam.json"), "w", encoding="utf-8",
                       newline="\n"), ensure_ascii=False, indent=1)
print("已挂 %d 条，失败 %d 条" % (ok, bad))

# ── 补自检：缺证据 / 证据不存在 都必须 FAIL ──────────────────────────
P = os.path.join(HERE, "redteam.py")
s = io.open(P, encoding="utf-8").read()
anchor = '    ck("有 finding 未关闭 → FAIL"'
add = '''    # 第 119 轮：证据必须落到文件上，且逐字命中
    td5 = tempfile.mkdtemp(prefix="rt_ev_")
    io.open(os.path.join(td5, "paper.tex"), "w", encoding="utf-8").write("x")
    rec5 = json.loads(json.dumps(rec))
    rec5["reviews"][0]["probes"][0].pop("where", None)
    rec5["reviews"][0]["probes"][0].pop("evidence", None)
    json.dump(rec5, io.open(os.path.join(td5, "redteam.json"), "w",
                            encoding="utf-8"), ensure_ascii=False)
    r5 = check(td5)
    ck("finding 缺 where/evidence → FAIL", r5["status"] == "FAIL",
       r5["detail"][:44])

    rec6 = json.loads(json.dumps(rec))
    rec6["reviews"][0]["probes"][0]["where"] = "redteam.py"
    rec6["reviews"][0]["probes"][0]["evidence"] = "这句话在文件里不存在zzz"
    td6 = tempfile.mkdtemp(prefix="rt_ev2_")
    io.open(os.path.join(td6, "paper.tex"), "w", encoding="utf-8").write("x")
    json.dump(rec6, io.open(os.path.join(td6, "redteam.json"), "w",
                            encoding="utf-8"), ensure_ascii=False)
    r6 = check(td6)
    ck("evidence 在文件里找不到 → FAIL", r6["status"] == "FAIL",
       r6["detail"][:44])

''' + anchor
if "finding 缺 where/evidence" not in s:
    s = s.replace(anchor, add, 1)
    io.open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("已补两条自检断言")
