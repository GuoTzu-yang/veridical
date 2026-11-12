#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
papercheck.py —— 论文完备性检查器（第 86 轮建）

它是什么
--------
一个**尺子**。给定一份 .tex，按数模评阅的硬要求逐项量：
摘要够不够长、有没有具体数字、每张图有没有配文字、代码在不在附录、
章节齐不齐、编号连不连续、有没有身份信息。

为什么先造尺子
--------------
「论文能不能交」是个模糊判断，不量化就会自欺。
先有检查器，后面每轮改动的效果才量得出来；
否则只能凭感觉说「更好了」，那和"够用就行"没区别。

检查项直接来自用户给的四模块要求，不是我自己编的。
"""
from __future__ import annotations

import os
import re

# 数模论文的九个必备章节（用户明确列出的）
REQUIRED_SECTIONS = [
    ("Summary", [r"\\begin\{abstract\}", r"\\section\*?\{Summary\}"]),
    ("Introduction", [r"\\section\*?\{Introduction\}"]),
    ("Assumptions and Notations",
     [r"\\section\*?\{Assumptions", r"\\section\*?\{Notation"]),
    # 结构改成「按小问组织」后这三节换了名字（Problem 1/2/3）。
    # 旧名保留作为兼容：不是每道题都会拆小问，单问时仍是旧结构。
    ("Sub-problem 1",
     [r"\\section\*?\{Problem~?1", r"\\section\*?\{Problem 1: ",
      r"\\section\*?\{Model Formulation\}"]),
    ("Sub-problem 2",
     [r"\\section\*?\{Problem~?2", r"\\section\*?\{Problem 2: ",
      r"\\section\*?\{Model Solution", r"\\section\*?\{Results"]),
    ("Sub-problem 3",
     [r"\\section\*?\{Problem~?3", r"\\section\*?\{Problem 3: ",
      r"\\section\*?\{Sensitivity"]),
    ("Evaluation", [r"\\section\*?\{Evaluation",
                    r"\\section\*?\{Model Evaluation"]),
    ("References", [r"thebibliography", r"\\bibliography\{"]),
    ("Appendix", [r"\\appendix", r"\\section\*?\{Appendix"]),
]

# 摘要里应当出现的「具体数字」形态
NUMBER_PATTERNS = [
    r"\d+\.\d+",                       # 小数
    r"\\?\d+(\.\d+)?\s*\\?%",          # 百分比
    r"R\^2",                           # 拟合优度
    r"RMSE",
]


def _strip_comments(tex: str) -> str:
    """去掉整行注释，避免把注释里的字当成正文。"""
    return "\n".join(l for l in tex.splitlines()
                     if not l.strip().startswith("%"))


def _abstract(tex: str) -> str:
    m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", tex, re.S)
    if m:
        return m.group(1)
    m = re.search(r"\\section\*?\{Summary\}(.*?)(?=\\section)", tex, re.S)
    return m.group(1) if m else ""


def _count_words(s: str) -> int:
    """数英文词数（去掉 LaTeX 命令后）。"""
    s = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^{}]*\})?", " ", s)
    s = re.sub(r"[{}$\\]", " ", s)
    return len(re.findall(r"[A-Za-z][A-Za-z\-']*", s))


def check(tex: str, figures_dir: str | None = None) -> dict:
    """逐项量。返回每项的状态与说明。"""
    body = _strip_comments(tex)
    items = []

    def add(name, ok, detail, level="硬"):
        items.append(dict(name=name, ok=bool(ok), detail=detail,
                          level=level))

    # ---- 1. 九个章节 ----
    missing = []
    for name, pats in REQUIRED_SECTIONS:
        if not any(re.search(p, body) for p in pats):
            missing.append(name)
    add("九个必备章节齐全", not missing,
        "全齐" if not missing else f"缺 {len(missing)} 个: " +
        "、".join(missing))

    # ---- 2. 摘要字数 300-500 ----
    ab = _abstract(body)
    wc = _count_words(ab)
    add("摘要 300-500 词", 300 <= wc <= 500,
        f"{wc} 词" + ("" if 300 <= wc <= 500
                      else f"（要求 300-500，差 {300 - wc if wc < 300 else wc - 500:+d}）"))

    # ---- 3. 摘要含具体数字 ----
    hits = [p for p in NUMBER_PATTERNS if re.search(p, ab)]
    add("摘要含具体数字", len(hits) >= 2,
        f"命中 {len(hits)} 类" + ("" if len(hits) >= 2
                                  else "（评委最先看摘要，必须有数）"))

    # ---- 4. 数学公式 ----
    n_eq = len(re.findall(r"\\begin\{(equation|align|gather)",
                          body))
    add("有数学公式环境", n_eq >= 3, f"{n_eq} 个（数模论文至少 3 个）")

    # ---- 5. 表格 ----
    n_tab = len(re.findall(r"\\begin\{(table|longtable)\}", body))
    add("有数据表格", n_tab >= 3, f"{n_tab} 个")

    # ---- 6. 图 ----
    figs = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", body)
    add("有图片引用", len(figs) >= 4, f"{len(figs)} 张")
    if figures_dir is not None:
        # 按 tex 所在目录解析相对路径 —— 论文里可能写 ../fig/box.png，
        # 只取 basename 会误报缺文件（A 题实测踩到）
        absent = [f for f in figs
                  if not os.path.exists(os.path.join(figures_dir, f))
                  and not os.path.exists(
                      os.path.join(figures_dir, os.path.basename(f)))]
        add("图片文件真实存在", not absent,
            "全部存在" if not absent else f"缺文件: {absent[:3]}")

    # ---- 7. 每张图配文字（用户强调「千万别只放图不说话」）----
    uncommented = []
    for m in re.finditer(r"\\end\{figure\}", body):
        tail = body[m.end():m.end() + 700]
        nxt = re.search(r"\\begin\{figure\}|\\section", tail)
        seg = tail[:nxt.start()] if nxt else tail
        prose = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^{}]*\})?", " ", seg)
        prose = re.sub(r"[{}$\\]", " ", prose)
        if len(re.findall(r"[A-Za-z][A-Za-z\-']{2,}", prose)) < 15:
            uncommented.append(len(uncommented) + 1)
    add("每张图都有文字分析", not uncommented,
        "都有" if not uncommented else
        f"{len(uncommented)} 张图后面没有分析文字")

    # ---- 8. 参考文献 ----
    n_bib = len(re.findall(r"\\bibitem", body))
    add("参考文献 ≥5 条", n_bib >= 5, f"{n_bib} 条")

    # ---- 9. 附录有代码 ----
    has_verb = bool(re.search(r"\\begin\{(verbatim|lstlisting|minted)\}", body))
    add("附录贴了代码", has_verb, "有 verbatim 环境" if has_verb else "没有代码块")

    # ---- 10. 匿名 ----
    id_hits = [x for x in ("大学", "学院", "University", "College",
                           "@qq.com", "@gmail.com", "@163.com")
               if x in tex]
    add("没有身份信息", not id_hits,
        "干净" if not id_hits else f"含 {id_hits}")

    # ---- 11. 页眉只有队号 ----
    m = re.search(r"\\fancyhead\[C\]\{([^}]*)\}", body)
    ok_head = bool(m) and "Team" in m.group(1) and not re.search(
        r"[A-Z][a-z]+ [A-Z][a-z]+", m.group(1))
    add("页眉只有队号", ok_head, m.group(1) if m else "没有页眉设置")

    # ---- 12. 敏感性别只提一句 ----
    sens = re.search(r"\\section\*?\{Sensitivity[^}]*\}(.*?)(?=\\section|"
                     r"\\appendix|\\end\{document\})", body, re.S)
    if sens:
        n_words = _count_words(sens.group(1))
        n_fig = len(re.findall(r"\\includegraphics", sens.group(1)))
        add("敏感性分析独立成章且有图", n_words >= 80 and n_fig >= 1,
            f"{n_words} 词 / {n_fig} 张图")
    else:
        add("敏感性分析独立成章且有图", False, "没有独立章节")

    # ---- 13. 没有未填的占位 ----
    n_todo = len(re.findall(r"\[TODO", tex))
    add("没有未填占位", n_todo == 0,
        "无" if n_todo == 0 else f"{n_todo} 处 [TODO]")

    # ---- 14. 编译结构 ----
    begins = re.findall(r"\\begin\{([^}]+)\}", body)
    ends = re.findall(r"\\end\{([^}]+)\}", body)
    from collections import Counter
    cb, ce = Counter(begins), Counter(ends)
    bad_env = [e for e in set(cb) | set(ce) if cb[e] != ce[e]]
    add("环境全部配对", not bad_env,
        "全部配对" if not bad_env else f"不配对: {bad_env}")

    hard = [i for i in items if i["level"] == "硬"]
    passed = sum(1 for i in hard if i["ok"])
    return dict(items=items, total=len(hard), passed=passed,
                failed=[i for i in hard if not i["ok"]],
                score=passed / len(hard) if hard else 0.0)


def report(r: dict) -> str:
    L = []
    L.append(f"论文完备性 {r['passed']}/{r['total']} "
             f"({r['score']:.0%})")
    L.append("-" * 62)
    for it in r["items"]:
        mark = "OK  " if it["ok"] else "缺  "
        L.append(f"  [{mark}] {it['name']:<24} {it['detail']}")
    return "\n".join(L)


if __name__ == "__main__":
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "out",
        "paper_apmcm.tex")
    if not os.path.exists(p):
        print(f"找不到 {p}")
        raise SystemExit(2)
    tex = open(p, encoding="utf-8").read()
    r = check(tex, figures_dir=os.path.dirname(os.path.abspath(p)))
    print(report(r))
    raise SystemExit(0 if not r["failed"] else 1)
