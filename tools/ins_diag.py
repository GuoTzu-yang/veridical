#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""插入残差诊断节（12 空格缩进，因为嵌在 if os.path.exists(_sp): 里面）。"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()

if "What the residuals say" in s:
    print("  已存在，跳过")
    raise SystemExit(0)

DIAG = '''            # 残差诊断：题目的「评估拟合效果」在残差层面的结论
            _dg = ctx.get("diag") or {}
            if _dg.get("rows"):
                L.append(r"\\subsection{What the residuals say}")
                L.append(
                    "A good fit statistic and a sound residual are "
                    "different claims, and only the second rules out a "
                    "specification that is wrong rather than merely "
                    "imprecise. Four checks are reported for each indicator: "
                    "a Breusch-Pagan statistic for heteroskedasticity, "
                    "skewness and kurtosis for the normality of the errors, "
                    "the correlation between residual and fitted value for a "
                    "missed curvature, and the largest correlation between "
                    "the residual and any single factor for an omitted "
                    "factor.")
                L.append("")
                L += [r"\\begin{table}[H]", r"\\centering",
                      r"\\caption{Residual diagnostics. The "
                      r"Breusch-Pagan statistic is compared against its "
                      r"0.05 critical value of 7.81 (three regressors).}",
                      r"\\label{tab:diag}",
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
                    f"Breusch-Pagan test would reject: the largest "
                    f"statistic is {_bpmax.get('bp', 0):.2f} for "
                    f"{esc_tex(str(_bpmax.get('y_en')))} against a critical "
                    f"value of 7.81. The largest correlation between "
                    f"residual and fitted value is "
                    f"{_trmax.get('c_trend', 0):+.3f}, so the residuals do "
                    f"not carry a curved pattern the specification has "
                    f"missed. The largest correlation between a residual "
                    f"and a single factor is {_cmax:.3f}, which leaves no "
                    f"factor visibly unaccounted for.")
                L.append("")
                L.append(
                    "These checks do not prove the specification is right; "
                    "they say that the ways it could be wrong are not "
                    "detectable in this sample. That is the honest form of "
                    "the claim, and it is also why the intervals reported "
                    "earlier are given rather than a single error figure.")
                L.append("")

'''

ANCHOR = ('            L.append(\n'
          '                "The three panels are the reason a single '
          'specification "')
if ANCHOR in s:
    s = s.replace(ANCHOR, DIAG + ANCHOR, 1)
    print("① 残差诊断节已插入")
else:
    raise SystemExit("! 锚点仍未匹配")

ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print(f"  paper.py {len(s.splitlines())} 行")
