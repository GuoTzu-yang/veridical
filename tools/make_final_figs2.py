"""第二批图（fig11–fig20），全部从 data.json / data2.json 出。"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
OUT = os.path.join(HERE, "out", "final")
FIG = os.path.join(OUT, "fig")
D = json.load(open(os.path.join(OUT, "data.json"), encoding="utf-8"))
D2 = json.load(open(os.path.join(OUT, "data2.json"), encoding="utf-8"))

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


def fig11_matrix():
    M = D2["gate_matrix"]
    ids = D2["gate_ids"]
    probs = sorted(M)
    code = {"PASS": 0, "WARN": 1, "N/A": 2, "FAIL": 3}
    A = np.array([[code.get(M[p][c][1], 2) for c in ids] for p in probs])
    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    cmap = ListedColormap([GREEN, ORANGE, "#cbd5e0", RED])
    ax.imshow(A, aspect="auto", cmap=cmap, vmin=0, vmax=3)
    ax.set_xticks(range(len(ids)))
    ax.set_xticklabels(ids, rotation=90, fontsize=7.4)
    ax.set_yticks(range(len(probs)))
    ax.set_yticklabels(probs, fontsize=7.8)
    for i in range(len(probs)):
        for j in range(len(ids)):
            if A[i, j] == 2:
                ax.text(j, i, "·", ha="center", va="center", fontsize=6.5,
                        color="#4a5568")
    ax.set_title("Gate outcome for every check on every problem "
                 "(%d × %d)" % (len(probs), len(ids)), fontsize=10)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in
               (GREEN, ORANGE, "#cbd5e0", RED)]
    ax.legend(handles, ["pass", "warn", "not applicable", "fail"],
              fontsize=7.6, frameon=False, ncol=4, loc="upper center",
              bbox_to_anchor=(0.5, -0.28))
    save(fig, "fig11_matrix")


def fig12_passrate():
    M = D2["gate_matrix"]
    ids = D2["gate_ids"]
    rate = []
    for c in ids:
        st = [M[p][c][1] for p in M]
        n = len(st)
        na = sum(1 for s in st if s == "N/A")
        rate.append(100.0 * sum(1 for s in st if s == "PASS") / max(1, n - na))
    order = np.argsort(rate)
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    ax.bar(range(len(ids)), [rate[i] for i in order],
           color=[RED if rate[i] < 100 else GREEN for i in order], alpha=0.85)
    ax.set_xticks(range(len(ids)))
    ax.set_xticklabels([ids[i] for i in order], rotation=90, fontsize=7.4)
    ax.set_ylabel("pass rate over applicable problems (%)")
    ax.set_ylim(0, 106)
    ax.axhline(100, color=GREY, ls="--", lw=0.8)
    ax.set_title("Every check passes somewhere; the interesting part is where "
                 "they do not", fontsize=10)
    save(fig, "fig12_passrate")


def fig13_labelmatrix():
    TC = D["type_coverage"]
    labels = sorted({k for r in TC for k in r["curated"] + r["advise"]})
    probs = [r["name"] for r in TC]
    cur = np.zeros((len(probs), len(labels)))
    adv = np.zeros((len(probs), len(labels)))
    for i, r in enumerate(TC):
        for k in r["curated"]:
            cur[i, labels.index(k)] = 1
        for k in r["advise"]:
            adv[i, labels.index(k)] = 1
    fig, ax = plt.subplots(figsize=(6.6, 4.6))
    ax.imshow(cur - adv, aspect="auto", cmap="RdBu", vmin=-1, vmax=1)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=42, ha="right", fontsize=8)
    ax.set_yticks(range(len(probs)))
    ax.set_yticklabels(probs, fontsize=7.6)
    for i in range(len(probs)):
        for j in range(len(labels)):
            if cur[i, j] and not adv[i, j]:
                ax.text(j, i, "−", ha="center", va="center", fontsize=7,
                        color="#7f1d1d")
            elif adv[i, j] and not cur[i, j]:
                ax.text(j, i, "+", ha="center", va="center", fontsize=7,
                        color="#1e3a8a")
    ax.set_title("Curated label minus detected label "
                 "(red −: missed, blue +: over-reported)", fontsize=10)
    save(fig, "fig13_labelmatrix")


def fig14_abstract():
    A = D2["abstract_scores"]
    if not A:
        return
    names = list(A)
    vals = [A[n] for n in names]
    fig, ax = plt.subplots(figsize=(7.2, 2.9))
    order = np.argsort(vals)
    ax.bar(range(len(names)), [vals[i] for i in order],
           color=[GREEN if vals[i] >= 90 else ORANGE for i in order],
           alpha=0.85)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels([names[i] for i in order], rotation=70, ha="right",
                       fontsize=7)
    ax.set_ylabel("abstract score (/100)")
    ax.set_ylim(0, 108)
    ax.axhline(90, color=GREY, ls="--", lw=0.9)
    ax.set_title("Abstract quality across the corpus (median %.1f)"
                 % float(np.median(vals)), fontsize=10)
    save(fig, "fig14_abstract")


def fig15_runtime():
    R = D2["runtimes"]
    if not R:
        return
    fig, ax = plt.subplots(figsize=(5.6, 2.7))
    names = [x["cmd"] for x in R]
    vals = [x["seconds"] for x in R]
    bars = ax.barh(names, vals, color=BLUE, alpha=0.85, height=0.6)
    for b, v in zip(bars, vals):
        ax.text(v + 0.02, b.get_y() + b.get_height() / 2, "%.2fs" % v,
                va="center", fontsize=8)
    ax.set_xlabel("wall-clock seconds (one problem)")
    ax.set_xlim(0, max(vals) * 1.25)
    ax.set_title("Cheap enough to run on every draft", fontsize=10)
    save(fig, "fig15_runtime")


def fig16_sections():
    S = D2["sections"]
    if not S:
        return
    fig, ax = plt.subplots(figsize=(6.8, 3.0))
    names = [s["title"] for s in S]
    w = [s["words"] for s in S]
    ax.bar(range(len(names)), w, color=BLUE, alpha=0.85)
    for i, (ww, s) in enumerate(zip(w, S)):
        ax.text(i, ww + 8, "%d" % ww, ha="center", fontsize=7.6)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels([n[:26] for n in names], rotation=40, ha="right",
                       fontsize=7.6)
    ax.set_ylabel("words")
    ax.set_title("Where the words go (total %d)" % D2["paper_words"],
                 fontsize=10)
    save(fig, "fig16_sections")


def fig17_trace_pages():
    rows = [r for r in D["problems"]
            if r.get("pages") and r.get("gate_num_pct") is not None]
    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    xs = [r["pages"] for r in rows]
    ys = [r["gate_num_pct"] for r in rows]
    ax.scatter(xs, ys, s=30, color=BLUE, alpha=0.85, edgecolor="white")
    for r in rows:
        if r["gate_num_pct"] < 97:
            ax.annotate(r["name"], (r["pages"], r["gate_num_pct"]),
                        textcoords="offset points", xytext=(4, -9),
                        fontsize=6.6, color=RED)
    ax.set_xlabel("pages")
    ax.set_ylabel("numbers traced, gate scope (%)")
    ax.set_title("Longer papers are not less traceable", fontsize=10)
    save(fig, "fig17_trace_pages")


def fig18_orphans():
    rows = [r for r in D["problems"]
            if r.get("num_total") and r.get("num_ok") is not None]
    if not rows:
        return
    orph = [r["num_total"] - r["num_ok"] for r in rows]
    fig, ax = plt.subplots(figsize=(5.4, 2.8))
    ax.hist(orph, bins=max(5, len(set(orph))), color=ORANGE, alpha=0.85,
            edgecolor="white")
    ax.set_xlabel("untraced numeric tokens per paper (verify scope)")
    ax.set_ylabel("papers")
    ax.set_title("The residue is structural integers, not invented results "
                 "(median %.0f)" % float(np.median(orph)), fontsize=9.8)
    save(fig, "fig18_orphans")


def fig19_timeline():
    T = D["defect_taxonomy"]
    fig, ax = plt.subplots(figsize=(6.8, 2.8))
    keys = sorted(T, key=lambda k: min(T[k]["rounds"]) if T[k]["rounds"] else 0)
    for i, k in enumerate(keys):
        rr = T[k]["rounds"]
        ax.scatter(rr, [i] * len(rr), s=42, color=RED, alpha=0.75, zorder=3)
    ax.set_yticks(range(len(keys)))
    ax.set_yticklabels([k.replace("-", " ") for k in keys], fontsize=8.6)
    ax.set_xlabel("optimisation round")
    ax.grid(axis="x", color="#e2e8f0", lw=0.8)
    ax.set_axisbelow(True)
    ax.set_title("When each defect class was repaired", fontsize=10)
    save(fig, "fig19_timeline")


def fig20_inventory():
    pairs = [
        ("subcommands", D["n_commands"]),
        ("gate checks", D["n_gate_checks"]),
        ("regression pins", D["n_regression_pins"]),
        ("modules with selftest", D["n_modules_with_selftest"]),
        ("problems in corpus", len(D["problems"])),
        ("patches implemented", D["n_patches_done"]),
    ]
    fig, ax = plt.subplots(figsize=(5.8, 2.7))
    names = [p[0] for p in pairs]
    vals = [p[1] for p in pairs]
    ax.barh(names, vals, color=GREEN, alpha=0.85, height=0.62)
    for b, v in zip(ax.patches, vals):
        ax.text(v + 0.8, b.get_y() + b.get_height() / 2, str(v), va="center",
                fontsize=8.4)
    ax.set_xlabel("count")
    ax.set_xlim(0, max(vals) * 1.18)
    ax.set_title("The tool's size, as measured", fontsize=10)
    save(fig, "fig20_inventory")


if __name__ == "__main__":
    print("第二批图:")
    fig11_matrix()
    fig12_passrate()
    fig13_labelmatrix()
    fig14_abstract()
    fig15_runtime()
    fig16_sections()
    fig17_trace_pages()
    fig18_orphans()
    fig19_timeline()
    fig20_inventory()
    print("完成 ->", FIG)
