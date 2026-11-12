"""当前能力快照：题型覆盖到底认得出几类（紧凑版）。"""
import io
import json
import os
import subprocess
import sys

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
PY = sys.executable
os.chdir(HERE)
SYN = {"explain": "regression", "optimize": "optimization",
       "evaluate": "evaluation", "forecast": "prediction"}
cfg = json.load(io.open("runs.json", encoding="utf-8"))
full = 0
partial = 0
miss_labels = {}
advise_labels = set()
gold_labels = set()
rows = []
for name, it in cfg.items():
    d = it["out"]
    fz = os.path.join(d, "冻结数字.json")
    tp = os.path.join(d, "题型.json")
    if not os.path.exists(fz) or not os.path.exists(tp):
        rows.append((name, "跳过", ""))
        continue
    fd = json.load(io.open(fz, encoding="utf-8"))
    src = str(fd.get("source") or "").split(" · ")[0].strip()
    cands = [os.path.join(HERE, "out", "data", src),
             os.path.join(HERE, "out", "data", src + ".xlsx")]
    data = next((c for c in cands if os.path.exists(c)), None)
    if not data:
        rows.append((name, "数据找不到", src[:24]))
        continue
    argv = [PY, "mmkit.py", "advise", "--data", data,
            "--y", str(fd.get("y")),
            "--x", ",".join(str(x) for x in (fd.get("x") or []))]
    _min = [x.strip() for x in str(it.get("min") or "").split(",") if x.strip()]
    if _min:
        argv += ["--min", ",".join(_min)]
    if it.get("problem"):
        argv += ["--problem", str(it["problem"])]
    argv += ["--json"]
    r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=HERE, timeout=180)
    try:
        j = json.loads(r.stdout or "{}")
    except Exception:
        rows.append((name, "JSON 解析失败", ""))
        continue
    ks = [SYN.get(k, k) for k in (j.get("kinds") or [j.get("kind", "?")])]
    gold = json.load(io.open(tp, encoding="utf-8")).get("kinds") or []
    advise_labels |= set(ks)
    gold_labels |= set(gold)
    miss = sorted(set(gold) - set(ks))
    if not miss:
        full += 1
    elif set(ks) & set(gold):
        partial += 1
    for m in miss:
        miss_labels[m] = miss_labels.get(m, 0) + 1
    rows.append((name, "全中" if not miss else "缺 " + ",".join(miss),
                 "/".join(ks)))

print("题库 %d 道（可测 %d）" % (len(cfg), len(rows)))
print(" advise 认出的标签集合: %s" % ", ".join(sorted(advise_labels)))
print(" 题库人工标注的标签集合: %s" % ", ".join(sorted(gold_labels)))
print(" 题库有、advise 完全认不出的标签: %s"
      % (", ".join(sorted(gold_labels - advise_labels)) or "无"))
print()
print("  完全覆盖 %d 道 / 部分覆盖 %d 道" % (full, partial))
print("  仍缺的标签及出现次数: %s"
      % (", ".join("%s×%d" % (k, v) for k, v in
                   sorted(miss_labels.items(), key=lambda kv: -kv[1])) or "无"))
print()
for n, s, k in rows:
    print("   %-16s %-22s %s" % (n, s, k))
