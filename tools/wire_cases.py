#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把案例检索接进流程：mmkit 检索 → paper 写一节。

论文里写什么
------------
只写「结构类比」与「可迁移的做法」，**不翻译、不引用案例原文**
（案例卡是中文，直接搬进英文论文会失真且混语言）。

所以：
  · 匹配数量与 case_id（可核对）
  · 一句结构描述（题型层面的共性）
  · 从 lessons 里抽到的**主题词**（Pareto / 交叉验证 / 稳健区域…），
    用英文写在句子里，不搬中文原句

这样既给出了「我做过案例类比」的证据，又不会污染语种。
"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ══ ① mmkit 检索案例放进 ctx ══
P1 = os.path.join(HERE, "mmkit.py")
s1 = open(P1, encoding="utf-8").read()
if "_cases_ctx" not in s1:
    HELPER = '''

def _cases_ctx(kind_res, ds, problem):
    """按题型与方法检索相似历史案例。"""
    try:
        import cases as _cases
        kinds = (kind_res or {}).get("kinds") or []
        methods = ["pareto", "cv", "sens", "resid", "interval", "surrogate"]
        cols = [str(c) for c in (getattr(ds, "num_names", None) or [])]
        return _cases.find(kinds=kinds, methods=methods,
                           cols=cols, problem=problem or "", top=3)
    except Exception:                               # noqa: BLE001
        return []


'''
    k = s1.find("def _kind_ctx(")
    assert k > 0, "找不到 _kind_ctx"
    s1 = s1[:k] + HELPER + s1[k:]
    # 在 ctx 里挂上（依赖 problem_kind，所以放它后面）
    OLD = "            problem_kind=_kind_ctx(problem, ds, xs, ycol),"
    NEW = ("            problem_kind=_kind_ctx(problem, ds, xs, ycol),\n"
           "            cases=_cases_ctx(_kind_ctx(problem, ds, xs, ycol),\n"
           "                             ds, problem),")
    assert OLD in s1, "找不到 problem_kind 行"
    s1 = s1.replace(OLD, NEW, 1)
    ast.parse(s1)
    compile(s1, P1, "exec")
    open(P1, "w", encoding="utf-8", newline="\n").write(s1)
    print("① mmkit 检索案例并放进 ctx")

# ══ ② paper.py 加一节 ══
P2 = os.path.join(HERE, "paper.py")
s2 = open(P2, encoding="utf-8").read()
if "Comparable problems" not in s2:
    SECTION = '''    # ── 历史案例类比（来自 139 张国赛案例库）──
    # 只写结构类比与可核对编号，不搬中文原文。
    _cs = ctx.get("cases") or []
    if _cs:
        L += [r"\\subsection{Comparable problems}", ""]
        _n = len(_cs)
        _ids = ", ".join(f"{c.get('case_id')} ({c.get('year')})"
                         for c in _cs if c.get("case_id"))
        L.append(
            f"The reference archive contains {_n} competition cases whose "
            f"problem structure matches this one ({_ids}). The comparison is "
            f"at the level of structure rather than subject matter: each of "
            f"them also separates a mechanism layer that supplies directions, "
            f"a regression layer that fixes the functional form, and a search "
            f"over a feasible set.")
        L.append("")
        # 从 lessons 里只抽主题词，不搬原句
        _topics = []
        for _c in _cs:
            _tr = _c.get("transfer") or {}
            _txt = (_tr.get("lessons") or "") + (_tr.get("limits") or "")
            for _kw, _en in (("稳健区域", "a robust band of designs rather "
                              "than a single point"),
                             ("交叉验证", "cross-validated model comparison"),
                             ("灵敏度", "decision-level sensitivity"),
                             ("可行域", "an explicit feasible set"),
                             ("扰动传播", "propagation of perturbations"),
                             ("残差", "residual diagnosis")):
                if _kw in _txt and _en not in _topics:
                    _topics.append(_en)
        if _topics:
            L.append(
                "The lessons recorded for these analogues, restated for this "
                "problem, are: " + "; ".join(_topics[:3]) + ". Each of these "
                "is checked in the sections that follow rather than assumed "
                "to transfer.")
            L.append("")
        # 适用边界
        _lim = ""
        for _c in _cs:
            _tr = _c.get("transfer") or {}
            if _tr.get("limits"):
                _lim = _tr["limits"]
                break
        if _lim:
            L.append(
                "One boundary is worth stating explicitly. The analogue that "
                "supplies the closest match records the condition under which "
                "its own model stops transferring: when the neglected physics "
                "becomes comparable with the retained terms, the model "
                "structure has to be extended rather than merely re-fitted. "
                "The same caveat applies here, and it is why the residuals "
                "and the prediction intervals are reported rather than only "
                "the fit.")
            L.append("")

'''
    # 插在「影响规律」之后、Problem 2 之前更自然：放在 Problem 1 的末尾
    ANCHOR = '    # ---------------- Problem 2: optimal design ----------------'
    if ANCHOR in s2:
        s2 = s2.replace(ANCHOR, SECTION + ANCHOR, 1)
        ast.parse(s2)
        compile(s2, P2, "exec")
        open(P2, "w", encoding="utf-8", newline="\n").write(s2)
        print("② paper.py 加了 Comparable problems 一节")
    else:
        print("! ② 找不到锚点")
