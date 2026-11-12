#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rules_apmcm.py —— APMCM（亚太地区大学生数学建模竞赛）专用规则检查。

为什么单独一套
--------------
rules.py 是按 MCM/ICM 的评审习惯写的。APMCM 的评审口径写在官方章程里，
与 MCM 不同，最关键的三条：

  章程第八条（二）：
    参赛者提交的作品应为一篇包括**模型假设、模型建立、模型求解、模型改进
    以及结果分析与检验**等内容的论文。作品评审的标准主要为
    **模型及其假设与结果的合理性、创造性、文字表述的规范性**。

  章程第十二条：
    竞赛论文若引用其他文献、图片、图表、数据应给予**明确说明**。

  章程第八条（一）：题目一般来源于工程与管理、图象图形、计算机等领域。

所以本文件把上面三条拆成 7 条可自动判定的检查（A001-A007）。
每条都能在论文里找到**结构痕迹**，而不是靠某几个固定词。

与 rules.py 的关系：两套并存，用 --scheme 选择，默认 mcm（保持既有回归不变）。

用法
    python rules_apmcm.py paper.tex
    python rules_apmcm.py paper.tex --json
    python rules_apmcm.py selftest
"""

from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _norm(tex: str) -> str:
    return tex.lower()


def _has(low: str, raw: str, kws):
    return [k for k in kws if k in low or k in raw]


# ══════════════════════════════════════════════════════════════════════
#  A001 模型建立与求解（章程第八条：模型建立的合理性）
# ══════════════════════════════════════════════════════════════════════
def _a001(t):
    """要有「建立模型」与「求解模型」两件事，不只是结果。"""
    low = _norm(t)
    build = _has(low, t, (
        "we model", "we formulate", "the model is", "model formulation",
        "formulation", "we construct", "we define the model",
        "our model", "model establishment", "模型建立", "建立模型", "建模"))
    solve = _has(low, t, (
        "we solve", "the solution", "solved by", "solving", "we compute",
        "computed by", "numerically", "we obtain", "optimization",
        "模型求解", "求解", "求解模型"))
    if not build:
        return False, "没找到「建立模型」的痕迹"
    if not solve:
        return False, "没找到「求解模型」的痕迹"
    return True, "建立 %s / 求解 %s" % (build[:2], solve[:2])


# ══════════════════════════════════════════════════════════════════════
#  A002 模型假设（章程第八条：假设的合理性）
# ══════════════════════════════════════════════════════════════════════
def _a002(t):
    """假设要显式列出，而且要给出理由 —— 只有结论没有理由的假设不算合理。"""
    low = _norm(t)
    has_sec = bool(re.search(r"\\(sub)?section\*?\{[^}]*assumption", low)) \
        or "assumptions" in low or "模型假设" in t
    if not has_sec:
        return False, "没有显式的假设小节（Assumptions / 模型假设）"
    reasons = _has(low, t, (
        "because", "since", "we assume", "justified", "motivated by",
        "reasonable to assume", "it is natural", "we may assume",
        "理由", "因为", "由于", "假设是合理的"))
    if not reasons:
        return False, "有假设但没给理由（合理性无从判断）"
    return True, "有假设小节，理由信号 %s" % reasons[:2]


# ══════════════════════════════════════════════════════════════════════
#  A003 结果分析与检验（章程第八条：结果的合理性）
# ══════════════════════════════════════════════════════════════════════
def _a003(t):
    """结果要有检验，不是光报数。至少覆盖两类不同的检验。"""
    low = _norm(t)
    groups = {
        "误差/残差": ("residual", "rmse", "standard error", "error analysis",
                   "残差", "误差"),
        "交叉验证/样本外": ("cross-validation", "cross validation", "held out",
                      "out-of-sample", "leave-one-out", "交叉验证", "留一"),
        "敏感性": ("sensitivity", "sensitivit", "敏感"),
        "稳健性": ("robust", "perturbation", "稳健"),
        "一致性/区间": ("confidence interval", "interval", "bootstrap",
                   "一致性检验", "置信区间"),
    }
    hit = [k for k, kws in groups.items()
           if any(w in low or w in t for w in kws)]
    if len(hit) < 2:
        return False, ("结果检验只有 %d 类（%s），至少要两类"
                       % (len(hit), "、".join(hit) or "无"))
    return True, "结果检验覆盖 %s" % "、".join(hit)


# ══════════════════════════════════════════════════════════════════════
#  A004 创造性（章程第八条：创造性）
# ══════════════════════════════════════════════════════════════════════
def _a004(t):
    """要有可辨认的差异化主张 —— 不是「我们做了什么」，而是「和常规做法不同在哪」。"""
    low = _norm(t)
    contrast = _has(low, t, (
        "unlike", "in contrast", "differs from", "distinct from",
        "rather than", "as opposed to", "our approach differs",
        "与常规", "不同于", "而不是"))
    contribution = _has(low, t, (
        "we propose", "we introduce", "our contribution", "the contribution",
        "we show that", "novel", "contribution of this",
        "我们提出", "本文的贡献"))
    if not contrast and not contribution:
        return False, "没有可辨认的差异化/贡献主张"
    return True, "差异化 %s / 贡献 %s" % (contrast[:2] or ["-"], contribution[:2] or ["-"])


# ══════════════════════════════════════════════════════════════════════
#  A005 文字表述的规范性（章程第八条：文字表述的规范性）
# ══════════════════════════════════════════════════════════════════════
def _a005(t):
    """摘要、关键词、图注、标签齐备。"""
    problems = []
    if not re.search(r"\\begin\{abstract\}", t, re.I):
        problems.append("缺摘要环境")
    if not re.search(r"\\textbf\{keywords?\}|\\keyword\{|keywords?:", t, re.I):
        problems.append("缺关键词")
    n_fig = len(re.findall(r"\\begin\{figure\}", t))
    n_cap = len(re.findall(r"\\caption\{", t))
    n_tab = len(re.findall(r"\\begin\{table\}", t))
    n_cap2 = len(re.findall(r"\\caption\{", t))
    if n_fig and n_cap2 < n_fig:
        problems.append("%d 张图但只有 %d 个 caption" % (n_fig, n_cap2))
    if n_tab and n_cap2 < n_fig + n_tab:
        problems.append("%d 图 + %d 表但只有 %d 个 caption" % (n_fig, n_tab, n_cap2))
    if problems:
        return False, "；".join(problems)
    return True, ("摘要+关键词齐备，%d 图 %d 表，caption %d"
                  % (n_fig, n_tab, n_cap2))


# ══════════════════════════════════════════════════════════════════════
#  A006 引用/图片/图表/数据的明确说明（章程第十二条）
# ══════════════════════════════════════════════════════════════════════
def _a006(t):
    """第十二条：引用其他文献、图片、图表、数据要「给予明确说明」。"""
    low = _norm(t)
    # 逐个 caption 检查是否交代了来源
    caps = re.findall(r"\\caption\{(.*?)\}\s*\n", t, re.S)
    src_kw = ("data:", "data are", "source:", "sourced from", "adapted from",
              "taken from", "our own", "we computed", "computed from",
              "reproduced from", "derived from", "数据来源", "改自")
    with_src = [c for c in caps
                if any(k in c.lower() for k in src_kw)]
    global_src = _has(low, t, (
        "all data are from", "data were provided", "data provided by",
        "the data set used", "the dataset used", "we use the data",
        "数据由", "数据集来自", "所用数据"))
    if with_src or global_src:
        return True, ("图注交代来源 %d 处 / 全文说明 %s"
                      % (len(with_src), global_src[:2] or ["-"]))
    return False, ("第十二条要求对引用的文献/图片/图表/数据给予明确说明，"
                   "但既没在图注里交代来源，也没在正文说明数据出处")


# ══════════════════════════════════════════════════════════════════════
#  A007 模型改进与结论（章程第八条：模型改进）
# ══════════════════════════════════════════════════════════════════════
def _a007(t):
    """要有「改进/局限/后续」与明确的结论段。"""
    low = _norm(t)
    improve = _has(low, t, (
        "limitation", "we improve", "improvement", "future work",
        "further work", "extension of this", "局限", "改进", "后续",
        "下一步"))
    concl = _has(low, t, (
        "\\section{conclusion", "\\section*{conclusion", "we conclude",
        "in conclusion", "conclusions", "结论", "小结"))
    if not improve:
        return False, "缺「模型改进/局限」内容（章程要求含模型改进）"
    if not concl:
        return False, "缺结论段"
    return True, "改进/局限 %s / 结论 %s" % (improve[:2], concl[:2])


# ══════════════════════════════════════════════════════════════════════
#  A008 格式：摘要后必须有 Keywords
# ══════════════════════════════════════════════════════════════════════
def _a008(t):
    """APMCM 论文摘要后应有 Keywords 段。

    这一条是**元规则**：gate 原本用「有没有 Keywords」来判断一篇论文是不是
    APMCM 格式，没有就整块跳过检查。于是漏写 Keywords 会导致所有 A00x 静默
    N/A —— 假绿。把它本身变成一条规则，这个洞才补上。
    """
    m = re.search(r"\\textbf\{keywords?\}|\\keyword\{|keywords?\s*:",
                  t, re.I)
    if not m:
        return False, "摘要后缺 Keywords（APMCM 格式要求；缺失会让整块检查被跳过）"
    return True, "有 Keywords"


RULES = [
    ("A001", "模型建立与求解", _a001),
    ("A002", "模型假设与理由", _a002),
    ("A003", "结果分析与检验", _a003),
    ("A004", "创造性主张", _a004),
    ("A005", "文字表述规范性", _a005),
    ("A006", "文献/图表/数据来源说明", _a006),
    ("A007", "模型改进与结论", _a007),
    ("A008", "摘要后 Keywords", _a008),
]

MANUAL = [
    ("A-M1", "模型及其假设与结果的合理性（人工）",
     "章程第八条的评审核心，自动检查只能看结构痕迹；"
     "假设是否站得住、结果是否可信要人看"),
    ("A-M2", "创造性（人工）",
     "自动检查只能确认「写了差异化主张」，主张是否真的新要靠文献对照"),
]


def check(tex: str) -> dict:
    results = []
    for rid, name, fn in RULES:
        try:
            ok, detail = fn(tex)
        except Exception as e:                      # noqa: BLE001
            ok, detail = False, f"检查器异常：{type(e).__name__}: {e}"
        results.append(dict(id=rid, name=name, ok=ok, detail=detail))
    passed = sum(1 for r in results if r["ok"])
    return dict(results=results, passed=passed, total=len(results),
                manual=MANUAL, ok=passed == len(results))


def report(r: dict) -> str:
    L = [f"APMCM 规则检查：{r['passed']}/{r['total']} 通过", ""]
    for x in r["results"]:
        L.append(f"  [{'PASS' if x['ok'] else 'FAIL'}] {x['id']} {x['name']}")
        if x["detail"]:
            L.append(f"         {x['detail']}")
    if r["manual"]:
        L.append("")
        L.append("  需人工判断（章程口径，自动检查覆盖不了）：")
        for rid, name, why in r["manual"]:
            L.append(f"  [人工] {rid} {name}")
            L.append(f"         {why}")
    return "\n".join(L)


def selftest() -> int:
    ok = True

    def ck(name, cond, detail=""):
        nonlocal ok
        ok = ok and cond
        print("  [%s] %s %s" % ("PASS" if cond else "FAIL", name, detail))

    good = r"""
\begin{abstract}We reconstruct the fan vote by constraint inversion.\end{abstract}
\textbf{Keywords} modeling; inversion
\section{Model establishment}
We model the week by a polytope and formulate the constraints explicitly.
We solve the resulting program numerically and we obtain a feasible set.
\section{Assumptions}
We assume the eliminated contestant had the lowest combined score, because the
show resolves eliminations that way.
\section{Results and checking}
Residual analysis and cross-validation of the fitted model. We also report a
sensitivity analysis and the robustness of the conclusions.
\section{Creativity}
In contrast to the usual practice of fitting a vote-share regression, we propose
a constraint inversion, which differs from the standard approach.
\section{Figures}
\begin{figure}\includegraphics[width=0.8\textwidth]{a.png}
\caption{Weekly feasible range. Data: our computation from the official file.}\end{figure}
\section{Conclusion and improvement}
We conclude that the reconstruction is consistent with most eliminations.
Limitations and future work are discussed.
"""
    r = check(good)
    ck("合格论文全过", r["ok"], "%d/%d" % (r["passed"], r["total"]))

    no_assume = good.replace(r"\section{Assumptions}", r"\section{Setup}")
    r = check(no_assume)
    ck("缺假设 -> A002 失败", not [x for x in r["results"] if x["id"] == "A002"][0]["ok"])

    no_src = good.replace(" Data: our computation from the official file.", "")
    r = check(no_src)
    ck("缺来源说明 -> A006 失败", not [x for x in r["results"] if x["id"] == "A006"][0]["ok"])

    empty = r"\documentclass{article}\begin{document}\end{document}"
    r = check(empty)
    ck("空文档至少 A001/A003 失败",
       not [x for x in r["results"] if x["id"] == "A001"][0]["ok"]
       and not [x for x in r["results"] if x["id"] == "A003"][0]["ok"])

    print("\n%s" % ("ALL PASS" if ok else "FAILED"))
    return 0 if ok else 1


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] == "selftest":
        return selftest()
    as_json = "--json" in argv
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    tex = open(args[0], encoding="utf-8").read()
    r = check(tex)
    if as_json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(report(r))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
