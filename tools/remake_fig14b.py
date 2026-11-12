"""fig14 替换版：每页数字密度（有方差的量）。

摘要分项那张图不可用：23 题 × 8 项全过，没有方差，等于装饰；
且分项名是中文，matplotlib 缺字。按本文自己的标准（图要承载论证），
换成一个真有方差的量：每个数字令牌 / 每页。
"""
import io
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
OUT = os.path.join(HERE, "out", "final")
FIG = os.path.join(OUT, "fig")
D = json.load(open(os.path.join(OUT, "data.json"), encoding="utf-8"))

rows = [r for r in D["problems"]
        if r.get("num_total") and r.get("pages")]
rows = [r for r in rows if (r.get("pages") or 0) > 0]
dens = [(r["name"], r["num_total"] / float(r["pages"])) for r in rows]
dens.sort(key=lambda t: t[1])

fig, ax = plt.subplots(figsize=(7.0, 3.0))
names = [d[0] for d in dens]
vals = [d[1] for d in dens]
ax.bar(range(len(names)), vals, color="#2b6cb0", alpha=0.85)
ax.set_yscale("log")
i=int(vals.index(max(vals)))
ax.annotate("nflis: 1027 table rows", (i, vals[i]),
            textcoords="offset points", xytext=(-14, 6), fontsize=7.6,
            color="#c53030")
ax.axhline(float(np.median(vals)), color="#c53030", ls="--", lw=1.1)
ax.text(len(names) - 0.5, float(np.median(vals)) + 0.4,
        "median %.1f" % float(np.median(vals)), ha="right", fontsize=8,
        color="#c53030")
ax.set_xticks(range(len(names)))
ax.set_xticklabels(names, rotation=62, ha="right", fontsize=7.2)
ax.set_ylabel("numeric tokens per page")
ax.set_title("Numeric density (log scale): one paper is two orders of "
             "magnitude denser", fontsize=10)
fig.tight_layout()
for ext in ("pdf", "png"):
    fig.savefig(os.path.join(FIG, "fig14_density.%s" % ext), dpi=300)
plt.close(fig)
print("已画 fig14_density：%d 题，范围 %.1f–%.1f/页"
      % (len(names), min(vals), max(vals)))
