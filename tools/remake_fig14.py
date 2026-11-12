"""把 fig14 换成有信息量的版本：摘要分项，逐题看哪一项接近失分。

原来那张图所有柱子都是 100 —— 一张没有信息的图，正是本文批评的「装饰」。
"""
import io
import json
import os
import subprocess
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
OUT = os.path.join(HERE, "out", "final")
FIG = os.path.join(OUT, "fig")
PY = sys.executable

cfg = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
rows = {}
names = None
for name, it in cfg.items():
    tex = os.path.join(HERE, it["out"], "paper.tex")
    if not os.path.exists(tex):
        continue
    r = subprocess.run(
        [PY, "-c",
         "import sys,io,json;sys.path.insert(0, '.');import abstract;"
         "t=io.open(sys.argv[1],encoding='utf-8').read();"
         "a=abstract.audit(t);"
         "print(json.dumps([[i['name'],1 if i['ok'] else 0] for i in a['items']],"
         "ensure_ascii=False))", tex],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=HERE, timeout=300)
    try:
        items = json.loads(r.stdout)
    except Exception:
        continue
    names = [i[0] for i in items]
    rows[name] = [i[1] for i in items]

if not rows and not names:
    print("没有数据")
    raise SystemExit(1)

probs = list(rows)
M = np.array([rows[p] for p in probs], dtype=float)
fig, ax = plt.subplots(figsize=(6.8, 4.4))
ax.imshow(M, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
ax.set_xticks(range(len(names)))
ax.set_xticklabels(names, rotation=28, ha="right", fontsize=9)
ax.set_yticks(range(len(probs)))
ax.set_yticklabels(probs, fontsize=7.8)
for i in range(len(probs)):
    for j in range(len(names)):
        if M[i, j] == 0:
            ax.text(j, i, "×", ha="center", va="center", fontsize=7,
                    color="#7f1d1d")
ax.set_title("Abstract rubric, item by item (%d problems × %d items); "
             "× = failed" % (len(probs), len(names)), fontsize=10)
fig.tight_layout()
for ext in ("pdf", "png"):
    fig.savefig(os.path.join(FIG, "fig14_abstract.%s" % ext), dpi=300)
plt.close(fig)
print("已重画 fig14_abstract：%d 题 × %d 项" % (len(probs), len(names)))
fails = {}
for j, nm in enumerate(names):
    k = int((M[:, j] == 0).sum())
    if k:
        fails[nm] = k
print("失分项:", fails or "无")
