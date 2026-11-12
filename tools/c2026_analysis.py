import os
import json
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "out", "data")
os.makedirs(OUT, exist_ok=True)

L = pd.read_excel(os.path.join(HERE, "out", "data", "dwts2026c_long.xlsx"))
W = pd.read_excel(os.path.join(HERE, "out", "data", "dwts2026c.xlsx"))
B = pd.read_csv(os.path.join(HERE, "out", "fanvote_bounds.csv"))
LAM = pd.read_csv(os.path.join(HERE, "out", "fanvote_lam.csv"))

# 复合键：跨季重名的选手（Kelly Monaco 等）必须用 (season, name)
W["_k"] = list(zip(W.season, W.celebrity_name))
L["_k"] = list(zip(L.season, L.celebrity_name))
B["_k"] = list(zip(B.season, B.celebrity_name))
place = dict(zip(W["_k"], W.placement))
exitw = dict(zip(W["_k"], np.where(W.eliminated_week > 0, W.eliminated_week, W.last_week)))
S = {}

# ── 1. 一致性：两种合并法各能复现多少季-周的淘汰结果 ──
for m in ("pct", "rank"):
    d = LAM[(LAM.method == m) & (LAM.ok == 1)]
    S["feasible_%s" % m] = round(100 * len(d) / int((LAM.method == m).sum()), 1)
    S["lam_width_%s" % m] = round(float(d.width.median()), 3)
    S["lam_mid_%s" % m] = round(float(((d.lam_lo + d.lam_hi) / 2).median()), 3)
    S["weeks_%s" % m] = int((LAM.method == m).sum())
S["weeks_total"] = int((LAM.method == "pct").sum())

# ── 2. controversy：评委名次 vs 观众名次的倒挂 ──
rows = []
for (s, w), g in B.groupby(["season", "week"]):
    if len(g) < 3:
        continue
    g = g.sort_values("p_est", ascending=False).reset_index(drop=True)
    g["fan_rank"] = np.arange(1, len(g) + 1)
    for _, r in g.iterrows():
        rows.append(dict(season=s, week=w, celebrity_name=r.celebrity_name,
                         placement=int(r.placement), judge_rank=int(r.judge_rank),
                         fan_rank=int(r.fan_rank),
                         upside=int(r.judge_rank) - int(r.fan_rank),
                         judge=float(r.judge), n=int(r.n),
                         p_lo=float(r.p_lo), p_hi=float(r.p_hi)))
CR = pd.DataFrame(rows)
CR.to_csv(os.path.join(OUT, "c2026c_controversy.csv"), index=False)
S["upside_mean"] = round(float(CR.upside.mean()), 3)
S["upside_pos_frac"] = round(100 * float((CR.upside > 0).mean()), 1)
S["upside_max"] = int(CR.upside.max())

# ── 3. 两法对比：同一份 fan vote 估计，换合并法会不会改结果 ──
piv = B.pivot_table(index=["season", "week"], columns="celebrity_name", values="p_est")
def simulate(s, method, wfan):
    """按给定合并法模拟整季，返回 (淘汰顺序, 最终名次映射)。

    起点必须是该季**第一个真的有人被淘汰的周**。数据里第 1 周常常
    无人淘汰（例如季 1 共 6 人，placement 6 的 Trista 是第 2 周才出局），
    若从 W1 就开始淘汰，会与真实淘汰周整体错开一位，整季比对全错。
    """
    names = W[W.season == s].celebrity_name.tolist()
    alive = list(names)
    order = []
    first = W[(W.season == s) & (W.eliminated_week > 0)].eliminated_week.min()
    if not np.isfinite(first):
        first = 1
    for wk in range(int(first), 12):
        live = [n for n in alive if exitw[(s, n)] >= wk]
        # 2026-11-10 修：原来是 <=2 就 break，于是最后两人从未被淘汰，
        # 而下游把 alive[0] 当冠军 —— alive[0] 只是名字列表的第一个。
        # 实测与真实冠军 34 季只对上 1 季。必须模拟到只剩 1 人。
        if len(live) <= 1:
            break
        row = piv.loc[(s, wk)] if (s, wk) in piv.index else None
        # 2026-11-10 修：原实现在该周没有重建份额时直接 break，导致模拟
        # 提前终止（piv 只覆盖 193/335 周，实测 11/34 季一步没走）。
        # 缺份额时退到均匀分布继续推演，而不是放弃整季。
        if row is None:
            p = np.full(len(live), 1.0 / len(live))
        else:
            p = np.array([float(row[n]) if n in row.index and not pd.isna(row[n])
                          else 1.0 / len(live) for n in live])
            p = p / p.sum()
        J = np.array([float(L[(L.season == s) & (L.week == wk) &
                              (L.celebrity_name == n)].judge_score.iloc[0])
                      for n in live])
        n = len(live)
        Jn = (J - J.min()) / (J.max() - J.min()) if J.max() > J.min() else np.zeros(n)
        if method == "pct":
            c = (1 - wfan) * Jn + wfan * p
            worst = int(np.argmin(c))
        else:
            rJ = np.empty(n); o = np.argsort(-J); rJ[o] = np.arange(1, n + 1)
            rp = np.empty(n); o2 = np.argsort(-p); rp[o2] = np.arange(1, n + 1)
            c = (1 - wfan) * rJ + wfan * rp
            worst = int(np.argmax(c))
        order.append((wk, live[worst]))
        alive = [x for x in alive if x != live[worst]]
    return order, alive

# 3a. 真实淘汰顺序（按 placement 排 = 名次从好到差 = 淘汰从晚到早）
real_order = {}
for s in sorted(W.season.unique()):
    dd = W[W.season == s].sort_values("placement")
    real_order[s] = dd.celebrity_name.tolist()

cmp_rows = []
for s in sorted(W.season.unique()):
    o_pct, _ = simulate(s, "pct", 0.5)
    o_rank, _ = simulate(s, "rank", 0.5)
    seq_pct = [nm for _, nm in o_pct]
    seq_rank = [nm for _, nm in o_rank]
    real = real_order[s]
    # 真实淘汰顺序：placement 降序（先出局的名次差）
    real_seq = list(reversed(real))
    cmp_rows.append(dict(
        season=s,
        pct_match=int(sum(a == b for a, b in zip(seq_pct, real_seq))),
        rank_match=int(sum(a == b for a, b in zip(seq_rank, real_seq))),
        pct_len=len(seq_pct), rank_len=len(seq_rank), real_len=len(real_seq),
        pct_same_as_rank=int(seq_pct == seq_rank)))
CMP = pd.DataFrame(cmp_rows)
CMP.to_csv(os.path.join(OUT, "c2026c_two_methods.csv"), index=False)
S["pct_exact_seasons"] = int((CMP.pct_match == CMP.real_len).sum())
S["rank_exact_seasons"] = int((CMP.rank_match == CMP.real_len).sum())
S["pct_agree_with_rank"] = int(CMP.pct_same_as_rank.sum())
S["seasons_total"] = int(len(CMP))

# 3b. 权重敏感度：观众权重从 0 到 1，冠军会变吗
sens = []
for s in sorted(W.season.unique()):
    for w in np.arange(0, 1.001, 0.05):
        _, alive = simulate(s, "pct", float(w))
        sens.append(dict(season=s, w=round(float(w), 2),
                         # 冠军只可能是「模拟淘汰到只剩 1 人」的那个幸存者。
                         # 早期版本写 alive[0]，而 break 在剩 2 人时就触发，
                         # 于是 alive[0] 只是名字列表第一个，与冠军无关。
                         champ=alive[0] if len(alive) == 1 else ""))
SE = pd.DataFrame(sens)
SE.to_csv(os.path.join(OUT, "c2026c_weight_sens.csv"), index=False)
base = SE[np.isclose(SE.w, 0.5)].set_index("season").champ
for w in (0.3, 0.4, 0.6, 0.7):
    d = SE[np.isclose(SE.w, w)].set_index("season").champ
    same = int((d.reindex(base.index) == base.reindex(d.index)).sum())
    S["champ_same_w%.1f" % w] = "%d/%d (%.0f%%)" % (same, len(d), 100 * same / len(d))

# ── 4. 因素影响 ──
for f in ("judge_avg", "age", "n_weeks", "judge_max", "judge_min", "judge_trend"):
    if f in W.columns:
        S["rho_" + f] = round(float(W[[f, "placement"]].corr(method="spearman").iloc[0, 1]), 3)
ind = W.groupby("industry").placement.agg(["mean", "count"]).sort_values("mean")
S["n_industries"] = int(W.industry.nunique())
S["n_pro_dancers"] = int(W.pro_dancer.nunique())
S["industry_worst"] = str(ind.tail(1).index[0])
S["industry_best"] = str(ind.head(1).index[0])

# ── 5. 汇总输出 ──
with open(os.path.join(HERE, "out", "c2026c_summary.json"), "w", encoding="utf-8",
          newline="\n") as fh:
    json.dump(S, fh, ensure_ascii=False, indent=1)
for k, v in S.items():
    print("  %-26s %s" % (k, v))
print()
print("  === controversy 倒挂最大的 10 位 ===")
print(CR.sort_values("upside", ascending=False).head(10)[
    ["celebrity_name", "season", "week", "placement", "judge_rank", "fan_rank", "upside"]
].to_string(index=False))
print()
print("  === 题面点名的四个案例 ===")
for nm, s in [("Jerry Rice", 2), ("Billy Ray Cyrus", 4),
              ("Bristol Palin", 11), ("Bobby Bones", 27)]:
    d = CR[(CR.season == s) & (CR.celebrity_name == nm)]
    if d.empty:
        print("    %-16s 数据中无此人" % nm)
        continue
    for _, r in d.iterrows():
        print("    %-16s S%-3d W%-2d 名次%2d 评委名次%2d 观众名次%2d 倒挂%+d"
              % (nm, s, int(r.week), int(r.placement), int(r.judge_rank),
                 int(r.fan_rank), int(r.upside)))
