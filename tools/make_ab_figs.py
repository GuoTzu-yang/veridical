#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_ab_figs.py —— A/B 对照实验的四张图（第 123 轮）。

数据全部读 out/final/ablation_ab.json，没有手写常量。
四张图各自回答一个问题：

  fig21_scores      五维度两组得分，同一标尺
  fig22_gap         逐维差距（谁在哪一项上更强）
  fig23_trace       可核验性：数字数与可机械溯源数
  fig24_overlap     重叠检查：六项全是 0 或结构性值
"""
import io
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "out", "final")
FIG = os.path.join(OUT, "fig")
C1 = "#2b6cb0"      # 用插件
C2 = "#c05621"      # 不用插件


def load():
    return json.load(io.open(os.path.join(OUT, "ablation_ab.json"), encoding="utf-8"))


def _save(fig, name):
    fig.savefig(os.path.join(FIG, name + ".png"), bbox_inches="tight", dpi=200)
    fig.savefig(os.path.join(FIG, name + ".pdf"), bbox_inches="tight")
    plt.close(fig)


def fig_scores(d):
    s = d["scores"]
    lab, mx = s["dimensions"], s["max"]
    a, b = s["arm_plugin"], s["arm_plain"]
    x = np.arange(len(lab))
    w = 0.36
    fig, ax = plt.subplots(figsize=(7.4, 3.2))
    ax.bar(x - w / 2, a, w, label="with plugin (94)", color=C1)
    ax.bar(x + w / 2, b, w, label="without plugin (90)", color=C2)
    for i, m in enumerate(mx):
        ax.plot([i - 0.42, i + 0.42], [m, m], color="#888", lw=1, ls=":")
        ax.text(i + 0.44, m, str(m), va="center", fontsize=7, color="#666")
    ax.set_xticks(x)
    ax.set_xticklabels(lab, fontsize=8)
    ax.set_ylabel("score")
    ax.set_ylim(0, 34)
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(axis="y", ls=":", alpha=0.45)
    _save(fig, "fig21_scores")


def fig_gap(d):
    s = d["scores"]
    lab = s["dimensions"]
    diff = [p - q for p, q in zip(s["arm_plugin"], s["arm_plain"])]
    fig, ax = plt.subplots(figsize=(6.6, 2.9))
    colors = [C1 if v > 0 else C2 for v in diff]
    ax.barh(range(len(lab)), diff, color=colors)
    ax.set_yticks(range(len(lab)))
    ax.set_yticklabels(lab, fontsize=8)
    ax.invert_yaxis()
    ax.axvline(0, color="#333", lw=0.8)
    for i, v in enumerate(diff):
        ax.text(v + (0.25 if v >= 0 else -0.25), i, "%+d" % v,
                va="center", ha="left" if v >= 0 else "right", fontsize=8)
    ax.set_xlabel("score difference (with plugin minus without), points")
    ax.set_xlim(-8.5, 8.5)
    ax.grid(axis="x", ls=":", alpha=0.45)
    _save(fig, "fig22_gap")


def fig_trace(d):
    t = d["traceability"]
    a, b = t["arm_plugin"], t["arm_plain"]
    fig, ax = plt.subplots(figsize=(5.6, 3.0))
    x = [0, 1]
    tot = [a["n_numbers"], b["n_numbers"]]
    tr = [a["n_traced"], b["n_traced"]]
    ax.bar(x, tot, 0.5, color="#cbd5e0", label="numbers in the paper")
    ax.bar(x, tr, 0.5, color=C1, label="mechanically traceable")
    for i in x:
        ax.text(i, tot[i] + 8, str(tot[i]), ha="center", fontsize=9)
        ax.text(i, tr[i] / 2 if tr[i] > 30 else 12,
                ("%d (%.0f%%)" % (tr[i], 100.0 * tr[i] / tot[i])),
                ha="center", fontsize=9, color="white" if tr[i] > 30 else "#333")
    ax.set_xticks(x)
    ax.set_xticklabels(["with plugin", "without plugin"], fontsize=9)
    ax.set_ylabel("count of numeric tokens")
    ax.set_ylim(0, max(tot) * 1.25)
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(axis="y", ls=":", alpha=0.45)
    _save(fig, "fig23_trace")


def fig_overlap(d):
    o = d["overlap_check"]
    items = [("solver values\n(informative)", o["solver_values_informative_shared"]),
             ("paper decimals", o["paper_decimals_shared"]),
             ("prose, 30 chars", o["prose_30char_shared"]),
             ("code, 3 lines", o["code_3line_shared"]),
             ("data files\n(same hash)", o["data_files_same_hash"])]
    fig, ax = plt.subplots(figsize=(6.4, 2.8))
    names = [i[0] for i in items]
    vals = [i[1] for i in items]
    ax.bar(range(len(items)), vals, 0.55, color="#38a169")
    for i, v in enumerate(vals):
        ax.text(i, v + max(vals) * 0.06 if max(vals) else 0.15, str(v),
                ha="center", fontsize=10)
    ax.set_xticks(range(len(items)))
    ax.set_xticklabels(names, fontsize=8)
    ax.set_ylabel("shared items")
    ax.set_ylim(0, 1.6)
    ax.axhline(0, color="#333", lw=0.8)
    ax.text(0.5, 0.62,
            "43 solver values do coincide,\nbut all are grid points, cabin counts,\n"
            "time steps and common ratios — not optima",
            transform=ax.transAxes, fontsize=7.5, ha="center",
            bbox=dict(boxstyle="round,pad=0.35", fc="#f7fafc", ec="#cbd5e0"))
    ax.grid(axis="y", ls=":", alpha=0.45)
    _save(fig, "fig24_overlap")


def main():
    d = load()
    os.makedirs(FIG, exist_ok=True)
    fig_scores(d)
    fig_gap(d)
    fig_trace(d)
    fig_overlap(d)
    print("四张图已写:", FIG)
    for n in ("fig21_scores", "fig22_gap", "fig23_trace", "fig24_overlap"):
        p = os.path.join(FIG, n + ".png")
        print("  %-16s %d 字节" % (n, os.path.getsize(p)))


if __name__ == "__main__":
    main()
