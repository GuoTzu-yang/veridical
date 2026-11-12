#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""响应面：代理模型在两个最强因子上的映射曲面。

题目要「刻画结构参数与性能指标之间的映射关系」。原来只有系数表和符号
检验，没有任何一张图展示这个映射长什么样。

要点：
  · 用该指标**自己的**最佳模型（热阻线性、压降与温度二次），
    一律用线性画出来的面是假的
  · 按线性部分系数绝对值挑影响最大的两个因子作坐标，第三个固定中位数
  · 填色等高线 + 实测点叠上去：点落在等高线上说明贴合，偏离说明漏了东西
"""
import ast
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ══ ① mm.surface ══
P1 = os.path.join(HERE, "mm.py")
s1 = open(P1, encoding="utf-8").read()
if "def surface(" not in s1:
    FUNC = '''

def surface(ds: DS, yname: str, xnames: list[str], n: int = 42) -> dict:
    """代理模型在两个最强因子上的响应面（网格 + 预测值 + 实测点）。"""
    y = np.asarray(ds.col(yname), dtype=float)
    X = np.column_stack([np.asarray(ds.col(c), dtype=float)
                         for c in xnames])
    r = fit(ds, yname, xnames)
    kind = (r.get("best") or {}).get("kind") or "linear"
    A = design(X, kind)
    if A is None:
        return None
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    lin = np.column_stack([np.ones(len(y)), X])
    lb, *_ = np.linalg.lstsq(lin, y, rcond=None)
    order = np.argsort(-np.abs(lb[1:]))
    i, j = int(order[0]), int(order[1])
    k = (3 - i - j) if len(xnames) == 3 else -1
    g1 = np.linspace(X[:, i].min(), X[:, i].max(), n)
    g2 = np.linspace(X[:, j].min(), X[:, j].max(), n)
    G1, G2 = np.meshgrid(g1, g2)
    grid = np.zeros((n * n, len(xnames)))
    grid[:, i] = G1.ravel()
    grid[:, j] = G2.ravel()
    fixed_val = None
    if k >= 0:
        fixed_val = float(np.median(X[:, k]))
        grid[:, k] = fixed_val
    Z = (design(grid, kind) @ beta).reshape(n, n)
    return dict(x_name=xnames[i], y_name=xnames[j],
                fixed_name=(xnames[k] if k >= 0 else None),
                fixed_value=fixed_val, g1=g1, g2=g2, Z=Z, kind=kind,
                px=X[:, i], py=X[:, j], pz=y)


'''
    k = s1.find("def print_fit(")
    s1 = s1[:k] + FUNC + s1[k:]
    ast.parse(s1)
    compile(s1, P1, "exec")
    open(P1, "w", encoding="utf-8", newline="\n").write(s1)
    print("① mm.surface 已加")

# ══ ② plot_mpl.plot_surface ══
P2 = os.path.join(HERE, "plot_mpl.py")
s2 = open(P2, encoding="utf-8").read()
if "def plot_surface(" not in s2:
    F = '''def plot_surface(s, out="surface", title=None, cbar_label="predicted"):
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
    ax.set_xlabel(_short(s["x_name"], 28))
    ax.set_ylabel(_short(s["y_name"], 28))
    if s.get("fixed_name"):
        ax.set_title(title or
                     f"{_short(s['x_name'], 20)} vs "
                     f"{_short(s['y_name'], 20)} "
                     f"({_short(s['fixed_name'], 16)} = {s['fixed_value']:g})",
                     fontsize=8)
    elif title:
        ax.set_title(title, fontsize=9)
    return _save(fig, out)


'''
    k = s2.find("PLOTTERS = dict(")
    s2 = s2[:k] + F + s2[k:]
    s2 = s2.replace("PLOTTERS = dict(",
                    "PLOTTERS = dict(surface=plot_surface,", 1)
    ast.parse(s2)
    compile(s2, P2, "exec")
    open(P2, "w", encoding="utf-8", newline="\n").write(s2)
    print("② plot_surface 已加")

# ══ ③ mmkit 分支 + choices ══
P3 = os.path.join(HERE, "mmkit.py")
s3 = open(P3, encoding="utf-8").read()
if 'kind == "surface"' not in s3:
    OLD = '        elif kind == "tornado":'
    NEW = '''        elif kind == "surface":
            if not a.y or not a.x:
                return None
            _sf = mm.surface(ds, ds.pick([a.y])[0],
                             ds.pick(a.x.split(",")))
            if _sf:
                paths = M.plot_surface(
                    _sf, base, title=f"{_en_text(a.y)} response surface")
        elif kind == "tornado":'''
    if OLD in s3:
        s3 = s3.replace(OLD, NEW, 1)
        ast.parse(s3)
        compile(s3, P3, "exec")
        open(P3, "w", encoding="utf-8", newline="\n").write(s3)
        print("③ mmkit 加了 surface 分支")

m = re.search(r'choices=\[(.*?)\]', s3, re.S)
if m and '"surface"' not in m.group(1):
    s3 = s3[:m.start(1)] + m.group(1) + ', "surface"' + s3[m.end(1):]
    ast.parse(s3)
    open(P3, "w", encoding="utf-8", newline="\n").write(s3)
    print("④ surface 已注册")
