#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
abstract.py —— 摘要审查（第 15 轮，清单集成自 dsh-ultramath 的《摘要写作增强》）

它给的清单
----------
四要素占比：问题 10% / 方法 20% / **数值结果 50%** / 意义 20%
三段式：总起 10% / 逐题 70-80% / 收束 10-20%
八项硬性自检（▲必查）：可独立读懂、逐问对应、每问有量化结果、
              模型名具体、有验证、无模糊词、篇幅合理、无公式

这里把能自动化的七项写出来。第一项（可独立读懂）只能部分启发式判断 ——
我查的是「有没有依赖正文的指针」，不是真的读懂。

为什么需要它
------------
我们正文已经按小问组织（Problem 1/2/3），摘要却还是「按流程」讲：
问题分解 → 数据 → 选型 → 结果 → 稳健性。评委在摘要里找不到
「问题一的结果是什么」，只能往下翻。这是 35% 那一项的直接失分。

用法
    python abstract.py out/fig/paper.tex
    python abstract.py selftest
"""

from __future__ import annotations

import os
import re
import sys

# 模糊词：说了等于没说
# 只留**明确**的模糊词。
# very / quite / rather / fairly 是程度副词，正常行文也会用
# （"rather than" 是对的），把它们算成模糊会误伤。
VAGUE = (
    "good", "very good", "excellent", "significant improvement",
    "significantly better", "效果良好", "较为理想", "显著提升",
    "大概", "很好", "较好",
)

# 笼统的模型表述
VAGUE_MODEL = (
    "a model", "some model", "a certain model", "a suitable model",
    "建了个模型", "建立模型", "适当的模型",
)

# 验证信号
VERIFY = ("cross-validat", "validat", "verif", "residual", "rmse",
          "error analysis", "bootstrap", "hold-out", "holdout",
          "交叉验证", "残差", "误差", "检验")


def _clean(tex: str) -> str:
    """去掉注释和格式命令，留正文。"""
    s = re.sub(r"(?<!\\)%.*$", "", tex, flags=re.M)
    s = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", " ", s)
    return re.sub(r"[{}]", " ", s)


def _words(s: str) -> int:
    en = len(re.findall(r"[A-Za-z][A-Za-z'-]*", s))
    zh = len(re.findall(r"[\u4e00-\u9fff]", s))
    return en + zh


def extract(tex: str) -> str:
    r"""从 paper.tex 里取出摘要正文。

    认三种写法，顺序从最明确到最宽松：
      ① 名字里含 abstract 的环境 —— abstract / abstractbox / abstractenv …
         原来只认 `\begin{abstract}`，于是自定义环境（例如本仓库技术报告用的
         `abstractbox`）会被判成「没有摘要」，硬门直接 N/A 放行。
      ② `\section{Abstract}` / `\section*{摘要}`，取到下一个 \section 为止
      ③ `\section{Summary}`，同上（旧行为，保留）
    """
    m = re.search(r"\\begin\{(\w*abstract\w*)\}(.*?)\\end\{\1\}", tex, re.S)
    if m:
        return m.group(2).strip()
    for pat in (r"\\section\*?\{\s*(?:Abstract|摘要)\s*\}",
                r"\\section\*?\{\s*Summary\s*\}"):
        m = re.search(pat + r"(.*?)(?=\\section)", tex, re.S)
        if m:
            return m.group(1).strip()
    return ""


def audit(tex: str) -> dict:
    ab = extract(tex)
    if not ab:
        return dict(ok=False, why="没有摘要（abstract 或 Summary 节）",
                    items=[], n_words=0)
    body = _clean(ab)
    low = body.lower()
    items = []

    def add(name, ok, detail, weight):
        items.append(dict(name=name, ok=ok, detail=detail, weight=weight))

    # ① 可独立读懂（启发式：不能出现「见正文」这类指针）
    ptr = re.search(r"see (section|the appendix|below)|as shown in "
                    r"section|详见|见正文", low)
    add("可独立读懂", not ptr,
        "有指向正文的引路" if ptr else "无依赖正文的指针", 3)

    # ② 逐问一一对应
    # 原来只数「锚点出现次数 >= 2」——写「Problem 4 / Problem 5」也能过，
    # 而 1..3 一个没提。改成要求锚点编号**从 1 起连续**：
    # 摘要按小问组织，就该把小问一个不落地提到。
    # 实测 23 道模板题 + 本仓库技术报告的锚点集合都是 [1..N] 连续，
    # 收紧这一条不会误伤既有论文。
    _CN = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
           "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    _nums = []
    for m in re.finditer(r"problem\s*([1-9])", low):
        _nums.append(int(m.group(1)))
    for m in re.finditer(r"问题\s*([一二三四五六七八九十1-9])", low):
        g = m.group(1)
        _nums.append(_CN.get(g) or int(g))
    anchors = _nums
    _uniq = sorted(set(_nums))
    _gap = [i for i in range(1, (_uniq[-1] + 1) if _uniq else 1)
            if i not in _uniq]
    add("逐问一一对应",
        bool(_uniq) and not _gap and _uniq[0] == 1 and len(_uniq) >= 2,
        (f"{len(_uniq)} 个问题锚点 {_uniq}" if _uniq and not _gap
         else (f"锚点 {_uniq} 缺第 {_gap} 问" if _gap
               else "没有按小问组织")), 3)

    # ③ 每问有量化结果：按锚点切段，每段要有数
    if anchors:
        parts = re.split(r"(?:problem\s*[1-9]|问题\s*[一二三四五六七八九十1-9])",
                         low)
        segs = [p for p in parts[1:] if _words(p) > 10]
        nonum = [i + 1 for i, p in enumerate(segs)
                 if not re.search(r"\d+\.?\d*", p)]
        add("每问有量化结果", not nonum,
            f"第 {nonum} 段没有数值" if nonum else f"{len(segs)} 段都有数", 3)
    else:
        # 没锚点时退化为「整体有数」
        has = bool(re.search(r"\d+\.\d+|\d+\s*%", low))
        add("每问有量化结果", has, "有数值但没按问分" if has else "没有数值", 3)

    # ④ 模型名具体
    # 用词边界匹配，不用 `w in low`：子串匹配会把
    # "a modelling team" 判成笼统表述 "a model" —— 实测本仓库的技术报告
    # 摘要就因这句话被扣分（73.7 分里有一项是这么丢的）。
    def _phrase_hit(w):
        if w.isascii():
            return re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", low)
        return w in low

    vm = [w for w in VAGUE_MODEL if _phrase_hit(w)]
    add("模型名具体", not vm, f"笼统表述 {vm[:2]}" if vm else "无笼统表述", 2)

    # ⑤ 有验证
    vh = [w for w in VERIFY if w in low]
    add("有验证", bool(vh), f"验证信号 {vh[:3]}" if vh else "没提检验", 2)

    # ⑥ 无模糊词
    vg = [w for w in VAGUE if re.search(rf"\b{re.escape(w)}\b", low)
          or (not w.isascii() and w in low)]
    add("无模糊词", not vg, f"模糊词 {vg[:3]}" if vg else "无模糊词", 2)

    # ⑦ 篇幅
    n = _words(body)
    add("篇幅合理", 200 <= n <= 600,
        f"{n} 词" + ("" if 200 <= n <= 600 else "（应 200-600）"), 2)

    # ⑧ 无公式（抽象里不该出现推导）
    eq = re.search(r"\\begin\{(equation|align|gather)\}|\\\[", ab)
    heavy = re.findall(r"\$[^$]{20,}\$", ab)   # 长的行内公式也算
    add("无公式", not eq and not heavy,
        "含公式环境" if eq else (f"{len(heavy)} 个长公式" if heavy
                                 else "无公式"), 2)

    got = sum(i["weight"] for i in items if i["ok"])
    total = sum(i["weight"] for i in items)
    return dict(ok=got == total, items=items, n_words=n,
                score=round(100 * got / total, 1) if total else 0,
                anchors=len(anchors))


def report(r: dict) -> str:
    if not r.get("items"):
        return f"  {r.get('why')}"
    L = [f"摘要审查：{r['score']}/100"
         f"（{r['n_words']} 词，{r['anchors']} 处问题锚点）"
         + ("" if r["ok"] else "  —— 有失分项"), ""]
    for i in r["items"]:
        L.append(f"  [{'OK  ' if i['ok'] else 'FAIL'}] {i['name']:<12}"
                 f"{i['detail']}")
    return "\n".join(L)


# ══════════════════════════════════════════════════════════════════════
def selftest() -> int:
    bad = 0
    n = 0

    def ck(name, cond, detail=""):
        nonlocal bad, n
        n += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
              + (f"  — {detail}" if detail else ""))
        if not cond:
            bad += 1

    good = r"""\begin{abstract}
Problem 1 asks how the geometry governs thermal resistance. A multiple
linear regression on 84 observations attains a cross-validated RMSE of
0.00743, and the Breusch--Pagan statistic of 7.27 sits below the 5 percent
critical value of 7.81.

Problem 2 turns the fitted relation into a constrained design problem. The
Pareto front over thermal resistance and pressure drop holds 9 of the 84
designs, and the best compromise reduces resistance by 18.3 percent relative
to the sample mean.

Problem 3 tests whether those conclusions survive perturbation. Re-estimating
under logarithmic and square-root responses leaves all 3 predictors with the
same sign, so the directions of association are stable. The same procedure is
repeated with a square-root response and with a rank transform, and in both
cases the signs are unchanged, which is what the stability claim rests on.
Every number reported in these three paragraphs appears in the tables of the
body, and each is reproduced by the scripts listed in the appendix, so a
reader who distrusts the summary can check it line by line without rereading
the derivation. The dataset contains eighty-four usable observations after
rows with missing values in the retained columns were removed explicitly, and
that count is stated here explicitly rather than left to be inferred from
the tables, which is the only honest way to let a reader judge whether the
sample is large enough for the claims that follow.
\end{abstract}"""
    r = audit(good)
    ck("好摘要通过", r["ok"], f"{r['score']}/100，{r['items'] and ''}")
    ck("识别出 3 处问题锚点", r["anchors"] >= 3, str(r["anchors"]))
    ck("每问都有数值", any(i["name"] == "每问有量化结果" and i["ok"]
                       for i in r["items"]))
    ck("篇幅在范围内", 200 <= r["n_words"] <= 600, f"{r['n_words']} 词")

    # 没按小问组织
    bad1 = r"""\begin{abstract}
This report develops a model for the problem and proceeds through data
preparation, model selection and validation. The selected structure attains
a cross-validated RMSE of 0.00743 on 84 observations, which is good.
\end{abstract}"""
    r2 = audit(bad1)
    ck("没锚点被抓出", not any(i["name"] == "逐问一一对应" and i["ok"]
                          for i in r2["items"]))
    ck("模糊词被抓出", not any(i["name"] == "无模糊词" and i["ok"]
                          for i in r2["items"]),
       str([i["detail"] for i in r2["items"] if i["name"] == "无模糊词"]))

    # 笼统模型名
    r3 = audit(r"""\begin{abstract}
Problem 1 asks a question. We build a model and obtain a result of 0.5 after
cross-validation on 84 rows. Problem 2 extends it and gives 3 outcomes.
\end{abstract}""")
    ck("笼统模型名被抓出", not any(i["name"] == "模型名具体" and i["ok"]
                            for i in r3["items"]),
       str([i["detail"] for i in r3["items"] if i["name"] == "模型名具体"]))

    # 含公式
    r4 = audit(r"""\begin{abstract}
Problem 1 uses a regression. \begin{equation} y = \beta_0 + \beta_1 x
\end{equation} The RMSE is 0.007 on 84 rows. Problem 2 gives 9 points.
\end{abstract}""")
    ck("公式被抓出", not any(i["name"] == "无公式" and i["ok"]
                         for i in r4["items"]))

    # 没有摘要
    ck("没有摘要时返回 why", "why" in audit("no abstract here"))

    # ── 第 89 轮补：识别形式与假阳性 ────────────────────────────────
    body = "Problem 1 asks this, and Problem 2 asks that."
    for label, src in (
            ("环境 abstract", "\\begin{abstract}" + body + "\\end{abstract}"),
            ("环境 abstractbox",
             "\\begin{abstractbox}" + body + "\\end{abstractbox}"),
            ("节 Abstract", "\\section*{Abstract}\n" + body + "\n\\section{X}"),
            ("节 摘要", "\\section{摘要}\n" + body + "\n\\section{X}")):
        ck("认得出「%s」" % label, extract(src).strip() == body,
           repr(extract(src))[:40])
    ck("仍然认不出真正的无摘要", extract("no abstract here") == "")

    # 子串假阳性：「a modelling team」不该被当成笼统表述「a model」
    fake = ("\\begin{abstract}" + body + " A modelling team measures cost. "
            "Problem 3 asks more. 0.42 and 0.77 are numbers."
            "\\end{abstract}")
    rf = audit(fake)
    item = [i for i in rf["items"] if i["name"] == "模型名具体"][0]
    ck("「a modelling」不算笼统表述「a model」", item["ok"], item["detail"])
    # 但真的写了「a model」要抓得到
    real_vague = "\\begin{abstract}" + body + " We build a model for it." \
                 " Problem 3 asks more. 0.42 and 0.77." \
                 "\\end{abstract}"
    rv = audit(real_vague)
    item2 = [i for i in rv["items"] if i["name"] == "模型名具体"][0]
    ck("真写了「a model」仍被抓出", not item2["ok"], item2["detail"])

    # 逐问锚点必须从 1 起连续（只数次数会让「Problem 4/5」蒙混过关）
    def _anchor_ok(body):
        r = audit("\\begin{abstract}" + body + "\\end{abstract}")
        return [i for i in r["items"] if i["name"] == "逐问一一对应"][0]

    a1 = _anchor_ok("Problem 1 asks a. Problem 2 asks b. 0.42 and 0.77 here.")
    ck("锚点 1..2 连续 → 过", a1["ok"], a1["detail"])
    a2 = _anchor_ok("Problem 4 asks a. Problem 5 asks b. 0.42 and 0.77 here.")
    ck("只提 Problem 4/5 → 未过", not a2["ok"], a2["detail"])
    a3 = _anchor_ok("Problem 1 asks a. Problem 3 asks b. 0.42 and 0.77 here.")
    ck("提 1/3 缺 2 → 未过", not a3["ok"], a3["detail"])

    # 真实论文
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "out", "fig", "paper.tex")
    if os.path.exists(p):
        real = audit(open(p, encoding="utf-8").read())
        ck("真实论文能审", "items" in real and len(real["items"]) >= 7,
           f"{real.get('score')}/100，{real.get('n_words')} 词")

    print(f"\n{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="摘要审查")
    ap.add_argument("tex", nargs="?", default="")
    a = ap.parse_args(argv)
    if not a.tex or a.tex == "selftest":
        return selftest()
    if not os.path.exists(a.tex):
        print(f"  没有 {a.tex}")
        return 2
    r = audit(open(a.tex, encoding="utf-8").read())
    print(report(r))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
