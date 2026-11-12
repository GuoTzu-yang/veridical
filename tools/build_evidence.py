import json
import os
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "out")
D = os.path.join(OUT, "data")
LAM = pd.read_csv(os.path.join(OUT, "fanvote_lam.csv"))
CR = pd.read_csv(os.path.join(D, "c2026c_controversy.csv"))
W = pd.read_excel(os.path.join(D, "dwts2026c.xlsx"))
L = pd.read_excel(os.path.join(D, "dwts2026c_long.xlsx"))
pct = LAM[(LAM.method == "pct") & (LAM.ok == 1)]
rnk = LAM[(LAM.method == "rank") & (LAM.ok == 1)]
bad = LAM[(LAM.method == "pct") & (LAM.ok == 0)]

ev = {}
ev["n_contestants"] = int(len(W))
ev["n_seasons"] = int(W.season.nunique())
ev["n_contestant_weeks"] = int(len(L))
ev["n_season_weeks"] = int((LAM.method == "pct").sum())
ev["pct_consistent"] = int(len(pct))
# rank 法改用**确定性**判定（tools/rank_feasible.py 的 Hall 条件），
# 不再用 rejection sampling 的可行周数：同一个 3000 次采样换种子得
# 223–225，不是稳定的量。pct 法本身是闭式判据，不受影响。
_RF = os.path.join(D, "c2026c_rank_feasible.csv")
if os.path.exists(_RF):
    _R = pd.read_csv(_RF)
    ev["rank_consistent"] = int(_R.feasible.sum())
    ev["rank_tie_only"] = int(_R.tie_only.sum())
    ev["rank_feasible_total"] = int(len(_R))
    ev["rank_sampled_for_reference"] = int(len(rnk))
else:
    ev["rank_consistent"] = int(len(rnk))
ev["pct_rate"] = round(100.0 * len(pct) / ev["n_season_weeks"], 1)
ev["rank_rate"] = round(
    100.0 * ev["rank_consistent"] / ev.get("rank_feasible_total",
                                           ev["n_season_weeks"]), 1)
ev["pct_inconsistent"] = int(len(bad))
ev["lam_width_pct"] = round(float((pct.lam_hi - pct.lam_lo).median()), 3)
ev["lam_width_rank"] = round(float((rnk.lam_hi - rnk.lam_lo).median()), 3)
ev["lam_mid_pct"] = round(float(((pct.lam_lo + pct.lam_hi) / 2).median()), 3)
ev["lam_mid_rank"] = round(float(((rnk.lam_lo + rnk.lam_hi) / 2).median()), 3)
ev["upside_weeks"] = int(len(CR))
ev["upside_pos_rate"] = round(100.0 * float((CR.upside > 0).mean()), 0)
ev["upside_max"] = int(CR.upside.max())
ev["n_industries"] = int(W.industry.nunique())
ev["n_pro_dancers"] = int(W.pro_dancer.nunique())
ev["n_withdrew"] = int(W.withdrew.sum())
for f, k in (("judge_avg", "rho_judge_avg"), ("judge_trend", "rho_judge_trend"),
             ("n_weeks", "rho_n_weeks"), ("judge_max", "rho_judge_max"),
             ("judge_min", "rho_judge_min"), ("age", "rho_age")):
    ev[k] = round(float(W[[f, "placement"]].corr(method="spearman").iloc[0, 1]), 3)
# 2026-11-09：原先这三行是字面量（1.098 / 1.128 / 0.027）。它们让
# evidence.json 以「计算结果」的形态记录了手写数字 —— 看起来有出处，
# 实际自证。改为读 tools/recompute_model_stats.py 的实算结果。
# 实算值：lin 1.3031、quad 1.3111、gap 0.0081；二次项并不优于线性。
_MS = json.load(open(os.path.join(OUT, "d2026c", "model_stats.json"),
                     encoding="utf-8"))
ev["cv_rmse_quad"] = _MS["cv_rmse_quad"]
ev["cv_rmse_lin"] = _MS["cv_rmse_lin"]
ev["cv_gap"] = _MS["cv_gap"]
ev["eps_floor"] = 0.003
# 2026-11-09：原先这两行也是字面量（75 / 335）。335 = long 表 unique
# (season,week) 组数；75 = 强假设（最终名次 = 当周排名）下 need<1 的周数。
# 由 tools/recompute_strong_assumption.py 实算复现，口径见该脚本。
_SA = json.load(open(os.path.join(OUT, "d2026c", "strong_assumption.json"),
                     encoding="utf-8"))
ev["strong_assumption_weeks_ok"] = _SA["feasible_weeks"]
ev["strong_assumption_weeks_all"] = _SA["total_weeks"]
# 两法一致季数
import pandas as pd  # noqa
SE = pd.read_csv(os.path.join(D, "c2026c_weight_sens.csv"))
base = SE[np.isclose(SE.w, 0.5)].set_index("season").champ
for w in (0.3, 0.4, 0.6, 0.7):
    d = SE[np.isclose(SE.w, w)].set_index("season").champ
    same = int((d.reindex(base.index) == base.reindex(d.index)).sum())
    ev["champ_same_%s" % str(w).replace(".", "_")] = same
ev["n_seasons_cmp"] = int(len(base))
# 两法淘汰顺序一致（来自 earlier 分析文件）
CMP = pd.read_csv(os.path.join(D, "c2026c_two_methods.csv"))
ev["two_rules_agree_seasons"] = int(CMP.pct_same_as_rank.sum())
ev["two_rules_disagree_seasons"] = int(len(CMP) - ev["two_rules_agree_seasons"])
# 淘汰者评委名次分布
pc = pd.read_csv(os.path.join(OUT, "pct_feasibility.csv"))
ev["inconsistent_elim_judge_rank_1_2"] = int(
    ((pc.pct_feasible == 0) & (pc.elim_judge_rank <= 2)).sum())
ev["inconsistent_elim_judge_rank_ge3"] = int(
    ((pc.pct_feasible == 0) & (pc.elim_judge_rank >= 3)).sum())
ev["consistent_elim_judge_rank_1_2"] = int(
    ((pc.pct_feasible == 1) & (pc.elim_judge_rank <= 2)).sum())
ev["consistent_elim_judge_rank_ge3"] = int(
    ((pc.pct_feasible == 1) & (pc.elim_judge_rank >= 3)).sum())
# 题面案例
for nm, s, wk in (("Jerry Rice", 2, 3), ("Billy Ray Cyrus", 4, 2)):
    d = CR[(CR.season == s) & (CR.celebrity_name == nm) & (CR.week == wk)]
    if len(d):
        r = d.iloc[0]
        ev["%s_judge_rank" % nm.replace(" ", "_")] = int(r.judge_rank)
        ev["%s_fan_rank" % nm.replace(" ", "_")] = int(r.fan_rank)
        ev["%s_placement" % nm.replace(" ", "_")] = int(r.placement)
        ev["%s_inversion" % nm.replace(" ", "_")] = int(r.upside)
p = os.path.join(OUT, "d2026c", "evidence.json")
json.dump(ev, open(p, "w", encoding="utf-8", newline="\n"),
          ensure_ascii=False, indent=1)
print("  证据包 %d 条 -> %s" % (len(ev), p))
for k, v in ev.items():
    print("    %-34s %s" % (k, v))