import json
import os
import warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "out")
D = os.path.join(OUT, "data")
L = pd.read_excel(os.path.join(D, "dwts2026c_long.xlsx"))
W = pd.read_excel(os.path.join(D, "dwts2026c.xlsx"))
B = pd.read_csv(os.path.join(OUT, "fanvote_bounds.csv"))
W["_k"] = list(zip(W.season, W.celebrity_name))
exitw = dict(zip(W["_k"], np.where(W.eliminated_week > 0, W.eliminated_week, W.last_week)))

def d_rank(v):
    v = np.asarray(v, float)
    o = np.argsort(-v, kind="mergesort")
    r = np.empty(len(v)); r[o] = np.arange(1, len(v) + 1)
    u = {}
    for i, x in enumerate(v):
        u.setdefault(x, []).append(i)
    for x, idx in u.items():
        if len(idx) > 1:
            r[idx] = np.mean(r[idx])
    return r

# 逐周：同一份 p 估计，两法各算一次淘汰者，看是否相同
same = diff = 0
diff_rows = []
for (s, w), g in B.groupby(["season", "week"]):
    if len(g) < 3:
        continue
    g = g.sort_values("p_est", ascending=False)
    J = g.judge.values.astype(float)
    p = g.p_est.values.astype(float)
    p = p / p.sum()
    n = len(J)
    Jn = (J - J.min()) / (J.max() - J.min()) if J.max() > J.min() else np.zeros(n)
    e_pct = int(np.argmin(0.5 * Jn + 0.5 * p))
    e_rnk = int(np.argmax(0.5 * d_rank(J) + 0.5 * d_rank(p)))
    if e_pct == e_rnk:
        same += 1
    else:
        diff += 1
        diff_rows.append(dict(season=s, week=w, n=n,
                              pct_out=g.celebrity_name.iloc[e_pct],
                              rank_out=g.celebrity_name.iloc[e_rnk]))
tot = same + diff
print("  === 逐周两法分歧（同一份 p 估计）===")
print("  共 %d 周；两法给出相同淘汰者 %d 周 (%.1f%%)，不同 %d 周 (%.1f%%)"
      % (tot, same, 100 * same / tot, diff, 100 * diff / tot))

# 分歧时，哪一法淘汰的人评委分更差
worse = []
for r in diff_rows:
    g = B[(B.season == r["season"]) & (B.week == r["week"])]
    j = dict(zip(g.celebrity_name, g.judge))
    if r["pct_out"] in j and r["rank_out"] in j:
        worse.append(j[r["pct_out"]] - j[r["rank_out"]])
worse = np.array(worse)
print("  分歧周中，rank 法淘汰者的评委分更低（rank 更严）: %d / %d (%.0f%%)"
      % ((worse < 0).sum(), len(worse), 100 * (worse < 0).mean()))

ev = json.load(open(os.path.join(OUT, "d2026c", "evidence.json"), encoding="utf-8"))
ev.pop("two_rules_agree_seasons", None)
ev.pop("two_rules_disagree_seasons", None)
ev["week_level_total"] = tot
ev["week_level_same"] = same
ev["week_level_diff"] = diff
ev["week_level_same_rate"] = round(100 * same / tot, 1)
ev["week_level_rank_stricter_rate"] = round(100 * float((worse < 0).mean()), 0)
json.dump(ev, open(os.path.join(OUT, "d2026c", "evidence.json"), "w",
                   encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
pd.DataFrame(diff_rows).to_csv(os.path.join(D, "c2026c_week_disagree.csv"), index=False)
print("  证据包已更新（%d 条）" % len(ev))