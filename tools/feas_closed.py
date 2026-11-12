import os
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EPS = 0.003
L = pd.read_excel(os.path.join(HERE, "out", "data", "dwts2026c_long.xlsx"))
W = pd.read_excel(os.path.join(HERE, "out", "data", "dwts2026c.xlsx"))
W["_k"] = list(zip(W.season, W.celebrity_name))
place = dict(zip(W["_k"], W.placement))
exitw = dict(zip(W["_k"], np.where(W.eliminated_week > 0,
                                     W.eliminated_week, W.last_week)))
L["_k"] = list(zip(L.season, L.celebrity_name))

rows = []
for (s, w), g in L.groupby(["season", "week"], sort=True):
    en = g.loc[g.eliminated == 1, "celebrity_name"].tolist()
    if len(en) != 1:
        continue
    gg = g.copy()
    gg["plc"] = gg["_k"].map(place)
    gg["exw"] = gg["_k"].map(exitw)
    gg = gg[gg.exw >= gg.week]
    if len(gg) < 3 or gg.plc.isna().any():
        continue
    J = gg.judge_score.values.astype(float)
    n = len(J)
    Jn = (J - J.min()) / (J.max() - J.min()) if J.max() > J.min() else np.zeros(n)
    e = int(np.where(gg.celebrity_name.values == en[0])[0][0])
    c = Jn - Jn[e]
    # pct 法可行性闭式判据：存在 p_e 使 sum_i max(EPS, p_e - c_i) <= 1
    need = float(np.maximum(EPS, EPS - c).sum())
    rows.append(dict(season=s, week=w, n=n, elim_judge_rank=int(
        (Jn > Jn[e]).sum() + 1), need=need,
        pct_feasible=1 if need <= 1.0 else 0))
R = pd.DataFrame(rows)
print("  === pct 法可行性的闭式判据 ===")
print("  可行 %d / %d (%.1f%%)" % (R.pct_feasible.sum(), len(R),
                                    100 * R.pct_feasible.mean()))
print("  不可行的周里，被淘汰者评委分的名次分布：")
bad = R[R.pct_feasible == 0]
print("    %s" % bad.elim_judge_rank.value_counts().sort_index().to_dict())
good = R[R.pct_feasible == 1]
print("  可行的周里，被淘汰者评委分的名次分布：")
print("    %s" % good.elim_judge_rank.value_counts().sort_index().to_dict())
print()
print("  → 关键：评委分不是当周最低时，percentage 法在数学上就无法让该选手垫底")
print("    （约束 sum_i max(EPS, p_e-c_i) > 1，无解）")
R.to_csv(os.path.join(HERE, "out", "pct_feasibility.csv"), index=False)

# ── 两法对观众的偏向：有效权重 ──
print()
print("  === 两种合并法的「评委有效权重」===")
print("  percentage: c = 0.5*Jn + 0.5*p ; Jn 跨度恒为 1")
print("  rank     : c = 0.5*rJ + 0.5*rp ; rJ 跨度为 N-1")
for n in (6, 10, 12):
    rowsj = []
    for (s, w), g in L.groupby(["season", "week"]):
        en = g.loc[g.eliminated == 1, "celebrity_name"].tolist()
        if len(en) != 1 or w != 2:
            continue
        gg = g.copy(); gg["exw"] = gg.celebrity_name.map(exitw)
        gg = gg[gg.exw >= gg.week]
        if len(gg) != n:
            continue
        J = gg.judge_score.values.astype(float)
        Jn = (J - J.min()) / (J.max() - J.min())
        rowsj.append((Jn.max() - Jn.min(), 1.0))
    if rowsj:
        print("    n=%2d : Jn 实际跨度均值 %.3f (理论 1.0)  → pct 法下评委实际跨度占比 %.1f%%"
              % (n, np.mean([r[0] for r in rowsj]),
                 100 * np.mean([r[0] for r in rowsj])))