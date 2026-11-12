"""观众权重扫描：周级复现率随权重变化。

为什么替换旧的「整季模拟冠军」做法
----------------------------------
旧实现在 tools/c2026_analysis.py 里用 simulate() 推演整季、取 alive[0] 当冠军。
两个致命问题（2026-11-10 实测）：
  1. 剩 <=2 人就 break，最后两人从未被淘汰，alive[0] 只是名字列表第一个
     —— 与真实冠军 34 季只对上 1 季；
  2. 循环必须用真实离场周 exitw 过滤 live（否则后续周没有 judge_score），
     于是真实已离开的人仍留在 alive，模拟无法把 alive 收到 1 人
     —— 修完后 champ 列 714/714 全空。
结论：在「必须借用真实离场信息」的约束下，整季模拟无法定义冠军。
所以改为**周级**口径：对每个权重 w，看当周预测的淘汰者是否等于真实淘汰者。

口径
----
对每周（有重建份额、且该周恰有 1 人被淘汰）：
    c_i(w) = (1-w) * Jn_i + w * p_i
    预测淘汰者 = argmin c(w)
    命中 = 预测者 == 真实淘汰者
其中 Jn 是评委分在该周内的 min-max 归一化，p 是重建份额的代表点（p_est）。
**judge_score == 0 的行必须剔除**：那是缺席被填 0，不剔除会让 argmin 落在
不在场的人身上（实测会把准确率从 95.9% 压到 11.9%）。

产出
----
out/data/c2026c_weight_curve.csv   w, hit, total, rate
stdout                             曲线 + 峰值位置
"""
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(HERE, "out", "data")


def build_weeks():
    L = pd.read_excel(os.path.join(D, "dwts2026c_long.xlsx"))
    B = pd.read_csv(os.path.join(HERE, "out", "fanvote_bounds.csv"))
    piv = B.pivot_table(index=["season", "week"], columns="celebrity_name",
                        values="p_est")
    rows = []
    for (s, w), g in L.groupby(["season", "week"]):
        if (s, w) not in piv.index:
            continue
        g = g.dropna(subset=["judge_score"])
        g = g[g.judge_score > 0]          # 剔除缺席填 0
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
        truth = int(np.where(g.eliminated.to_numpy() == 1)[0][0])
        rows.append(dict(season=s, week=w, Jn=Jn, p=p, truth=truth))
    return rows


def main():
    weeks = build_weeks()
    out = []
    for w in np.round(np.arange(0, 1.0001, 0.05), 2):
        hit = sum(1 for r in weeks
                  if int(np.argmin((1 - w) * r["Jn"] + w * r["p"])) == r["truth"])
        out.append(dict(w=float(w), hit=hit, total=len(weeks),
                        rate=round(100.0 * hit / len(weeks), 2)))
    df = pd.DataFrame(out)
    p = os.path.join(D, "c2026c_weight_curve.csv")
    df.to_csv(p, index=False)

    print("观众权重扫描（周级复现率）")
    print("  可评估季-周：%d" % len(weeks))
    print()
    print("  %-6s %-8s %s" % ("w", "命中", "比例"))
    for r in out:
        mark = "  <== 峰值" if r["hit"] == df.hit.max() else ""
        print("  %.2f   %3d/%-3d %6.2f%%%s" % (r["w"], r["hit"], r["total"],
                                               r["rate"], mark))
    best = df.loc[df.hit.idxmax()]
    print()
    print("  峰值 w=%.2f，%d/%d = %.2f%%" % (best.w, best.hit, best.total, best.rate))
    for dw in (0.05, 0.10, 0.20):
        lo = df[np.isclose(df.w, round(best.w - dw, 2))]
        hi = df[np.isclose(df.w, round(best.w + dw, 2))]
        if len(lo) and len(hi):
            print("  w 偏离 ±%.2f：%.2f%% / %.2f%%（掉 %.1f / %.1f 个百分点）"
                  % (dw, lo.rate.iloc[0], hi.rate.iloc[0],
                     best.rate - lo.rate.iloc[0], best.rate - hi.rate.iloc[0]))
    print("\n  写出 %s" % p)


if __name__ == "__main__":
    main()
