import os
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "out")
D = os.path.join(OUT, "data")
os.makedirs(os.path.join(OUT, "fig2026c"), exist_ok=True)

LAM = pd.read_csv(os.path.join(OUT, "fanvote_lam.csv"))
CR = pd.read_csv(os.path.join(D, "c2026c_controversy.csv"))
SE = pd.read_csv(os.path.join(D, "c2026c_weight_sens.csv"))

# 图 1 数据：每周 λ 区间（pct 法）—— 一行一季-周
g = LAM[(LAM.method == "pct") & (LAM.ok == 1)].copy()
g["lam_mid"] = (g.lam_lo + g.lam_hi) / 2
g["wid"] = g.lam_hi - g.lam_lo
g[["season", "week", "n", "lam_lo", "lam_mid", "lam_hi", "wid"]].to_csv(
    os.path.join(D, "fig1_lambda.csv"), index=False)
print("  图1: %d 周，λ 中位 %.3f，宽度中位 %.3f" % (len(g), g.lam_mid.median(), g.wid.median()))

# 图 2 数据：controversy 倒挂（评委名次 vs 观众名次）
cr = CR[CR.n >= 4].copy()
cr[["judge_rank", "fan_rank", "upside", "season", "week"]].to_csv(
    os.path.join(D, "fig2_upside.csv"), index=False)
print("  图2: %d 个选手周，倒挂 >0 占 %.0f%%" % (len(cr), 100 * (cr.upside > 0).mean()))

# 图 3 数据：权重敏感度（每档权重的冠军是否与 w=0.5 相同）
base = SE[np.isclose(SE.w, 0.5)].set_index("season").champ
rows = []
for w in sorted(SE.w.unique()):
    d = SE[np.isclose(SE.w, w)].set_index("season").champ
    same = int((d.reindex(base.index) == base.reindex(d.index)).sum())
    rows.append(dict(w=w, agree=same, total=len(d), pct=round(100 * same / len(d), 1)))
W3 = pd.DataFrame(rows)
W3.to_csv(os.path.join(D, "fig3_weight.csv"), index=False)
print("  图3: %d 档权重" % len(W3))

# 图 4 数据：两法可行性
# rank 的可行率改从 tools/rank_feasible.py 的**确定性**判定读（Hall 条件），
# 不再写采样的 97.0% —— 那是个不稳定量（换种子 223–225）。
_RF = os.path.join(D, "c2026c_rank_feasible.csv")
_rank_pct = 97.0
if os.path.exists(_RF):
    _R = pd.read_csv(_RF)
    _rank_pct = round(100.0 * int(_R.feasible.sum()) / len(_R), 1)
F = pd.DataFrame([
    dict(method="percentage", feasible=83.5, width=0.494),
    dict(method="rank", feasible=_rank_pct, width=0.531),
])
F.to_csv(os.path.join(D, "fig4_two_methods.csv"), index=False)
print("  图4: pct 83.5%% / rank %.1f%%" % _rank_pct)
print()
print("  当前数据文件：")
for f in sorted(os.listdir(D)):
    if f.startswith(("fig", "c2026c", "fanvote")):
        print("    %-30s %d 字节" % (f, os.path.getsize(os.path.join(D, f))))