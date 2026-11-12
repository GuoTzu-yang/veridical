import os
import re
import warnings
warnings.filterwarnings("ignore")
import pandas as pd
import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "external", "github", "li1408__MathModelHub",
                   "competitions", "2026_MCM_Problem_C_Data.csv")
OUT = os.path.join(HERE, "out", "data")
os.makedirs(OUT, exist_ok=True)
d = pd.read_csv(SRC)

JC = [c for c in d.columns if re.match(r"^week\d+_judge\d+_score$", c)]
JNUM = {}
for c in JC:
    m = re.match(r"^week(\d+)_judge(\d+)_score$", c)
    JNUM.setdefault(int(m.group(1)), []).append(c)

def elim_week(r):
    m = re.match(r"^Eliminated Week (\d+)$", str(r["results"]))
    return int(m.group(1)) if m else 0

rows = []
for _, r in d.iterrows():
    wk = {}
    tot = {}
    for w, cols in sorted(JNUM.items()):
        vals = [r[c] for c in cols if pd.notna(r[c])]
        if vals:
            wk[w] = float(np.mean(vals))
            tot[w] = float(np.sum(vals))
    ew = elim_week(r)
    last_w = max(wk) if wk else 0
    # 参赛周数：到被淘汰周（含），冠军/亚军到最后一周
    n_w = ew if ew else last_w
    placed = str(r["results"]) in ("1st Place", "2nd Place", "3rd Place",
                                   "4th Place", "5th Place")
    rows.append(dict(
        celebrity_name=str(r["celebrity_name"]),
        pro_dancer=str(r["ballroom_partner"]),
        industry=str(r["celebrity_industry"]),
        age=int(r["celebrity_age_during_season"]),
        home_region=str(r["celebrity_homecountry/region"]),
        season=int(r["season"]),
        result=str(r["results"]),
        placement=int(r["placement"]) if pd.notna(r["placement"]) else 0,
        eliminated_week=ew,
        withdrew=1 if str(r["results"]) == "Withdrew" else 0,
        n_weeks=int(n_w),
        last_week=int(last_w),
        judge_avg=float(np.mean(list(wk.values()))) if wk else np.nan,
        judge_first=float(np.mean([wk[w] for w in wk if w == 1])) if 1 in wk else np.nan,
        judge_last=float(wk[last_w]) if last_w else np.nan,
        judge_max=float(max(wk.values())) if wk else np.nan,
        judge_min=float(min(wk.values())) if wk else np.nan,
        judge_trend=float(np.mean(list(wk.values())) - np.mean(list(wk.values())[:2]))
        if len(wk) >= 3 else np.nan,
        # 每周评委分拼成一个字符串列（反演用），如 w1:7.5|w2:8.2
        weekly_judge="|".join("w%d:%.4f" % (w, wk[w]) for w in sorted(wk)),
    ))
wide = pd.DataFrame(rows)
wide.to_excel(os.path.join(OUT, "dwts2026c.xlsx"), index=False)
print("  宽表: %s" % (wide.shape,))
print("  列: %s" % list(wide.columns))

# 长表：每周一位选手
lrows = []
for _, r in wide.iterrows():
    if not r["weekly_judge"]:
        continue
    for part in str(r["weekly_judge"]).split("|"):
        w, v = part.split(":")
        w = int(w[1:])
        alive_after = (r["eliminated_week"] == 0) or (w < r["eliminated_week"])
        lrows.append(dict(
            celebrity_name=r["celebrity_name"], pro_dancer=r["pro_dancer"],
            industry=r["industry"], age=r["age"], season=r["season"],
            week=w, judge_score=float(v),
            eliminated=(1 if (r["eliminated_week"] == w) else 0),
            withdrew=int(r["withdrew"]),
            alive_after=int(alive_after),
            final_placement=int(r["placement"]),
        ))
long = pd.DataFrame(lrows)
long.to_excel(os.path.join(OUT, "dwts2026c_long.xlsx"), index=False)
print("  长表: %s" % (long.shape,))
print("  淘汰周分布:", long[long.eliminated == 1].week.value_counts().sort_index().to_dict())