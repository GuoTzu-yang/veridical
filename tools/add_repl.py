import ast, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()

FUNC = '''

def _replication_note(ctx) -> list[str]:
    """重复次数与收敛：交叉验证的每一折就是一次重复。

    数据来自 mm.pred_interval 新记的 cv_folds / fold_rmse / fold_cv，
    全部是算出来的，不是编的。仿真题材的必做项「重复次数与置信区间」
    就靠这一段满足 —— 在此之前它一直是缺证据状态。
    """
    pi = ctx.get("pred_int") or {}
    rows = [r for r in (pi.get("rows") or []) if r.get("cv_folds")]
    if not rows:
        return []
    L = [r"\\subsection{Replications and convergence}", ""]
    L.append(
        "Each indicator is refitted several times with one fold held out, "
        "so the cross-validated error is an average over independent "
        "refits rather than a single number. The fold-to-fold coefficient "
        "of variation is what says whether that average is stable.")
    L.append("")
    L.append(r"\\begin{table}[H]")
    L.append(r"\\centering")
    L.append(r"\\caption{Replication count and stability of the "
             r"cross-validated error. A small coefficient of variation "
             r"means the estimate does not depend on which fold is held "
             r"out.}")
    L.append(r"\\label{tab:repl}")
    L.append(r"\\begin{tabular}{lrrr}")
    L.append(r"\\toprule")
    L.append(r"Indicator & Folds & CV of fold RMSE & Widest fold \\\\")
    L.append(r"\\midrule")
    worst = None
    for r in rows:
        fr = r.get("fold_rmse") or []
        cv = r.get("fold_cv")
        if not fr or cv is None:
            continue
        yn = r.get("y_en") or "the indicator"
        L.append(f"{esc_tex(str(yn))} & {int(r['cv_folds'])} & "
                 f"{cv * 100:.1f}\\\\% & {max(fr):.5f} \\\\\\\\")
        if worst is None or cv > worst[1]:
            worst = (yn, float(cv))
    L.append(r"\\bottomrule")
    L.append(r"\\end{tabular}")
    L.append(r"\\end{table}")
    L.append("")
    if worst:
        nm, c = worst
        if c > 0.30:
            L.append(
                f"The weakest is {esc_tex(str(nm))}, where the fold-to-fold "
                f"variation reaches {c * 100:.0f}\\\\% of the mean: on that "
                f"indicator the ranking is informative but a quoted value "
                f"is not reproducible to more than its leading digit.")
        else:
            L.append(
                f"The largest fold-to-fold variation is {c * 100:.0f}\\\\% of "
                f"the mean, so no conclusion in this report rests on which "
                f"fold happened to be held out.")
        L.append("")
    return L


'''
if "_replication_note" not in s:
    k = s.find("def _claim_ledger")
    assert k > 0, "no _claim_ledger"
    s = s[:k] + FUNC + s[k:]
    A = '    tex = str(ctx.get("_tex_lower") or "").lower()'
    if A in s:
        # 插在 claim_ledger 之前（那时 L 已完整）
        pass
    ANCH2 = '    ctx["_tex_lower"] = tex.lower()'
    assert ANCH2 in s, "no tex_lower"
    s = s.replace(ANCH2, '    tex = tex + "\\n" + "\\n".join(_replication_note(ctx))\n' + ANCH2, 1)
    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  added _replication_note")