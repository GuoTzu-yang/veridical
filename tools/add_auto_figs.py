import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "mmkit.py")
s = open(P, encoding="utf-8").read()

FUNC = '''

_FIG_KINDS = ("hist", "box", "corr", "resid", "qq", "pred", "sens",
              "cand", "tornado", "surfaces", "pareto", "flow")


def _auto_figs(ds, ycol, xs, min_cols, tex_path):
    """把 12 张图直接生成到 tex 同级目录的 fig/ 下。

    冷启动实测：只跑 run --compile 会得到一篇 400 KB、一张图都没有的 PDF。
    光给提示不够 —— 「直通」的意思是一条命令出完整稿，不是出稿再加 12 条命令。
    """
    import subprocess
    base = os.path.dirname(os.path.abspath(tex_path))
    figd = os.path.join(base, "fig")
    os.makedirs(figd, exist_ok=True)
    data = getattr(ds, "path", "") or ""
    ys = _paper.describe(ycol)[0]
    xnames = ",".join(_paper.describe(c)[0] for c in xs)
    mins = ",".join(_paper.describe(c)[0] for c in (min_cols or []))
    ok = 0
    for k in _FIG_KINDS:
        out = os.path.join(figd, k)
        try:
            subprocess.run(
                [sys.executable, os.path.abspath(__file__), "plot",
                 "--kind", k, "--data", data, "--y", ys, "--x", xnames,
                 "--min", mins, "--out-png", out],
                capture_output=True, timeout=120)
        except Exception:                           # noqa: BLE001
            continue
        if os.path.exists(out + ".pdf") and os.path.getsize(out + ".pdf") > 1000:
            ok += 1
    return ok


'''
if "_auto_figs" not in s:
    k = s.find("def _collect_figures")
    assert k > 0
    s = s[:k] + FUNC.lstrip("\n") + s[k:]

    # 在 ctx 构造前预生成
    OLD = "            figures=_collect_figures(tex_path),"
    assert OLD in s, "no figures slot"
    NEW = ("            figures=_figs_pre,")
    s = s.replace(OLD, NEW, 1)

    # 找 ctx = dict( 的位置，在前面插入预计算
    m = s.find("        ctx = dict(")
    if m < 0:
        m = s.find("ctx = dict(")
    assert m > 0, "no ctx = dict("
    PRE = ("        # 没有图就先自己出图 —— 一条命令出完整稿。\n"
           "        _figs_pre = _collect_figures(tex_path)\n"
           "        if (not _figs_pre) and tex_path and not no_figs:\n"
           "            _n = _auto_figs(ds, ycol, xs, min_cols, tex_path)\n"
           "            if _n:\n"
           "                _figs_pre = _collect_figures(tex_path)\n"
           "                print(f'  图：自动生成 {_n} 张 -> '\n"
           "                      f'{os.path.dirname(os.path.abspath(tex_path))}'\n"
           "                      f'{os.sep}fig')\n")
    s = s[:m] + PRE + s[m:]

    # 加 no_figs 参数
    OLD2 = "        lang: str = \"en\",\n"
    assert OLD2 in s, "no lang param"
    s = s.replace(OLD2, OLD2 + "        no_figs: bool = False,\n", 1)

    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  _auto_figs wired")