#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""响应面收尾：修标签截断，加三联图对比。

三张独立的图要占三页版面，而且「热阻是平面、压降是曲面」这个对比
被页面隔开了。做成一张三联图，对比一眼可见，也省版面。
"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "plot_mpl.py")
s = open(P, encoding="utf-8").read()

# ① 标签不截断
s = s.replace('    ax.set_xlabel(_short(s["x_name"], 28))\n'
              '    ax.set_ylabel(_short(s["y_name"], 28))',
              '    ax.set_xlabel(_short(s["x_name"], 40))\n'
              '    ax.set_ylabel(_short(s["y_name"], 40))')

# ② 三联图
if "def plot_surface_trio(" not in s:
    F = '''def plot_surface_trio(surfs, out="surfaces", titles=None):
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


'''
    k = s.find("PLOTTERS = dict(")
    s = s[:k] + F + s[k:]
    s = s.replace("PLOTTERS = dict(",
                  "PLOTTERS = dict(surface_trio=plot_surface_trio,", 1)

ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("① plot_mpl 修好了标签，加了三联图")

# ══ mmkit 加 trio 分支 ══
P2 = os.path.join(HERE, "mmkit.py")
s2 = open(P2, encoding="utf-8").read()
if 'kind == "surfaces"' not in s2:
    OLD = '        elif kind == "surface":'
    NEW = '''        elif kind == "surfaces":
            # 三个指标各一张，拼成一张三联图
            _ys = ds.pick(a.y.split(",")) if a.y else []
            _ys = [c for c in _ys if c in ds.num_names]
            _xss = ds.pick(a.x.split(",")) if a.x else []
            _sfs = []
            for _yc in _ys:
                _s = mm.surface(ds, _yc, _xss)
                if not _s:
                    continue
                _s = dict(_s)
                for _k in ("x_name", "y_name", "fixed_name"):
                    if _s.get(_k):
                        _s[_k] = _en_text(str(_s[_k]))
                _d = _paper.describe(_yc)
                _s["y_en"] = _d[0] if _d else _yc
                _sfs.append(_s)
            if _sfs:
                paths = M.plot_surface_trio(_sfs, base)
        elif kind == "surface":'''
    if OLD in s2:
        s2 = s2.replace(OLD, NEW, 1)
        ast.parse(s2)
        compile(s2, P2, "exec")
        open(P2, "w", encoding="utf-8", newline="\n").write(s2)
        print("② mmkit 加了 surfaces 分支")

import re
m = re.search(r'(ap\.add_argument\(\"--kind", default="scatter",\s*\n\s*choices=\[)(.*?)(\])',
               s2, re.S)
if m and '"surfaces"' not in m.group(2):
    s2 = s2[:m.start(2)] + m.group(2) + ', "surfaces"' + s2[m.end(2):]
    ast.parse(s2)
    open(P2, "w", encoding="utf-8", newline="\n").write(s2)
    print("③ surfaces 已注册")

import subprocess
import sys
r = subprocess.run([sys.executable, "mmkit.py", "plot", "--kind", "surfaces",
                    "--y", "热阻,压降,温度", "--x", "宽度,深高,排数",
                    "--out-png", os.path.join(HERE, "out", "fig",
                                             "surfaces.png")],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
o = (r.stdout or r.stderr or "").strip().splitlines()
print("  " + (o[0][:90] if o else "(无输出)"))
if "Traceback" in (r.stderr or ""):
    print("  ! " + (r.stderr or "").strip().splitlines()[-1][:110])
