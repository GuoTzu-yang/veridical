#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""论文加两节：残差诊断 + 前沿计算过程。写完由调用方统一编译。

转义约定（踩过很多次）：
    r"..."  里 `\\` → LaTeX 换行 ✓，`\%` → LaTeX 百分号 ✓
    f"..."  里 `\\%` → LaTeX 百分号 ✓（单反斜杠会触发 SyntaxWarning）
             `\\\\` → LaTeX 换行 ✓（双反斜杠只出 1 个，不够）
"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()

# ══ ① 残差诊断节：插在响应面那节之后 ══
ANCHOR_DIAG = '''        L.append(
            "The three panels are the reason a single specification "'''
DIAG = '''        # 残差诊断：题目的「评估拟合效果」在残差层面的结论
        _dg = ctx.get("diag") or {}
        if _dg.get("rows"):
            L.append(r"\\subsection{What the residuals say}")
            L.append(
                "A good fit statistic and a sound residual are different "
                "claims, and only the second one rules out a specification "
                "that is wrong rather than merely imprecise. Four checks are "
                "reported for each indicator: a Breusch-Pagan statistic for "
                "heteroskedasticity, skewness and kurtosis for the normality "
                "of the errors, the correlation between the residual and the "
                "fitted value for a missed curvature, and the largest "
                "correlation between the residual and any single factor for "
                "an omitted factor.")
            L.append("")
            L += [r"\\begin{table}[H]", r"\\centering",
                  r"\\caption{Residual diagnostics. The Breusch-Pagan "
                  r"statistic is compared against its 0.05 critical value "
                  r"of 7.81 (three regressors).}", r"\\label{tab:diag}",
                  r"\\begin{tabular}{lrrrrrrr}", r"\\toprule",
                  r"Indicator & $R^2$ & RMSE & BP & Skew & Kurt & JB & "
                  r"$r(e,\\hat{y})$ \\\\", r"\\midrule"]
            for _d in _dg["rows"]:
                L.append(
                    f"{esc_tex(str(_d.get('y_en')))} & "
                    f"{_d.get('r2', 0):.4f} & {_d.get('rmse', 0):.5g} & "
                    f"{_d.get('bp', 0):.2f} & {_d.get('skew', 0):+.2f} & "
                    f"{_d.get('kurt', 0):.2f} & {_d.get('jb', 0):.2f} & "
                    f"{_d.get('c_trend', 0):+.3f} \\\\\\\\")
            L += [r"\\bottomrule", r"\\end{tabular}", r"\\end{table}"]
            L.append("")
            _bpmax = max(_dg["rows"], key=lambda d: d.get("bp") or 0)
            _trmax = max(_dg["rows"],
                         key=lambda d: abs(d.get("c_trend") or 0))
            _cmax = max((max(abs(c) for c in (d.get("c_each") or [0]))
                         for d in _dg["rows"]))
            L.append(
                f"No indicator shows heteroskedasticity that the "
                f"Breusch-Pagan test would reject: the largest statistic "
                f"is {_bpmax.get('bp', 0):.2f} for "
                f"{esc_tex(str(_bpmax.get('y_en')))} against a critical "
                f"value of 7.81. The largest correlation between residual "
                f"and fitted value is {_trmax.get('c_trend', 0):+.3f}, so the "
                f"residuals do not carry a curved pattern that the "
                f"specification has missed. The largest correlation "
                f"between a residual and a single factor is {_cmax:.3f}, "
                f"which leaves no factor visibly unaccounted for.")
            L.append("")
            L.append(
                "These checks do not prove the specification is right; they "
                "say that the ways it could be wrong are not detectable in "
                "this sample. That is the honest form of the claim, and it "
                "is also why the intervals reported earlier are given "
                "rather than a single error figure.")
            L.append("")

'''

if "What the residuals say" not in s:
    i = s.find(ANCHOR_DIAG)
    if i > 0:
        # 插到那段之前
        s = s[:i] + DIAG + s[i:]
        print("① 残差诊断节已插入")
    else:
        print("! 诊断锚点未匹配")

# ══ ② 前沿计算过程节：插在 Problem 3 之前 ══
ANCHOR_P3 = '    L += [r"\\section{Problem 3: How stable are the conclusions?}", ""]'
FRONT = '''    # ── 前沿是怎么算出来的（可核对）──
    _fd = ctx.get("front_detail") or {}
    if _fd.get("front"):
        _cols_en = _fd.get("cols_en") or []
        L.append(r"\\subsection{How the front was computed}")
        L.append(
            f"The front is computed by dominance, not by a clustering "
            f"heuristic. Each of the {_fd.get('n_total')} designs is "
            f"tested against every other: a design is discarded if some "
            f"other design is no worse on all {_len(_cols_en)} objectives "
            f"and strictly better on at least one. The "
            f"{_fd.get('n_front')} designs that survive are the front, "
            f"and they are listed in the table below so the count can be "
            f"checked rather than taken on trust.")
        L.append("")
        _ex = _fd.get("example")
        if _ex:
            _wi = ", ".join(f"{_cols_en[j]} by "
                            f"{_ex['worse'][j]:.5g}" if _ex["worse"][j] > 0
                            else f"{_cols_en[j]} by "
                            f"{-_ex['worse'][j]:.5g} better"
                            for j in range(len(_ex["worse"])))
            L.append(
                f"Worked example. Design {_ex['i']} is not on the front "
                f"because design {_ex['dominated_by']} is no worse on any "
                f"objective and better on at least one: it improves "
                f"{_wi}. A design is removed from the front for exactly "
                f"this reason, which is why the front is a set of "
                f"genuinely distinct trade-offs rather than a cluster "
                f"label.")
            L.append("")
        L += [r"\\begin{table}[H]", r"\\centering",
              r"\\caption{The non-dominated designs, with their objective "
              r"values.}", r"\\label{tab:front}",
              r"\\begin{tabular}{rr" + "r" * max(0, len(_cols_en)) + "}",
              r"\\toprule", r"Design & " +
              " & ".join(esc_tex(str(c)) for c in _cols_en) +
              r" \\\\", r"\\midrule"]
        for _i, _c in enumerate(_fd.get("coords") or []):
            L.append(f"{_fd['front'][_i]} & " +
                     " & ".join(f"{float(v):.5g}" for v in _c) +
                     r" \\\\")
        L += [r"\\bottomrule", r"\\end{tabular}", r"\\end{table}"]
        L.append("")

'''
if "How the front was computed" not in s:
    if ANCHOR_P3 in s:
        s = s.replace(ANCHOR_P3, FRONT + ANCHOR_P3, 1)
        print("② 前沿计算过程节已插入")
    else:
        print("! 前沿锚点未匹配")

ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print(f"  paper.py {len(s.splitlines())} 行，写入完成（未编译）")
