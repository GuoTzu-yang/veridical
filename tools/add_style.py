#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 scienceplots 主题接进 plot_mpl。

用户反馈：图 8（帕累托）和图 10（敏感性）像 Jupyter 默认输出，
缺顶刊级别的配色与线宽。

scienceplots 的 `science` + `ieee` 组合就是为期刊排版做的：
更细的坐标轴线、更紧的留白、Times/STIX 字体、低饱和配色。

注意：它必须在 matplotlib 的 rcParams 上生效，且要放在所有绘图之前。
如果没装，退回原来的手写 rcParams（不能让缺依赖直接崩）。
"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "plot_mpl.py")
s = open(P, encoding="utf-8").read()

OLD_MARK = "pdf.fonttype = 42"
if "scienceplots" not in s:
    # 找到设置 rcParams 的那一段，在它之后插入 style
    ANCHOR = "plt.rcParams.update("
    i = s.find(ANCHOR)
    assert i > 0, "找不到 rcParams.update"
    # 找这一段的结尾（下一个空行后的顶层语句）
    j = s.find("\n\n\n", i)
    INSERT = '''

# ── 期刊级主题（scienceplots）──
# 用户反馈图「像 Jupyter 默认输出」。science/ieee 这套是期刊排版用的：
# 细轴线、紧留白、Times 系字体、低饱和配色。
# 没装就退回上面的手写 rcParams，不能让缺依赖直接崩。
try:
    import scienceplots as _sp          # noqa: F401
    plt.style.use(["science", "ieee"])
    plt.rcParams.update({
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
    _THEME = "science+ieee"
except Exception:                        # noqa: BLE001
    _THEME = "fallback"

'''
    s = s[:j] + INSERT + s[j:]
    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("① scienceplots 主题已接入")

import subprocess
import sys
r = subprocess.run([sys.executable, "-c",
                    "import plot_mpl as M; print(' 主题:', M._THEME)"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
print("  " + ((r.stdout or r.stderr or "").strip().splitlines() or ["?"])[-1])
