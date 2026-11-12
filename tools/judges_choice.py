"""judges' choice 的定量检验（填补 §4 只有定性推理的缺口）。

机制
----
现行规则：综合分最低者自动淘汰。
judges' choice：先把综合分最低的两人选出（bottom two），再由评委在这两人中定夺。
因为评委在两人之间当然保自己给分高的，所以该规则等价于
    「在 bottom two 里淘汰评委分较低的那一个」。

口径
----
综合分用 c = ½ Jn + ½ p_est（与 P1/P2 同一口径），p_est 取自 fanvote_bounds.csv
（可行样本中的代表性点）。判定「该规则是否复现观测淘汰」，与 83.5% 那个指标同源，
所以两个数可以直接比较。

用法
    python tools/judges_choice.py
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(HERE, "out", "data")


def main():
    L = pd.read_excel(os.path.join(D, "dwts2026c_long.xlsx"))
    B = pd.read_csv(os.path.join(HERE, "out", "fanvote_bounds.csv"))
    piv = B.pivot_table(index=["season", "week"], columns="celebrity_name",
                        values="p_est")
    rows = []
    for (s, w), g in L.groupby(["season", "week"]):
        if (s, w) not in piv.index:
            continue
        g = g.dropna(subset=["judge_score", "final_placement"])
        g = g[g.judge_score > 0]
        if len(g) < 3 or int(g.eliminated.sum()) != 1:
            continue
        names = list(g.celebrity_name)
        J = g.judge_score.to_numpy(float)
        Jn = ((J - J.min()) / (J.max() - J.min())) if J.max() > J.min() else np.zeros(len(J))
        row = piv.loc[(s, w)]
        p = np.array([float(row[n]) if n in row.index and not pd.isna(row[n])
                      else 1.0 / len(names) for n in names])
        if p.sum() <= 0:
            continue
        p = p / p.sum()
        c = 0.5 * Jn + 0.5 * p
        order = np.argsort(c)                     # 综合分从低到高
        b1, b2 = int(order[0]), int(order[1])
        # 评委在两人中保自己给分更高的，即淘汰 Jn 较低者
        jc = b1 if Jn[b1] <= Jn[b2] else b2
        truth = int(np.where(g.eliminated.to_numpy() == 1)[0][0])
        # 现行规则 = argmin(c)
        auto = b1
        rows.append(dict(season=int(s), week=int(w), n=len(np.atleast_1d(J)),
                         auto_hit=int(auto == truth),
                         judge_hit=int(jc == truth),
                         differ=int(jc != auto),
                         truth_in_bottom2=int(truth in (b1, b2))))
    df = pd.DataFrame(rows)
    n = len(df)
    out = dict(
        weeks=n,
        auto_rate=round(100.0 * df.auto_hit.sum() / n, 1),
        judges_choice_rate=round(100.0 * df.judge_hit.sum() / n, 1),
        weeks_rule_differs=int(df.differ.sum()),
        truth_in_bottom_two=round(100.0 * df.truth_in_bottom2.sum() / n, 1),
        note=("综合分 c = ½Jn + ½p_est；judges' choice 等价于「bottom two 中淘汰"
              "评委分较低者」；auto 是现行「综合分最低者淘汰」"),
    )
    p = os.path.join(D, "c2026c_judges_choice.csv")
    df.to_csv(p, index=False)
    print("judges' choice 定量检验")
    print("  可评估季-周            : %d" % n)
    print("  现行规则复现率         : %.1f%%  (%d/%d)"
          % (out["auto_rate"], int(df.auto_hit.sum()), n))
    print("  judges' choice 复现率  : %.1f%%  (%d/%d)"
          % (out["judges_choice_rate"], int(df.judge_hit.sum()), n))
    print("  两条规则给出不同淘汰的周: %d" % out["weeks_rule_differs"])
    print("  观测淘汰者在 bottom two 内: %.1f%%" % out["truth_in_bottom_two"])
    print("\n  写出 %s" % p)
    json.dump(out, open(os.path.join(D, "c2026c_judges_choice.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
