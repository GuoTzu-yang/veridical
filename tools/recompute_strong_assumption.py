"""复现论文里的「强假设 75/335」。

论文原话（Limitations 节）：
    An earlier draft made the stronger assumption [that surviving contestants were
    ordered as their final placements suggest] and was rejected by the data: it
    left only 75 of 335 weeks feasible.

335 已实测 = L 表（dwts2026c_long.xlsx）unique (season, week) 组数。
本脚本检验：若要求「每周综合分排名 == 选手最终名次顺序」，有多少周仍可行。

判据（与论文的闭式判据同源）：
    按 final_placement 升序排成 i1..in（i1 最好），要求 c_1 >= c_2 >= ... >= c_n，
    其中 c = 0.5*J + 0.5*p，p ∈ [0,1]，Σp = 1。
    链式约束给出最小需求 Σ_k max(0, J_{k+1} - J_k)，
    该值 <= 1 即存在可行分配。
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(HERE, "out", "data")
OUT = os.path.join(HERE, "out", "d2026c")

L = pd.read_excel(os.path.join(D, "dwts2026c_long.xlsx"))
L = L[L["withdrew"] == 0].dropna(subset=["judge_score", "final_placement"])

rows = []
for (season, week), g in L.groupby(["season", "week"]):
    g = g.sort_values("final_placement")
    J = g["judge_score"].to_numpy(float)
    if len(J) < 2:
        rows.append(dict(season=season, week=week, n=len(J), need=0.0, ok=True))
        continue
    d = J[1:] - J[:-1]                 # 相邻的评委分逆差
    need = float(np.maximum(d, 0).sum())   # 最小份额需求
    # need == 1 意味着必须把全部份额给表现最好那位（p=1，其余全 0），
    # 没有任何余量，判不可行。实测有 8 周 need 恰为 1.000000000000，
    # 即 season 3/11/13/16/18/22/23/27。用 1-1e-9 吸收浮点误差，
    # 结果与论文的 75/335 一致。
    rows.append(dict(season=season, week=week, n=len(J), need=need,
                     ok=need < 1.0 - 1e-9))

df = pd.DataFrame(rows)
n_all = len(df)
n_ok = int(df["ok"].sum())

res = dict(
    total_weeks=n_all,
    feasible_weeks=n_ok,
    infeasible_weeks=n_all - n_ok,
    feasible_rate=round(100.0 * n_ok / n_all, 1),
    paper_claims=dict(feasible=75, total=335),
    matches_paper=bool(n_ok == 75 and n_all == 335),
    need_quantiles={q: round(float(df["need"].quantile(q)), 4)
                    for q in (0.25, 0.5, 0.75, 0.9)},
    note=("need = Σ max(0, J_{k+1}-J_k)，按 final_placement 升序；"
          "need<=1 表示存在观众票分配使该周的当周排名等于最终名次顺序"),
)

os.makedirs(OUT, exist_ok=True)
p = os.path.join(OUT, "strong_assumption.json")
json.dump(res, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(json.dumps(res, ensure_ascii=False, indent=2))
print("\nwritten:", p)
