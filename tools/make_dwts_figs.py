#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_dwts_figs.py —— 给竞赛稿补两张图（第 123 轮）。

为什么补：`out/d2026c` 只有 4 张图，低于交付下限 6 张。gate 报
「只有 4 张图，低于交付下限 6 张（均分 8.0/10，质量不是问题，数量是）」。

两张图的数据**全部读自已算好的工件**，没有手写常量：
  · model_stats.json  → cv_rmse_{lin,quad,ridge1,ridge10} 与其 sd
  · evidence.json     → lam_width_pct / lam_width_rank / lam_mid_pct / lam_mid_rank

图 1：四个规格的交叉验证 RMSE，带一个标准差的误差棒。
      存在的意义：正文说「四个不可区分」，这张图让读者一眼看到四个区间互相重叠。
图 2：两种组合规则下，可行集区间宽度与中位位置的对比。
      存在的意义：正文说「排名规则的不确定性更大」，这张图给出量。
"""
import io
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "out", "d2026c")
FIG = os.path.join(OUT, "fig2026c")


def load(name):
    return json.load(io.open(os.path.join(OUT, name), encoding="utf-8"))


def _save(fig, path):
    """存 png（figcheck 只审 png，其余四张图也都是 png）+ pdf（矢量备份）。"""
    fig.savefig(path, bbox_inches="tight", dpi=200)
    fig.savefig(path[:-4] + ".pdf", bbox_inches="tight")


def fig_cvrmse(ms, path):
    """四个规格的 CV RMSE + 误差棒。"""
    specs = [("linear", "cv_rmse_lin", "cv_rmse_lin_sd"),
             ("quadratic", "cv_rmse_quad", "cv_rmse_quad_sd"),
             ("ridge, $\\lambda=1$", "cv_rmse_ridge1", "cv_rmse_ridge1_sd"),
             ("ridge, $\\lambda=10$", "cv_rmse_ridge10", "cv_rmse_ridge10_sd")]
    labels = [s[0] for s in specs]
    vals = [ms[s[1]] for s in specs]
    errs = [ms[s[2]] for s in specs]

    fig, ax = plt.subplots(figsize=(6.2, 2.9))
    y = range(len(labels))
    ax.errorbar(vals, list(y), xerr=errs, fmt="o", capsize=4,
                color="#1f4e79", ecolor="#1f4e79", markersize=6)
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    # 横轴从 1.295 起：四个值挤在 1.303 附近，从 0 起就什么都看不出
    ax.set_xlim(1.295, 1.320)
    ax.set_xlabel("Cross-validated RMSE (ranks), error bar = one standard deviation")
    ax.set_title("Four specifications are indistinguishable", fontsize=10)
    ax.grid(axis="x", linestyle=":", alpha=0.5)
    # 把重叠的区间画成一条带，让「都压在一起」变成可见的事实
    lo = min(v - e for v, e in zip(vals, errs))
    hi = max(v + e for v, e in zip(vals, errs))
    ax.axvspan(lo, hi, color="#d62728", alpha=0.08,
               label="span of all four intervals")
    ax.legend(fontsize=7, loc="lower right")
    fig.tight_layout()
    _save(fig, path)
    plt.close(fig)
    return vals, errs


def fig_width(ev, path):
    """两种规则的区间宽度与中位位置。"""
    groups = [("percentage", ev["lam_width_pct"], ev["lam_mid_pct"]),
              ("ranking", ev["lam_width_rank"], ev["lam_mid_rank"])]
    fig, ax = plt.subplots(figsize=(5.4, 2.9))
    x = range(len(groups))
    w = [g[1] for g in groups]
    m = [g[2] for g in groups]
    ax.bar([i - 0.18 for i in x], w, width=0.34, label="mean width",
           color="#4c72b0")
    ax.bar([i + 0.18 for i in x], m, width=0.34, label="midpoint",
           color="#dd8452")
    ax.set_xticks(list(x))
    ax.set_xticklabels([g[0] + " rule" for g in groups])
    ax.set_ylim(0, 0.65)
    ax.set_ylabel("share of the achievable range")
    ax.set_title("What the elimination leaves unidentified", fontsize=10)
    for i, (ww, mm) in enumerate(zip(w, m)):
        ax.text(i - 0.18, ww + 0.012, "%.3f" % ww, ha="center", fontsize=8)
        ax.text(i + 0.18, mm + 0.012, "%.3f" % mm, ha="center", fontsize=8)
    ax.legend(fontsize=8)
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    fig.tight_layout()
    _save(fig, path)
    plt.close(fig)
    return w, m


def main():
    os.makedirs(FIG, exist_ok=True)
    ms, ev = load("model_stats.json"), load("evidence.json")
    p1 = os.path.join(FIG, "fig5_cvrmse.png")
    p2 = os.path.join(FIG, "fig6_width.png")
    v, e = fig_cvrmse(ms, p1)
    w, m = fig_width(ev, p2)
    print("fig5_cvrmse.png  %s  ± %s" % (v, e))
    print("fig6_width.png   width=%s  mid=%s" % (w, m))
    print("完成 -> %s" % FIG)


if __name__ == "__main__":
    main()
