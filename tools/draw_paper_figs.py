"""按论文 caption 重画 fig1-4（原 PNG 与数据/caption 不符）。

原状（实测）：
  fig1 把 193 个季-周压成 11 列，与 caption 的「5th-95th percentile per week」不符
  fig2 没有对角线，而 caption 明确说「above the diagonal」
  fig3 的 x 轴写成 "displacement (standard deviations)"，实际是观众权重 w∈[0,1]
  fig4 是一块「Entropy weights」单色块，与 caption 的「两法一致率」毫无关系

数据源：out/data/fig*.csv（由 tools/prep_figs.py 生成）
输出：out/d2026c/fig2026c/fig*_{png,pdf}
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(HERE, "out", "data")
FIG = os.path.join(HERE, "out", "d2026c", "fig2026c")
os.makedirs(FIG, exist_ok=True)

INK = "#1f3b57"
MUTED = "#9aa7b3"
ACCENT = "#b4472e"

matplotlib.rcParams.update({
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
    "figure.dpi": 120,
    "savefig.dpi": 320,
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.labelsize": 10,
    "legend.fontsize": 9,
    "axes.spines.top": True,
    "axes.spines.right": True,
    "axes.edgecolor": "#333333",
    "axes.linewidth": 0.8,
    "axes.unicode_minus": False,
})


def save(fig, stem):
    for ext in ("png", "pdf"):
        p = os.path.join(FIG, "%s.%s" % (stem, ext))
        fig.savefig(p, format=ext, bbox_inches="tight")
    plt.close(fig)
    print("  wrote %s.{png,pdf}" % stem)


def fig1():
    """λ 可行范围：每周跨季的 5-95 分位 + 周中位数 + 总体中位数。"""
    df = pd.read_csv(os.path.join(D, "fig1_lambda.csv"))
    df = df[df["lam_mid"].notna()]
    g = df.groupby("week")["lam_mid"]
    weeks = sorted(df["week"].unique())
    lo = g.quantile(0.05).reindex(weeks).to_numpy(float)
    hi = g.quantile(0.95).reindex(weeks).to_numpy(float)
    mid = g.median().reindex(weeks).to_numpy(float)
    cnt = g.size().reindex(weeks).to_numpy(int)
    overall = float(df["lam_mid"].median())

    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    x = np.arange(len(weeks))
    ax.vlines(x, 0.0, 1.0, color=MUTED, linewidth=0.6, linestyles=":", zorder=1)
    ax.vlines(x, lo, hi, color=MUTED, linewidth=6.0, alpha=0.55, zorder=2)
    ax.plot(x, mid, "o", color=INK, markersize=5, zorder=3)
    ax.axhline(overall, color=ACCENT, linestyle="--", linewidth=1.0, zorder=4)
    ax.set_xticks(x)
    ax.set_xticklabels([str(w) for w in weeks])
    ax.set_xlabel("week of competition")
    ax.set_ylabel(r"$\lambda$  (share of fan vote explained by judges)")
    ax.set_ylim(-0.02, 1.02)
    ax.set_xlim(-0.6, len(weeks) - 0.4)
    ax.grid(axis="y", color="#e6e6e6", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.annotate("overall median %.3f" % overall,
                xy=(len(weeks) - 1, overall), xytext=(-6, 6),
                textcoords="offset points", ha="right", color=ACCENT, fontsize=9)
    ax.annotate("bars: 5th-95th percentile of %d season-weeks\n"
                "dots: weekly median; counts per week %d-%d"
                % (len(df), cnt.min(), cnt.max()),
                xy=(0.01, 0.02), xycoords="axes fraction",
                fontsize=8, color="#555555")
    save(fig, "fig1_lambda")


def fig2():
    """评委名次 vs 观众名次，对角线以上为观众更优。"""
    df = pd.read_csv(os.path.join(D, "fig2_upside.csv"))
    df = df.dropna(subset=["judge_rank", "fan_rank"])
    up = df["fan_rank"] < df["judge_rank"]
    rate = 100.0 * float(up.mean())

    fig, ax = plt.subplots(figsize=(4.6, 4.4))
    lim = (0, float(max(df["judge_rank"].max(), df["fan_rank"].max())) + 1)
    ax.plot(lim, lim, color="#444444", linewidth=0.9, linestyle="--", zorder=1)
    ax.scatter(df.loc[~up, "judge_rank"], df.loc[~up, "fan_rank"],
               s=8, color=MUTED, alpha=0.55, linewidths=0, zorder=2,
               label="audience not better")
    ax.scatter(df.loc[up, "judge_rank"], df.loc[up, "fan_rank"],
               s=8, color=ACCENT, alpha=0.65, linewidths=0, zorder=3,
               label="audience better (%.0f%%)" % rate)
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_xlabel("judge rank (1 = best)")
    ax.set_ylabel("audience rank (1 = best)")
    ax.set_aspect("equal")
    ticks = list(range(0, int(lim[1]) + 1, 2))
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.grid(color="#ededed", linewidth=0.6)
    ax.set_axisbelow(True)
    # 图例放到坐标区下方，否则会压住 (8,2)-(14,2) 一带的数据点
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=2,
              frameon=False, markerscale=2.0, handletextpad=0.4,
              columnspacing=1.4)
    ax.annotate("%d contestant-weeks" % len(df),
                xy=(0.03, 0.95), xycoords="axes fraction", fontsize=8,
                color="#555555")
    save(fig, "fig2_upside")


def fig3():
    """周级复现率随观众权重变化（等权是尖峰最优）。

    2026-11-10 换数据源：原图用 fig3_weight.csv（"冠军一致率"），而那一列
    来自整季模拟取 alive[0] 当冠军 —— 已证实该方法在「必须借用真实离场周」
    的约束下无法定义冠军（34 季仅对 1 季；修完后全空）。现改用
    c2026c_weight_curve.csv，它是周级口径：预测淘汰者 == 真实淘汰者的比例。
    """
    df = pd.read_csv(os.path.join(D, "c2026c_weight_curve.csv")).sort_values("w")
    fig, ax = plt.subplots(figsize=(6.0, 3.4))
    ax.plot(df["w"], df["rate"], "-o", color=INK, markersize=3.5,
            linewidth=1.3, zorder=3)
    peak = df.loc[df["rate"].idxmax()]
    # 用 hit/total 现算百分比再舍入：CSV 里的 rate 已 round 到 2 位，
    # 直接 "%.1f" % rate 会因浮点表示得到 95.8（真值 185/193 = 95.9）。
    peak_pct = round(100.0 * float(peak["hit"]) / float(peak["total"]), 1)
    ax.plot([peak["w"]], [peak_pct], "o", color=ACCENT, markersize=8,
            zorder=4, markerfacecolor="white", markeredgewidth=1.6)
    ax.axvline(0.5, color=ACCENT, linestyle="--", linewidth=0.9, zorder=1)
    ax.annotate("equal weight %.1f%%" % peak_pct,
                xy=(0.5, peak_pct), xytext=(10, -4),
                textcoords="offset points", color=ACCENT, fontsize=8)
    ax.set_xlabel("audience weight $w$ (judge weight $= 1-w$)")
    ax.set_ylabel("season-weeks reproduced (%)")
    ax.set_ylim(0, 105)
    ax.set_xlim(-0.02, 1.02)
    ax.grid(color="#ececec", linewidth=0.6)
    ax.set_axisbelow(True)
    for w in (0.45, 0.55):
        r = df[df["w"].round(2) == w].iloc[0]
        ax.annotate("%.1f%%" % r["rate"], xy=(w, r["rate"]),
                    xytext=(0, -13), textcoords="offset points",
                    ha="center", fontsize=8, color="#555555")
    save(fig, "fig3_weight")


def fig4():
    """两法对已观测淘汰的复现率。"""
    df = pd.read_csv(os.path.join(D, "fig4_two_methods.csv"))
    label = ["percentage rule\n$c_i=\\frac{1}{2}J_i+\\frac{1}{2}p_i$",
             "ranking rule\n$c_i=\\frac{1}{2}r^J_i+\\frac{1}{2}r^P_i$"]
    fig, ax = plt.subplots(figsize=(4.4, 3.4))
    x = np.arange(len(df))
    bars = ax.bar(x, df["feasible"], width=0.5,
                  color=[MUTED, INK], edgecolor="#333333", linewidth=0.6)
    for b, (_, r) in zip(bars, df.iterrows()):
        n = round(r["feasible"] / 100.0 * 231)
        ax.annotate("%.1f%%\n(%d/231)" % (r["feasible"], n),
                    xy=(b.get_x() + b.get_width() / 2, b.get_height()),
                    xytext=(0, 4), textcoords="offset points",
                    ha="center", fontsize=9, color="#222222")
    ax.set_xticks(x)
    ax.set_xticklabels(label, fontsize=8.5)
    ax.set_ylabel("eliminations reproduced (%)")
    ax.set_ylim(0, 112)
    ax.grid(axis="y", color="#ececec", linewidth=0.6)
    ax.set_axisbelow(True)
    save(fig, "fig4_feasible")


if __name__ == "__main__":
    print("redrawing figures ->", FIG)
    fig1()
    fig2()
    fig3()
    fig4()
    print("done")
