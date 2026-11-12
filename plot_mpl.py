#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plot_mpl.py —— matplotlib 绘图后端（第 9 轮）

为什么要换掉 PIL
----------------
用户两次指出图的问题：
    ① `normal($\\mu$=0.7467, $\\sigma$=0.01127)` —— LaTeX 标记直接显示出来
    ② 图例文字被截断（thermal resict / mathfold / depo...）

根因是手写 PIL：**它不会渲染数学符号，也不会自适应文本长度**。
matplotlib 两件都解决，而且能直接吐 PDF 矢量。

字体嵌入（关键）
----------------
    pdf.fonttype = 42   → TrueType 嵌入，而不是转成 Type3 轮廓
    svg.fonttype = none → SVG 保留 <text>，后期可编辑

不设这两项，图在 LaTeX 里编译后文字会变成模糊轮廓或错位
（评测里常见的"图糊了"就是这个原因）。

用法
    python plot_mpl.py selftest
    python plot_mpl.py --kind corr --data X.xlsx --cols a,b,c --out fig/corr
"""

from __future__ import annotations

import os
import sys

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

# ── 字体与输出设置（写在最前，任何图都适用）──
matplotlib.rcParams.update({
    "pdf.fonttype": 42,          # TrueType 嵌入，不转轮廓
    "ps.fonttype": 42,
    "svg.fonttype": "none",      # SVG 保留文字
    "figure.dpi": 110,
    "savefig.dpi": 300,          # 位图 300 dpi
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.labelsize": 10,
    "legend.fontsize": 9,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.autolayout": False,
})

# ── 期刊级主题（scienceplots）──
# 反馈：图（帕累托、敏感性）像 Jupyter 默认输出，缺顶刊质感。
# science+ieee 是期刊排版组合：细轴线、紧留白、Times 系字体、
# 低饱和配色。没装就退回上面的设置，不让缺依赖直接崩。
try:
    import scienceplots as _sp          # noqa: F401
    # 必须带 no-latex：science 样式默认 text.usetex=True，本机
    # 处理不了中文和部分符号，实测会让每张图回退到手写 PIL，
    # 比原来的 matplotlib 还差。no-latex 只取配色/线宽/留白。
    matplotlib.style.use(["science", "ieee", "no-latex"])
    matplotlib.rcParams.update({
        "text.usetex": False,
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
        "figure.dpi": 160,
        "savefig.dpi": 320,
        "axes.linewidth": 0.7,
        "grid.linewidth": 0.4,
        "grid.alpha": 0.35,
        "legend.frameon": False,
        "lines.linewidth": 1.1,
    })
    _THEME = "science+ieee+no-latex"
except Exception:                        # noqa: BLE001
    _THEME = "fallback"

# 中文字体回退（图里万一有中文也不至于变方块）
_CJK = None
for cand in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC",
             "Source Han Sans SC", "FangSong"):
    try:
        font_manager.findfont(cand, fallback_to_default=False)
        _CJK = cand
        break
    except Exception:                               # noqa: BLE001
        continue
if _CJK:
    matplotlib.rcParams["font.sans-serif"] = [_CJK, "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False

ACCENT = "#d62728"
BASE = "#4c72b0"


def _save(fig, out: str) -> dict:
    """同时存 PDF（矢量，进 LaTeX 用）和 PNG（预览用）。"""
    d = os.path.dirname(os.path.abspath(out))
    if d:
        os.makedirs(d, exist_ok=True)
    paths = {}
    fig.tight_layout()
    for ext in ("pdf", "png"):
        p = f"{out}.{ext}"
        fig.savefig(p, format=ext, bbox_inches="tight")
        paths[ext] = dict(path=p, bytes=os.path.getsize(p))
    plt.close(fig)
    return paths


# ══════════════════════════════════════════════════════════════════════
#  各图类型
# ══════════════════════════════════════════════════════════════════════
def plot_corr(M, names, out="corr", title=None):
    """相关性热力图。数值直接标在格子里，不靠颜色猜。"""
    n = len(names)
    fig, ax = plt.subplots(figsize=(max(4.2, 0.55 * n + 2.2),
                                    max(3.6, 0.55 * n + 1.8)))
    im = ax.imshow(M, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(names, rotation=38, ha="right")
    ax.set_yticklabels(names)
    for i in range(n):
        for j in range(n):
            v = float(M[i, j])
            # 小数位自适应：真 0 显示 0.00，「接近 0」必须露出真值。
            # 实测踩到：正交设计的因子相关是 0.004 这个量级，
            # 两位小数全显示 0.00 —— 读者看不出「近似正交」和
            # 「恰好为 0」的区别，而这正是设计质量的证据。
            # 三档：浮点噪声 / 小于 0.01 / 正常
            # 实测：正交设计算出来的相关是 -1.55e-18，不是精确 0。
            # 按 v==0 判断会漏掉它，按 <0.01 又显示成 -0.000 —— 两种都错。
            if abs(v) < 1e-10:
                _t = "0.00"          # 浮点噪声，就是 0
            elif abs(v) < 0.005:
                _t = f"{v:+.3f}"     # 真的小但不为零，露出来
            else:
                _t = f"{v:.2f}"
                if _t == "-0.00":
                    _t = "0.00"
            ax.text(j, i, _t, ha="center", va="center",
                    fontsize=8, color="white" if abs(v) > 0.55 else "black")
    ax.set_title(title or "Pairwise correlation")
    ax.grid(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    cb.set_label("Pearson r")
    return _save(fig, out)


def plot_box(series, labels, out="box", ylabel="value", title=None):
    """箱线图。抖动点画在最上层，样本少时能看出真实分布。

    跨量纲自动归一化：这批变量跨度从 0.3 到 84，共用一个 y 轴时
    除最大的那个之外全被压成一条线，图就没有信息量了（实测过）。
    归一化后看的是分布形状 —— 偏斜、离群、稀疏区，这才是箱线图
    在那一步该回答的问题。
    """
    spans = []
    for s in series:
        arr = np.asarray(s, dtype=float)
        if arr.size:
            spans.append(float(arr.max() - arr.min()))
    _scaled = bool(spans) and (max(spans) > 20 * max(1e-12, min(spans)))
    if _scaled:
        series = [(np.asarray(s, dtype=float) - np.nanmin(s))
                  / max(1e-12, np.nanmax(s) - np.nanmin(s))
                  for s in series]
        ylabel = "each variable scaled to [0, 1]"
    fig, ax = plt.subplots(figsize=(max(4.4, 0.8 * len(series) + 2.0), 3.8))
    bp = ax.boxplot(series, tick_labels=labels, patch_artist=True,
                    widths=0.55, showfliers=True,
                    medianprops=dict(color="black", lw=1.4))
    for b in bp["boxes"]:
        b.set(facecolor="#a8c4e0", alpha=0.75, edgecolor="#33506e", lw=1.0)
    for i, s in enumerate(series, start=1):
        arr = np.asarray(s, dtype=float)
        if arr.size and arr.size <= 60:
            jit = np.random.default_rng(7).normal(0, 0.045, arr.size)
            ax.plot(np.full(arr.size, i) + jit, arr, ".", ms=3.2,
                    color="#2b2b2b", alpha=0.55, zorder=3)
    ax.set_ylabel(ylabel)
    ax.set_title(title or "Distribution by group")
    ax.set_xticks(range(1, len(labels) + 1))
    # 实测教训：三个长标签（"manifold / depth-to-height ratio" 这种）
    # 只旋转 18° 会糊成一团，PDF 里读成
    # "pin-fin / widthmanifold / depth-to-height ratioflow direction"。
    # 45° 加斜杠处折行，两个一起才够。
    _lab = [str(x).replace(" / ", " /\n") if len(str(x)) > 14 else str(x)
            for x in labels]
    ax.set_xticklabels(_lab, rotation=45, ha="right")
    return _save(fig, out)


def plot_hist(x, out="hist", xlabel="value", title=None, bins=None):
    """直方图 + 核密度轮廓。"""
    arr = np.asarray(x, dtype=float)
    arr = arr[~np.isnan(arr)]
    fig, ax = plt.subplots(figsize=(5.2, 3.6))
    if bins is None:
        bins = max(8, min(30, int(np.sqrt(max(arr.size, 1)) * 2)))
    ax.hist(arr, bins=bins, color=BASE, alpha=0.72,
            edgecolor="white", linewidth=0.6, density=True)
    # 简单的正态参照曲线（不做 KDE，避免额外依赖）
    if arr.size > 3 and arr.std() > 0:
        xs = np.linspace(arr.min(), arr.max(), 200)
        pdf = (np.exp(-0.5 * ((xs - arr.mean()) / arr.std()) ** 2)
               / (arr.std() * np.sqrt(2 * np.pi)))
        ax.plot(xs, pdf, "--", color=ACCENT, lw=1.3,
                label=rf"normal($\mu$={arr.mean():.4g}, "
                      rf"$\sigma$={arr.std():.4g})")
        ax.legend()
    ax.set_xlabel(xlabel)
    ax.set_ylabel("density")
    ax.set_title(title or "Empirical distribution")
    return _save(fig, out)


def plot_pred(y_true, y_pred, out="pred", title=None):
    """预测 vs 实际，带 45 度参考线。"""
    t = np.asarray(y_true, dtype=float)
    p = np.asarray(y_pred, dtype=float)
    ok = ~(np.isnan(t) | np.isnan(p))
    t, p = t[ok], p[ok]
    fig, ax = plt.subplots(figsize=(4.8, 4.4))
    ax.plot(t, p, "o", ms=4.5, color=BASE, alpha=0.75, label="observations")
    lo, hi = float(min(t.min(), p.min())), float(max(t.max(), p.max()))
    pad = (hi - lo) * 0.05 or 0.01
    ax.plot([lo - pad, hi + pad], [lo - pad, hi + pad], "--",
            color=ACCENT, lw=1.2, label=r"$y=\hat{y}$")
    rmse = float(np.sqrt(np.mean((t - p) ** 2)))
    ax.set_xlabel("observed")
    ax.set_ylabel("fitted")
    ax.set_title(title or "Fitted against observed")
    ax.text(0.04, 0.94, rf"RMSE $=$ {rmse:.4g}   $n={t.size}$",
            transform=ax.transAxes, va="top", fontsize=9,
            bbox=dict(fc="white", ec="0.8", alpha=0.9, pad=3))
    ax.legend(loc="lower right")
    ax.set_aspect("equal", adjustable="box")
    return _save(fig, out)


def plot_sens(curves, factors, out="sens", xlabel="relative parameter change",
              ylabel="objective value", title=None):
    """敏感性：每个因子一条线。图例放图外，避免遮挡曲线。"""
    fig, ax = plt.subplots(figsize=(6.0, 3.9))
    for c, f in zip(curves, factors):
        ax.plot(c["x"], c["y"], "o-", ms=4, lw=1.4, label=f)
    ax.axvline(0, color="0.6", lw=0.8, ls=":")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title or "Sensitivity to parameter perturbation")
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5),
              frameon=False)
    return _save(fig, out)


def plot_pareto(M, front_idx, labels, out="pareto",
                minimize=(True, True), title=None):
    """帕累托前沿：被支配点灰、前沿点红。"""
    Mo = np.asarray(M, dtype=float).copy()
    for k, mn in enumerate(minimize):
        if not mn:
            Mo[:, k] = -Mo[:, k]
    fmask = np.zeros(len(Mo), dtype=bool)
    fmask[list(front_idx)] = True
    fig, ax = plt.subplots(figsize=(5.6, 4.4))
    ax.scatter(Mo[~fmask, 0], Mo[~fmask, 1], s=18, c="#bdc3c7",
               edgecolors="none", label="dominated")
    ax.scatter(Mo[fmask, 0], Mo[fmask, 1], s=42, c=ACCENT,
               edgecolors="black", linewidths=0.4,
               label=f"front of these two ({int(fmask.sum())} points)")
    ax.set_xlabel(labels[0])
    ax.set_ylabel(labels[1])
    # 标题必须点明是二维投影：正文的三目标前沿是 12 点，
    # 这张图只画其中两维，前沿是 9 点。不写清楚会被读成前后矛盾。
    ax.set_title(title or "Pareto front (two-objective projection)")
    ax.legend(loc="best")
    return _save(fig, out)


def plot_resid(fitted, resid, out="resid", title=None):
    """残差 vs 拟合值。水平带 = 0 附近的参考。"""
    f = np.asarray(fitted, dtype=float)
    r = np.asarray(resid, dtype=float)
    ok = ~(np.isnan(f) | np.isnan(r))
    f, r = f[ok], r[ok]
    fig, ax = plt.subplots(figsize=(5.2, 3.6))
    ax.plot(f, r, "o", ms=4, color=BASE, alpha=0.7)
    ax.axhline(0, color=ACCENT, lw=1.1)
    s = float(r.std()) if r.size else 0.0
    if s > 0:
        for k, style in ((1, ":"), (2, "--")):
            ax.axhline(k * s, color="0.55", lw=0.8, ls=style)
            ax.axhline(-k * s, color="0.55", lw=0.8, ls=style)
    ax.set_xlabel("fitted value")
    ax.set_ylabel("residual")
    ax.set_title(title or r"Residuals ($\pm1\sigma$, $\pm2\sigma$ bands)")
    return _save(fig, out)


def plot_flow(steps, out="flow", title=None, sub=None):
    """技术路线图：竖排方框 + 箭头。

    为什么用 matplotlib 画流程图：PIL 版是 72dpi 位图，进 LaTeX 会糊，
    而且没有 PDF。这里用 FancyBboxPatch 出矢量，字号和留白都可控。
    """
    from matplotlib.patches import FancyBboxPatch

    n = len(steps)
    h = max(4.0, 0.62 * n + 1.2)
    fig, ax = plt.subplots(figsize=(4.4, h))
    gap = 1.0 / n
    for i, s in enumerate(steps):
        y = 1 - (i + 0.5) * gap
        box = FancyBboxPatch(
            (0.10, y - gap * 0.30), 0.80, gap * 0.60,
            boxstyle="round,pad=0.012,rounding_size=0.02",
            linewidth=1.2, edgecolor="#33506e",
            facecolor="#dce8f5" if i % 2 == 0 else "#f2f6fb")
        ax.add_patch(box)
        ax.text(0.5, y, s, ha="center", va="center", fontsize=10)
        if i < n - 1:
            ax.annotate(
                "", xy=(0.5, y - gap * 0.72), xytext=(0.5, y - gap * 0.32),
                arrowprops=dict(arrowstyle="-|>", lw=1.3, color="#33506e"))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.axis("off")
    if title:
        ax.set_title(title, fontsize=11)
    if sub:
        ax.text(0.5, 0.005, sub, ha="center", va="bottom",
                fontsize=8, color="0.35")
    return _save(fig, out)


def plot_tornado(items, base, out="tornado", delta=0.3,
                 xlabel="change in the response", title=None):
    """龙卷风图：各因子在 ±delta 内变动对输出的影响，按幅度排序。

    为什么用条而不是表：读者一眼就能看出哪个因子最敏感，
    以及第一和第二敏感之间差多少倍。表要逐行比较才能得到这个结论。

    items 来自 mm.sens：每项有 name / d_mean / rel。
    线性拟合下 ±delta 的变化关于基线对称，所以一条横条覆盖两侧。
    """
    if not items:
        return None
    rows = sorted(items, key=lambda d: -abs(float(d.get("d_mean") or 0.0)))
    # 名字由调用方转好英文再传进来 —— plot_mpl 里没有 _en 这个函数
    names = [str(d.get("name", "")) for d in rows]
    vals = [abs(float(d.get("d_mean") or 0.0)) for d in rows]

    fig, ax = plt.subplots(figsize=(6.2, max(2.4, 0.62 * len(rows) + 1.6)))
    ypos = list(range(len(rows)))
    colors = ["#c44e52" if i == 0 else "#4c72b0" for i in ypos]
    ax.barh(ypos, [2 * v for v in vals], height=0.55, left=[-v for v in vals],
            color=colors, edgecolor="black", linewidth=0.6, alpha=0.85)
    ax.axvline(0.0, color="black", lw=1.0)
    ax.set_yticks(ypos)
    ax.set_yticklabels(names)
    ax.invert_yaxis()                 # 最敏感的放最上面
    ax.set_xlabel(xlabel)
    ax.set_title(title or f"Tornado: each factor at $\\pm${delta:.0%}")
    # 只标右侧 —— 负侧标签会压在 y 轴标签上（实测截图确认）。
    # 线性拟合下两侧对称，一个数就够了，不必标两遍。
    for i, v in enumerate(vals):
        ax.text(v * 1.03, i, f"{v:.4g}", va="center", ha="left",
                fontsize=8)
    ax.set_xlim(-max(vals) * 1.35 if vals else 1, max(vals) * 1.35 if vals else 1)
    ax.grid(axis="x", alpha=0.25)
    return _save(fig, out)


def _short(t, n=24):
    """截短标签，避免坐标轴文字过长挤掉图。"""
    t = str(t)
    return t if len(t) <= n else t[:n - 1] + chr(8230)


def plot_surface(s, out="surface", title=None, cbar_label="predicted"):
    """响应面：填色等高线 + 实测点。

    用等高线而不是 3D 曲面：3D 的透视会让人读错高低，等高线在纸面上
    不会，而且实测点能直接叠上去看贴合程度。
    """
    if not s:
        return None
    fig, ax = plt.subplots(figsize=(5.4, 4.3))
    cf = ax.contourf(s["g1"], s["g2"], s["Z"], levels=16, cmap="viridis")
    ax.scatter(s["px"], s["py"], c=s["pz"], s=22, cmap="viridis",
               edgecolor="black", linewidth=0.35, zorder=3)
    cb = fig.colorbar(cf, ax=ax)
    cb.set_label(cbar_label)
    ax.set_xlabel(_short(s["x_name"], 40))
    ax.set_ylabel(_short(s["y_name"], 40))
    if s.get("fixed_name"):
        ax.set_title(title or
                     f"{_short(s['x_name'], 20)} vs "
                     f"{_short(s['y_name'], 20)} "
                     f"({_short(s['fixed_name'], 16)} = {s['fixed_value']:g})",
                     fontsize=8)
    elif title:
        ax.set_title(title, fontsize=9)
    return _save(fig, out)


def plot_surface_trio(surfs, out="surfaces", titles=None):
    """三张响应面并排。

    为什么要并排而不是分开：本题的关键结论之一是「三个指标对几何的
    响应形式不同」。分开成三页，读者要来回翻才能看出这个对比；
    并排则一眼可见。
    """
    surfs = [x for x in (surfs or []) if x]
    if not surfs:
        return None
    fig, axes = plt.subplots(1, len(surfs), figsize=(4.3 * len(surfs), 3.9))
    if len(surfs) == 1:
        axes = [axes]
    for ax, s in zip(axes, surfs):
        cf = ax.contourf(s["g1"], s["g2"], s["Z"], levels=14,
                         cmap="viridis")
        ax.scatter(s["px"], s["py"], c=s["pz"], s=16, cmap="viridis",
                   edgecolor="black", linewidth=0.3, zorder=3)
        ax.set_xlabel(_short(s["x_name"], 40), fontsize=8)
        ax.set_ylabel(_short(s["y_name"], 40), fontsize=8)
        _t = (titles or {}).get(s.get("y_en") or "", "")
        if not _t:
            _t = s.get("y_en") or s.get("y_name") or ""
        ax.set_title(_t, fontsize=9)
        cb = fig.colorbar(cf, ax=ax, fraction=0.046)
        cb.set_label("predicted", fontsize=8)
    fig.tight_layout()
    return _save(fig, out)


PLOTTERS = dict(surface_trio=plot_surface_trio,surface=plot_surface,tornado=plot_tornado,corr=plot_corr, box=plot_box, hist=plot_hist,
                pred=plot_pred, sens=plot_sens, pareto=plot_pareto,
                resid=plot_resid)


# ══════════════════════════════════════════════════════════════════════
def selftest() -> int:
    bad = 0
    n = 0

    def ck(name, cond, detail=""):
        nonlocal bad, n
        n += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
              + (f"  — {detail}" if detail else ""))
        if not cond:
            bad += 1

    here = os.path.dirname(os.path.abspath(__file__))
    outdir = os.path.join(here, "out", "fig_mpl_selftest")
    rng = np.random.default_rng(0)

    # 字体设置
    ck("pdf.fonttype=42", matplotlib.rcParams["pdf.fonttype"] == 42)
    ck("svg.fonttype=none", matplotlib.rcParams["svg.fonttype"] == "none")
    ck("中文字体可用", _CJK is not None, _CJK or "无（不致命）")

    # corr
    M = np.corrcoef(rng.normal(size=(4, 30)))
    r = plot_corr(M, ["alpha", "beta", "gamma", "delta"],
                  out=os.path.join(outdir, "corr"))
    ck("corr 出 PDF+PNG", all(k in r for k in ("pdf", "png")),
       f"{r['pdf']['bytes']} / {r['png']['bytes']}")

    # box
    data = [rng.normal(0, 1, 40), rng.normal(0.5, 1.2, 40),
            rng.normal(-0.3, 0.8, 40)]
    r = plot_box(data, ["group A", "group B", "group C"],
                 out=os.path.join(outdir, "box"), ylabel="thermal resistance")
    ck("box 出 PDF+PNG", all(k in r for k in ("pdf", "png")),
       f"{r['pdf']['bytes']} 字节")

    # hist（带 LaTeX 的图例 —— 这是用户截图的原始问题）
    r = plot_hist(rng.normal(0.7467, 0.01127, 84),
                  out=os.path.join(outdir, "hist"),
                  xlabel="thermal resistance")
    ck("hist 出 PDF+PNG", all(k in r for k in ("pdf", "png")))
    pdf = open(r["pdf"]["path"], "rb").read()
    ck("hist PDF 字体嵌入", b"/FontFile2" in pdf)
    ck("hist PDF 无 Type3 轮廓", b"/Type3" not in pdf)

    # pred
    t = rng.normal(0.75, 0.01, 60)
    p = t + rng.normal(0, 0.004, 60)
    r = plot_pred(t, p, out=os.path.join(outdir, "pred"))
    ck("pred 出 PDF+PNG", all(k in r for k in ("pdf", "png")))

    # sens
    xs = [-1, 0, 1]
    curves = [dict(x=xs, y=[0.75, 0.7467, 0.743]),
              dict(x=xs, y=[0.742, 0.7467, 0.751])]
    r = plot_sens(curves, ["bin-fin / width", "manifold / depth"],
                  out=os.path.join(outdir, "sens"))
    ck("sens 出 PDF+PNG", all(k in r for k in ("pdf", "png")))
    svg_path = os.path.join(outdir, "sens.svg")
    fig, ax = plt.subplots()
    # 用普通文字测 —— mathtext（$\mu$）在 SVG 里必然被转成路径，
    # 那是 matplotlib 的行为，不是缺陷。我们最终用 PDF 进 LaTeX，
    # 所以这里只关心「普通文字是否仍是可编辑的 text 节点」。
    ax.plot([1, 2], [1, 2], label="plain label text")
    fig.savefig(svg_path, format="svg")
    plt.close(fig)
    svg = open(svg_path, encoding="utf-8").read()
    ck("SVG 保留文字（可编辑）", "<text" in svg)
    # 不断言完整字符串：matplotlib 会把文字拆成 <tspan> 或引用 <use> 字形，
    # 完整标签在 SVG 里搜不到很正常。真正能证明「文字还是文字」的是
    # <text> 节点带着 font-family —— 路径没有这个属性。
    ck("SVG 文字带字体属性（非路径化）",
       "font-family" in svg and svg.count("<text") >= 5,
       f"{svg.count('<text')} 个 text 节点")

    # pareto
    M2 = rng.normal(size=(40, 2))
    fidx = [0, 1, 2]
    r = plot_pareto(M2, fidx, ["thermal resistance", "pressure drop"],
                    out=os.path.join(outdir, "pareto"))
    ck("pareto 出 PDF+PNG", all(k in r for k in ("pdf", "png")))

    # resid
    r = plot_resid(t, rng.normal(0, 0.004, 60),
                   out=os.path.join(outdir, "resid"))
    ck("resid 出 PDF+PNG", all(k in r for k in ("pdf", "png")))

    # 全部图都产生了 PDF 和 PNG
    files = os.listdir(outdir)
    ck("7 种图各出两格式", len([f for f in files if f.endswith(".pdf")]) == 7
       and len([f for f in files if f.endswith(".png")]) == 7,
       f"{len(files)} 个文件")

    print(f"\n{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    print(f"  产物目录：{outdir}")
    return 0 if bad == 0 else 1


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="matplotlib 绘图后端")
    ap.add_argument("cmd", nargs="?", default="selftest",
                    choices=["selftest"])
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        return selftest()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
