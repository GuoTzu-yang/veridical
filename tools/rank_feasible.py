"""rank 法可行性的确定性判定（替代 3000 次拒绝采样）。

背景
----
论文原报「ranking rule 224/231 = 97.0%」，实现是 `tools/final_bounds.py` 里
对每周抽 3000 个 Dirichlet 份额、看有没有一个能让淘汰者综合分最差。
实测（2026-11-10）这个数字**依赖随机种子**：seed 2026 -> 225，seed 2 -> 223，
seed 7 -> 225。也就是说 97.0% 是**采样估计**，不是精确值。

为什么可以精确判定
------------------
rank 法的综合分 c_i = ½ rJ_i + ½ rp_i，要求淘汰者 e 的 c 最大。
最有利的情形是让 e 的观众名次最差（rp_e = n = 人数），此时其余 n-1 人分得
名次 1..n-1，每人需要
        rJ_i + rp_i <= rJ_e + n     即   rp_i <= ub_i := rJ_e + n - rJ_i
存在这样一个名次分配，当且仅当把 {ub_i} 升序排列后第 j 个 >= j（Hall 条件）。

无法满足时，再检查是否是「仅并列」：e 能达到的最大 c 是否恰好等于某个对手
能达到的最小 c。并列意味着 argmax 取决于排序，不是真正的不可行。

用法
    python tools/rank_feasible.py            # 统计
    python tools/rank_feasible.py --json
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(HERE, "out", "data")


def week_rows():
    """与 tools/final_bounds.py 相同的周筛选，保证分母对齐（231 周）。"""
    L = pd.read_excel(os.path.join(D, "dwts2026c_long.xlsx"))
    out = []
    for (s, w), g in L.groupby(["season", "week"]):
        # 必须**先**判淘汰人数，再剔 0 分缺席行。顺序反了会多算一周：
        # S18W2 有两人 eliminated=1（Sean Avery + Diana Nyad），后者
        # judge_score=0 属缺席/退赛；先剔 0 分就只剩 1 个标记，该周被误留，
        # 分母从 231 变成 232。tools/final_bounds.py 是先判人数，故排除该周。
        if int(g.eliminated.sum()) != 1:
            continue
        g = g.dropna(subset=["judge_score", "final_placement"])
        g = g[g.judge_score > 0]                 # 剔除缺席填 0
        if len(g) < 3:
            continue
        g = g.sort_values("final_placement").reset_index(drop=True)
        J = g.judge_score.to_numpy(float)
        rJ = np.empty(len(J))
        rJ[np.argsort(-J)] = np.arange(1, len(J) + 1)
        e = int(np.where(g.eliminated.to_numpy() == 1)[0][0])
        out.append(dict(season=int(s), week=int(w), n=len(g), e=e,
                        rJ=rJ, J=J))
    return out


def judge(r):
    """返回 (strict_ok, tie_only)。

    注意「e 是最差」要**严格**：c_i < c_e 对所有 i≠e。
    c = ½(rJ + rp) 是整数的一半，所以严格等价于 rJ_i + rp_i <= rJ_e + n - 1。
    早期版本用了 <= rJ_e + n（允许并列），结果 S14W9 这类四人对齐的情形被
    误判为可行 —— 那里的实际 c 全部等于 2.5。
    """
    rJ, e, n = r["rJ"], r["e"], r["n"]
    ub = []
    for i in range(n):
        if i == e:
            continue
        u = int(rJ[e] + n - 1 - rJ[i])
        u = min(u, n - 1)
        if u < 1:
            ub = None
            break
        ub.append(u)
    if ub is not None:
        ub.sort()
        if all(ub[j] >= j + 1 for j in range(len(ub))):
            return True, False
    # 不可严格满足：看是不是恰好并列
    e_worst = 0.5 * rJ[e] + 0.5 * n                  # e 能达到的最大 c
    opp_best = max(0.5 * rJ[i] + 0.5 for i in range(n) if i != e)  # 对手最小 c
    return False, bool(abs(e_worst - opp_best) < 1e-12)


def main(as_json=False):
    rows = week_rows()
    res = []
    for r in rows:
        ok, tie = judge(r)
        res.append(dict(season=r["season"], week=r["week"], n=r["n"],
                        e=r["e"], feasible=ok, tie_only=tie))
    df = pd.DataFrame(res)
    total = len(df)
    strict = int(df.feasible.sum())
    ties = int(df.tie_only.sum())
    out = dict(
        total_weeks=total,
        strictly_feasible=strict,
        strictly_rate=round(100.0 * strict / total, 1),
        tie_only=ties,
        infeasible_other=total - strict - ties,
        sampled_seed2026=225,
        note=("全部为确定性判定，无随机采样；tie_only 表示 e 能达到的最大综合分"
              "恰好等于某对手的最小综合分，此时 argmax 取决于排序"),
    )
    p = os.path.join(D, "c2026c_rank_feasible.csv")
    df.to_csv(p, index=False)
    if as_json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return
    print("rank 法可行性（确定性判定）")
    print("  可评估周数      : %d" % total)
    print("  严格可行        : %d (%.1f%%)" % (strict, out["strictly_rate"]))
    print("  仅并列          : %d" % ties)
    print("  真正不可行      : %d" % out["infeasible_other"])
    print("  对照：采样 3000 次得 225/%d = %.1f%%（换种子 223–225）"
          % (total, 100.0 * 225 / total))
    if ties:
        print("\n  并列周：")
        print(df[df.tie_only][["season", "week", "n"]].to_string(index=False))
    print("\n  写出 %s" % p)


if __name__ == "__main__":
    import sys
    main("--json" in sys.argv)
