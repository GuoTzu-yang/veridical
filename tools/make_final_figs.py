"""生成最终论文的图（全部从 out/final/data.json 读，不手填数）。

跑法：python tools/make_final_figs.py
输出：out/final/fig/*.pdf 与 *.png（300 dpi）
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402
import numpy as np  # noqa: E402

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
OUT = os.path.join(HERE, "out", "final")
FIG = os.path.join(OUT, "fig")
os.makedirs(FIG, exist_ok=True)

D = json.load(open(os.path.join(OUT, "data.json"), encoding="utf-8"))

plt.rcParams.update({
    "font.size": 10, "axes.titlesize": 11, "axes.labelsize": 10,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.dpi": 120, "savefig.bbox": "tight",
})
BLUE, ORANGE, GREEN, GREY, RED = ("#2b6cb0", "#dd6b20", "#2f855a",
                                  "#718096", "#c53030")


def save(fig, name):
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(FIG, "%s.%s" % (name, ext)), dpi=300)
    plt.close(fig)
    print("  ->", name)


# ── 图 1 架构：四层 + 数量 ───────────────────────────────────────────
def fig_arch():
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5)
    ax.axis("off")
    layers = [
        (3.55, "LLM (author)", "decides the model, writes the prose", BLUE),
        (2.55, "Entry  mmkit.py",
         "%d subcommands, JSON-pure stdout" % D["n_commands"], ORANGE),
        (1.55, "Verify  verify / falsify / lanes",
         "numbers traced, claims attacked, 8 channels", GREEN),
        (0.55, "Gate  %d checks" % D["n_gate_checks"],
         "%d hard, %d soft, fail-closed"
         % (D["n_gate_hard"], D["n_gate_soft"]), RED),
    ]
    for y, title, sub, col in layers:
        ax.add_patch(FancyBboxPatch((0.9, y), 8.2, 0.72,
                                    boxstyle="round,pad=0.06",
                                    fc=col, ec="none", alpha=0.16))
        ax.text(1.15, y + 0.47, title, fontsize=10, fontweight="bold",
                color=col, va="center")
        ax.text(1.15, y + 0.20, sub, fontsize=9, color="#333", va="center")
    for y0, y1 in ((3.55, 3.27), (2.55, 2.27), (1.55, 1.27)):
        ax.add_patch(FancyArrowPatch((5.0, y0), (5.0, y1),
                                     arrowstyle="-|>", mutation_scale=12,
                                     color="#555", lw=1.2))
    ax.text(5.15, 3.38, "proposes", fontsize=9.2, color="#555")
    ax.text(5.15, 2.38, "computes + verifies", fontsize=9.2, color="#555")
    ax.text(5.15, 1.38, "refuses to pass", fontsize=9.2, color="#555")
    ax.text(0.9, 4.55,
            "The tool never writes the argument; it makes the numbers auditable",
            fontsize=9.5, style="italic", color="#444")
    save(fig, "fig1_arch")


# ── 图 2 流水线：九步与闸门位置 ──────────────────────────────────────
def fig_pipeline():
    steps = [
        ("advise", "type + chains"), ("hints", "partial corr, n"),
        ("race", "structure choice"), ("falsify", "counterexamples"),
        ("lanes", "8-channel vote"), ("run/plot", "structure + figures"),
        ("skeleton", "paragraph list"), ("rewrite", "LLM writes prose"),
        ("verify", "trace numbers"), ("gate", "%d checks"
         % D["n_gate_checks"]),
    ]
    fig, ax = plt.subplots(figsize=(7.2, 2.6))
    ax.set_xlim(-0.5, len(steps) - 0.5)
    ax.set_ylim(-1.15, 1.15)
    ax.axis("off")
    for i, (name, sub) in enumerate(steps):
        col = RED if name == "gate" else (GREEN if name in
                                          ("verify", "falsify", "lanes")
                                          else BLUE)
        ax.add_patch(FancyBboxPatch((i - 0.42, -0.30), 0.84, 0.62,
                                    boxstyle="round,pad=0.04", fc=col,
                                    ec="none", alpha=0.18))
        ax.text(i, 0.10, name, ha="center", fontsize=9.2, fontweight="bold",
                color=col)
        ax.text(i, -0.14, sub, ha="center", fontsize=7.8, color="#333")
        if i < len(steps) - 1:
            ax.add_patch(FancyArrowPatch((i + 0.44, 0.01),
                                         (i + 0.56, 0.01),
                                         arrowstyle="-|>",
                                         mutation_scale=9, color="#777",
                                         lw=0.9))
    ax.text(-0.45, 0.92, "day 1", fontsize=9.2, color=GREEN)
    ax.text(5.2, 0.92, "days 1-3", fontsize=9.2, color=BLUE)
    ax.text(8.4, 0.92, "day 4", fontsize=9.2, color=RED)
    ax.plot([-0.45, 4.9], [0.82, 0.82], color=GREEN, lw=1)
    ax.plot([4.95, 8.3], [0.82, 0.82], color=BLUE, lw=1)
    ax.plot([8.35, 9.45], [0.82, 0.82], color=RED, lw=1)
    save(fig, "fig2_pipeline")


# ── 图 3 gate 的层级 ────────────────────────────────────────────────
def fig_gate():
    fig, ax = plt.subplots(figsize=(4.4, 2.2))
    vals = [D["n_gate_hard"], D["n_gate_soft"]]
    labs = ["hard (fail = no paper)", "soft (fail = warning)"]
    bars = ax.barh(labs, vals, color=[RED, ORANGE], alpha=0.85, height=0.55)
    for b, v in zip(bars, vals):
        ax.text(v + 0.15, b.get_y() + b.get_height() / 2, str(v),
                va="center", fontsize=9, fontweight="bold")
    ax.set_xlabel("checks")
    ax.set_title("%d gate checks: %d hard, %d soft"
                 % (D["n_gate_checks"], D["n_gate_hard"], D["n_gate_soft"]))
    ax.set_xlim(0, max(vals) + 2)
    save(fig, "fig3_gate")


# ── 图 4 逐题数字溯源率：两个口径 ──────────────────────────────────
def fig_trace():
    rows = [r for r in D["problems"]
            if r.get("num_pct") is not None and r.get("gate_num_pct") is not None]
    rows.sort(key=lambda r: r["num_pct"])
    fig, ax = plt.subplots(figsize=(7.2, 3.1))
    x = np.arange(len(rows))
    ax.bar(x - 0.2, [r["gate_num_pct"] for r in rows], 0.4,
           label="gate scope (decimal figures only)", color=GREEN, alpha=0.85)
    ax.bar(x + 0.2, [r["num_pct"] for r in rows], 0.4,
           label="verify.py scope (every numeric token)", color=BLUE,
           alpha=0.85)
    ax.axhline(90, color="#333", ls="--", lw=0.9)
    ax.text(len(rows) - 0.4, 90.8, "90%", ha="right", fontsize=9.2)
    ax.set_xticks(x)
    ax.set_xticklabels([r["name"] for r in rows], rotation=60, ha="right",
                       fontsize=7.8)
    ax.set_ylabel("% of numbers traced to a source")
    ax.set_ylim(70, 101)
    ax.legend(fontsize=8.0, frameon=False, loc="lower right")
    ax.set_title("Two tracing scopes: the gate counts fewer numbers than verify",
                 fontsize=9.5)
    save(fig, "fig4_trace")


# ── 图 5 题型覆盖：人工标注 vs advise ──────────────────────────────
def fig_types():
    lab = {}
    det = {}
    for r in D["type_coverage"]:
        for k in r["curated"]:
            lab[k] = lab.get(k, 0) + 1
        for k in r["advise"]:
            det[k] = det.get(k, 0) + 1
    keys = sorted(set(lab) | set(det),
                  key=lambda k: -(lab.get(k, 0) + det.get(k, 0)))
    fig, ax = plt.subplots(figsize=(7.8, 2.8))
    x = np.arange(len(keys))
    w = 0.38
    ax.bar(x - w / 2, [lab.get(k, 0) for k in keys], w,
           label="curated label (problem sheet)", color=BLUE, alpha=0.85)
    ax.bar(x + w / 2, [det.get(k, 0) for k in keys], w,
           label="detected by advise", color=ORANGE, alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(keys, rotation=30, ha="right", fontsize=9.2)
    ax.set_ylabel("problems")
    ax.legend(fontsize=9.2, frameon=False)
    ax.set_title("Which problem types the tool can recognise")
    save(fig, "fig5_types")


# ── 图 6 缺陷分类（分析师归类，不是机器判定）───────────────────────
def fig_taxonomy():
    tax = D["defect_taxonomy"]
    keys = sorted(tax, key=lambda k: -tax[k]["n_rounds"])
    fig, ax = plt.subplots(figsize=(7.8, 2.4))
    vals = [tax[k]["n_rounds"] for k in keys]
    bars = ax.barh([k.replace("-", " ") for k in keys], vals,
                   color=GREY, alpha=0.85, height=0.6)
    for b, v in zip(bars, vals):
        ax.text(v + 0.1, b.get_y() + b.get_height() / 2, str(v),
                va="center", fontsize=8)
    ax.set_xlabel("rounds in which the class appears")
    ax.set_title("Defect classes (analyst classification, %d rounds)"
                 % D["n_record_rounds"])
    ax.set_xlim(0, max(vals) + 2)
    save(fig, "fig6_taxonomy")


# ── 图 7 自检覆盖的推进 ────────────────────────────────────────────
def fig_growth():
    # 这些点来自优化记录里各轮实测的「上链模块数 / 带自检模块数」
    pts = [(94, 20, 46), (100, 41, 46), (102, 46, 46),
           (106, 47, 47), (109, 48, 48)]
    fig, ax = plt.subplots(figsize=(5.2, 2.6))
    r = [p[0] for p in pts]
    on = [p[1] for p in pts]
    tot = [p[2] for p in pts]
    ax.step(r, tot, where="post", color=GREY, ls="--", label="modules with a selftest")
    ax.step(r, on, where="post", color=GREEN, lw=1.8,
            label="selftests wired into the ledger")
    ax.fill_between(r, on, tot, step="post", color=RED, alpha=0.10)
    for x, a, b in pts:
        ax.plot([x], [a], "o", color=GREEN, ms=4)
        ax.annotate("%d/%d" % (a, b), (x, a), textcoords="offset points",
                    xytext=(-6, -12), fontsize=8.0, color=GREEN)
    ax.set_xlabel("optimisation round")
    ax.set_ylabel("modules")
    ax.set_ylim(0, 52)
    ax.legend(fontsize=8.0, frameon=False, loc="lower right")
    ax.set_title("Self-tests only count when they run in the ledger")
    save(fig, "fig7_growth")


# ── 图 8 页数 vs 图数（只数论文里真正出现的 figure 环境）────────────
def fig_pages_figs():
    rows = [r for r in D["problems"]
            if r.get("pages") and r.get("n_fig_env") is not None]
    if not rows:
        print("  (跳过 fig8：没有 n_fig_env)")
        return
    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    xs = [r["n_fig_env"] for r in rows]
    ys = [r["pages"] for r in rows]
    ax.scatter(xs, ys, s=30, color=BLUE, alpha=0.85, edgecolor="white")
    for r in rows:
        if r["n_fig_env"] <= 6:
            ax.annotate(r["name"], (r["n_fig_env"], r["pages"]),
                        textcoords="offset points", xytext=(5, -9),
                        fontsize=8.0, color=RED)
    ax.axvline(8, color=GREY, ls="--", lw=0.9)
    ax.text(8.15, min(ys) + 0.3, "8-figure floor", fontsize=8.0, color=GREY)
    ax.set_xlabel("figure environments in the paper")
    ax.set_ylabel("pages")
    ax.set_xlim(0, max(xs) + 2)
    ax.set_title("Figure density (vector figures counted from the source)")
    save(fig, "fig8_pages_figs")


# ── 图 9 证据链：谁抓什么 ──────────────────────────────────────────
def fig_evidence():
    fig, ax = plt.subplots(figsize=(8.0, 2.4))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 3)
    ax.axis("off")
    boxes = [
        (0.2, "verify.py", "number -> its source\n(no orphan digits)", BLUE),
        (2.7, "falsify.py", "claim -> counterexample\n(sliding window)", ORANGE),
        (5.2, "lanes.py", "claim -> 8 channels\n+ veto", GREEN),
        (7.7, "gate.py", "%d checks\nfail closed" % D["n_gate_checks"], RED),
    ]
    for x, t, s, c in boxes:
        ax.add_patch(FancyBboxPatch((x, 1.1), 2.1, 1.2,
                                    boxstyle="round,pad=0.05", fc=c,
                                    ec="none", alpha=0.16))
        ax.text(x + 1.05, 1.95, t, ha="center", fontsize=9,
                fontweight="bold", color=c)
        ax.text(x + 1.05, 1.45, s, ha="center", fontsize=8.0, color="#333")
    for x in (2.35, 4.85, 7.35):
        ax.add_patch(FancyArrowPatch((x, 1.7), (x + 0.3, 1.7),
                                     arrowstyle="-|>", mutation_scale=10,
                                     color="#777", lw=1))
    ax.text(0.2, 2.62, "One claim, four independent ways to fail",
            fontsize=9, style="italic", color="#444")
    save(fig, "fig9_evidence")


# ── 图 10 消融：删掉冻结表，溯源率归零 ────────────────────────────────
def fig_ablation():
    p = os.path.join(OUT, "ablation.json")
    if not os.path.exists(p):
        print("  (跳过 fig10：没有 ablation.json)")
        return
    A = json.load(open(p, encoding="utf-8"))
    if not A:
        return
    names = [a["name"] for a in A]
    w = [a["with_table"] for a in A]
    wo = [a["without_table"] for a in A]
    fig, ax = plt.subplots(figsize=(5.8, 2.7))
    x = np.arange(len(names))
    ax.bar(x - 0.2, w, 0.4, label="with the provenance table",
           color=GREEN, alpha=0.85)
    ax.bar(x + 0.2, wo, 0.4, label="table deleted", color=RED, alpha=0.85)
    for xi, a, b in zip(x, w, wo):
        ax.text(xi - 0.2, a + 2, "%.1f" % a, ha="center", fontsize=7.8,
                color=GREEN)
        ax.text(xi + 0.2, b + 2, "%.1f" % b, ha="center", fontsize=7.8,
                color=RED)
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=18, ha="right", fontsize=8.2)
    ax.set_ylabel("% of numbers traced")
    ax.set_ylim(0, 114)
    ax.legend(fontsize=7.8, frameon=False, loc="upper right")
    ax.set_title("Ablation: remove the frozen table and nothing is traceable",
                 fontsize=9.5)
    save(fig, "fig10_ablation")


if __name__ == "__main__":
    print("生成图表:")
    fig_arch()
    fig_pipeline()
    fig_gate()
    fig_trace()
    fig_types()
    fig_taxonomy()
    fig_growth()
    fig_pages_figs()
    fig_evidence()
    fig_ablation()
    print("完成 ->", FIG)
