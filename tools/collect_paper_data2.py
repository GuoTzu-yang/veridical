"""第二轮采集：为扩充版论文补数据（data2.json）。

采：逐题 × 逐项 gate 状态矩阵、补丁分类账、逐题摘要分、本章节字数、
逐题数字总数、命令耗时、缺陷分类时间线。
"""
import io
import json
import os
import re
import subprocess
import sys
import time

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
PY = sys.executable
OUT = os.path.join(HERE, "out", "final")
os.chdir(HERE)

D2 = {}
D = json.load(io.open(os.path.join(OUT, "data.json"), encoding="utf-8"))
cfg = json.load(io.open("runs.json", encoding="utf-8"))

# ── 1 逐题 × 逐项 gate 状态矩阵 ──
mat = {}
ids = None
t0 = time.time()
for name, it in cfg.items():
    d = it["out"]
    if not os.path.exists(os.path.join(d, "paper.tex")):
        continue
    r = subprocess.run(
        [PY, "-c",
         "import sys;sys.path.insert(0,'.');import gate,json;"
         "r=gate.run_all(sys.argv[1]);"
         "print(json.dumps([[c['id'],c['tier'],c['status']] "
         "for c in r['checks']],ensure_ascii=False))", d],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=600)
    try:
        rows = json.loads(r.stdout)
    except Exception:
        continue
    mat[name] = {cid: [tier, st] for cid, tier, st in rows}
    ids = [cid for cid, _t, _s in rows]
D2["gate_matrix"] = mat
D2["gate_ids"] = ids
D2["gate_matrix_seconds"] = round(time.time() - t0, 1)

# ── 2 逐题摘要分 ──
ab = {}
for name, it in cfg.items():
    d = it["out"]
    tex = os.path.join(d, "paper.tex")
    if not os.path.exists(tex):
        continue
    r = subprocess.run([PY, "-c",
        "import sys,io;sys.path.insert(0,'.');import abstract;"
        "t=io.open(sys.argv[1],encoding='utf-8').read();"
        "a=abstract.audit(t);print(a['score'])", tex],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=300)
    try:
        ab[name] = float([x for x in r.stdout.split() if x.strip()][-1])
    except Exception:
        pass
D2["abstract_scores"] = ab

# ── 3 本文字节/小节权重（按 section 切）──
p = os.path.join(OUT, "paper.tex")
t = io.open(p, encoding="utf-8").read()
# 第 123 轮修：原正则写成 r"\n\\\\section\{..." —— 原始字符串里 `\\\\`
# 匹配的是**两个字面反斜杠**，而 tex 源里只有一个 `\section{`，
# 于是 sections 永远是 []（实测 output 打「小节: 0」，而论文有 12 个 \section）。
# 正确的写法是 r"\n\\section\{"。
parts = re.split(r"\n\\section\*?\{([^}]*)\}", "\n" + t)
secs = []
for i in range(1, len(parts), 2):
    title = parts[i]
    body = parts[i + 1] if i + 1 < len(parts) else ""
    words = len(re.findall(r"[A-Za-z][A-Za-z'\-]+", body))
    secs.append(dict(title=title, words=words,
                     figs=body.count("\\begin{figure}"),
                     tabs=body.count("\\begin{table}")))
D2["sections"] = secs
# 第 123 轮：切到 0 个小节是**坏产物**，不是「这篇论文没有小节」。
# 实测：正则曾多转义一层（`\\\\section` 匹配两个字面反斜杠），
# sections 长期为空而没有任何断言，fig16 于是画了一版旧数据出来。
# 这里 fail-closed：宁可停，不要让坏产物往下游走。
if not secs:
    raise SystemExit("切分到 0 个小节：paper.tex 里没有 \\section，"
                     "或切分正则与源文件格式不符（不要带着空 sections 继续）")
D2["paper_words"] = len(re.findall(r"[A-Za-z][A-Za-z'\-]+", t))
D2["paper_bytes"] = len(t.encode("utf-8"))

# ── 4 补丁账本分类 ──
r = subprocess.run([PY, "patches.py", "list"], capture_output=True,
                   text=True, encoding="utf-8", errors="replace", timeout=300)
txt = (r.stdout or "") + (r.stderr or "")
cats = {}
for ln in txt.splitlines():
    m = re.match(r"\s*(\S+)\s+(已落实|待做)", ln)
    if m:
        cats["done" if m.group(2) == "已落实" else "todo"] = \
            cats.get("done" if m.group(2) == "已落实" else "todo", 0) + 1
D2["patch_ledger"] = cats

# ── 5 命令耗时（实测若干条）──
TIMED = [
    ("advise", ["mmkit.py", "advise", "--data", "out/data/heat_sink.xlsx",
                "--y", "热阻", "--x", "宽度,深高", "--json"]),
    ("race", ["mmkit.py", "race", "--data", "out/data/heat_sink.xlsx",
              "--y", "热阻", "--x", "宽度,深高", "--json"]),
    ("hints", ["mmkit.py", "hints", "--data", "out/data/heat_sink.xlsx",
               "--y", "热阻", "--x", "宽度,深高"]),
    ("plot corr", ["mmkit.py", "plot", "--kind", "corr", "--data",
                   "out/data/heat_sink.xlsx", "--y", "热阻", "--x", "宽度,深高",
                   "--out-png", "out/final/fig/_t.png"]),
    ("verify", ["verify.py", "out/runs/heat_sink/paper.tex"]),
    ("falsify", ["falsify.py", "counter", "--data", "out/data/heat_sink.xlsx",
                 "--y", "热阻", "--x", "宽度"]),
    ("lanes demo", ["lanes.py", "demo"]),
    ("gate", ["-c", "import sys;sys.path.insert(0,'.');import gate;"
              "gate.run_all('out/runs/heat_sink')"]),
]
rt = []
for label, argv in TIMED:
    tt = time.time()
    subprocess.run([PY] + argv, capture_output=True, cwd=HERE, timeout=900)
    rt.append(dict(cmd=label, seconds=round(time.time() - tt, 2)))
D2["runtimes"] = rt

json.dump(D2, io.open(os.path.join(OUT, "data2.json"), "w", encoding="utf-8",
                      newline="\n"), ensure_ascii=False, indent=1)
print("已写 data2.json")
print("  gate 矩阵:", len(mat), "题 ×", len(ids or []), "项",
      "(%.1fs)" % D2["gate_matrix_seconds"])
print("  摘要分:", len(ab), "题")
print("  本文字数:", D2["paper_words"], " 小节:", len(secs))
print("  补丁账本:", D2["patch_ledger"])
print("  耗时:", [(x["cmd"], x["seconds"]) for x in rt])
