#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""加「What each claim rests on」一节：每条声明挂上证据或明确标注无支撑。

为什么需要
----------
现在 gate 能查「结论有没有数字」（numbers 124/124），但没有一份显式清单
说明「哪些话我还没证据」。案例库的输出契约第 11 项正是这个：

    风险、无支撑的声明、还需要的数据

内容全部由 ctx 生成，不硬编码数字。判断规则：
    · 预测区间相对宽度 > 50%  → 该指标的预测不能用于具体值
    · 符号检验里 not fixed    → 机理没给方向，只有数据
    · 因子跨度为 0            → 无变异，其效应不可识别
    · 样本 < 30               → 小样本，结论偏弱
"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()

FUNC = '''

def _claim_ledger(ctx) -> list[str]:
    """生成「声明 → 证据 / 无支撑」清单。全部基于 ctx 里的事实。"""
    L = []
    rows = []

    # ① 模型形式：有交叉验证表
    mm = ctx.get("multimodel") or {}
    if (mm.get("rows") or []):
        rows.append(("The functional form is chosen by comparable "
                     "out-of-sample error rather than by fit.",
                     r"Table~\\ref{tab:multi}", ""))
    # ② 前沿：有表
    fd = ctx.get("front_detail") or {}
    if fd.get("front"):
        rows.append((f"There are {len(fd['front'])} non-dominated "
                     f"designs, not one.",
                     r"Table~\\ref{tab:front} and Figure~\\ref{fig:pareto}", ""))
    # ③ 预测区间：宽到什么程度
    pi = ctx.get("pred_int") or {}
    for r in (pi.get("rows") or []):
        w = r.get("width_rel_cv") or 0
        yn = r.get("y_en") or "the indicator"
        if w > 0.50:
            rows.append((f"Predicted values of {yn}.",
                         "", f"its 95\\% interval spans {w * 100:.0f}\\% "
                             f"of the mean, so it is used for ranking only"))
    # ④ 符号检验：机理没给方向的
    sg = ctx.get("signs") or {}
    for r in (sg.get("rows") or []):
        if str(r.get("predicted", "")).lower().startswith("not"):
            rows.append((f"The sign of {r.get('y_en')} against "
                         f"{r.get('x_en')}.",
                         "", "the mechanism does not fix it; only the data "
                             "speak here, on this sample"))
    # ⑤ 跨度为零的因子
    for sp in (ctx.get("spans") or []):
        try:
            if float(sp.get("span") or 1) <= 0:
                rows.append((f"The effect of {sp.get('x_en')}.", "",
                             "the factor has no variation in the data, so "
                             "its effect is not identifiable"))
        except (TypeError, ValueError):
            pass
    # ⑥ 小样本
    n = ctx.get("n") or ctx.get("rows")
    try:
        if n is not None and int(n) < 30:
            rows.append(("Every conclusion in this report.", "",
                         f"the sample holds {int(n)} observations; "
                         f"coefficients carry that uncertainty"))
    except (TypeError, ValueError):
        pass

    if not rows:
        return L

    L += [r"\\subsection{What each claim rests on}", ""]
    L.append(
        "It is worth stating separately which of the claims above are "
        "supported by a reported computation and which are not. The "
        "distinction is not a formality: a claim without a number behind "
        "it should be read as a hypothesis this report did not test, "
        "rather than as a result.")
    L.append("")
    L.append(r"\\begin{itemize}")
    for claim, anchor, caveat in rows:
        if caveat:
            L.append(rf"  \\item \\emph{{Not supported:}} {claim} {caveat}.")
        else:
            L.append(rf"  \\item {claim} Evidence: {anchor}.")
    L.append(r"\\end{itemize}")
    L.append("")
    return L


'''

if "_claim_ledger" not in s:
    # 插在 _mech 定义之前（模块级函数，build 里要用）
    k = s.find("def build(")
    assert k > 0, "找不到 build"
    s = s[:k] + FUNC + s[k:]

    # 在 Evaluation 之前调用
    ANCHOR = '    L += [r"\\section{Evaluation}"'
    if ANCHOR not in s:
        ANCHOR = '    L.append(r"\\section{Evaluation}")'
    assert ANCHOR in s, "找不到 Evaluation 锚点"
    s = s.replace(ANCHOR, "    L += _claim_ledger(ctx)\n" + ANCHOR, 1)

    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  已加 _claim_ledger 并接在 Evaluation 之前")
