import os
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "out")
FIG = os.path.join(OUT, "fig2026c")
g = pd.read_csv(os.path.join(OUT, "data", "fig1_lambda.csv"))
# 图1：每周 lambda 区间，按周次分组（观众票的不确定性）
fig, ax = plt.subplots(figsize=(9, 4.2))
for w in sorted(g.week.unique()):
    d = g[g.week == w]
    if len(d) < 2:
        continue
    ax.vlines(w, d.lam_lo.min(), d.lam_hi.max(), color="#8ab4f8", lw=6, alpha=.55)
    ax.plot(w, d.lam_mid.median(), "o", color="#1a73e8", ms=5)
ax.axhline(g.lam_mid.median(), ls="--", color="#d93025", lw=1,
           label="median $\\lambda$ = %.3f" % g.lam_mid.median())
ax.set_xlabel("week")
ax.set_ylabel(r"$\lambda$ (share of fan vote explained by judges)")
ax.set_title("Fan-vote feasible range by week (percentage rule, 193 season-weeks)")
ax.legend(loc="upper right", frameon=False)
ax.grid(alpha=.25)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "fig1_lambda.png"), dpi=160)
fig.savefig(os.path.join(FIG, "fig1_lambda.pdf"))
plt.close(fig)
print("  fig1_lambda: 193 周，λ 中位 %.3f，宽度中位 %.3f"
      % (g.lam_mid.median(), g.wid.median()))
print("  产物:")
for f in sorted(os.listdir(FIG)):
    print("    %-24s %d 字节" % (f, os.path.getsize(os.path.join(FIG, f))))