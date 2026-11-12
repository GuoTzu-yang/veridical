#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aitaste.py —— AI 味检测（第 9 轮，思路集成自 dsh-ultramath 的 check_ai_taste.py）

取自它的
--------
五个维度与扣分权重（原样保留）：
    1. AI 高频词        每次 5 分
    2. 模板化连接词      每次 3 分
    3. 问题罗列         超过 3 次，每次 10 分
    4. 句式重复（前 5 字） 重复 ≥3 次，每次 5 分
    5. 段落长度标准差    过小扣 30 分（AI 段落太均匀）
上限 100，<20 优秀 / <50 一般 / 否则较差。

丢掉的糟粕
----------
**它只支持中文**。18 个词全是「值得注意的是」「综上所述」这类，
对英文论文完全无效 —— 而我们的论文是英文。
另外它用**字符数**量段落长度，英文该用**词数**（英文词长差异大，字符数会失真）。

补上的
------
- 英文 AI 味词表（13 个高频套话 + 8 个模板连接词）
- 段落长度按词数
- .tex 预处理：剥掉 LaTeX 命令和注释，只留正文
- 数学环境里的词不算（`\\begin{equation}` 里的内容跳过）

用法
    python aitaste.py out/fig/paper.tex
    python aitaste.py --dir out/fig
    python aitaste.py selftest
"""

from __future__ import annotations

import os
import re
import sys
from collections import Counter

# ══════════════════════════════════════════════════════════════════════
#  词表
# ══════════════════════════════════════════════════════════════════════
# AI 高频套话 —— 英文对应物 + 原版中文（双语，因为可能写中文论文）
AI_PHRASES = [
    # 英文
    "it is worth noting", "it should be noted", "it is important to note",
    "in conclusion", "to sum up", "in summary",
    "plays a crucial role", "plays a vital role", "plays an important role",
    "this paper proposes a novel", "we propose a novel",
    "with the development of", "with the rapid development",
    "in today's society", "in modern society",
    "it can be seen that", "it is obvious that", "obviously",
    "as we all know", "as is well known",
    "of great significance", "significant importance",
    "provides strong support", "provides a strong foundation",
    "broad application prospects", "has broad prospects",
    "sheds light on", "paves the way for",
    # 中文
    "值得注意的是", "综上所述", "在当今社会", "随着科技的发展",
    "随着社会的进步", "具有重要意义", "发挥着重要作用",
    "取得了显著成效", "提供了有力支撑", "具有广阔的应用前景",
    "为了解决这一问题", "通过以上分析可以看出", "总而言之",
    "由此可见", "不难发现", "显而易见", "众所周知",
]

TEMPLATE_PHRASES = [
    # 英文
    "firstly", "secondly", "thirdly", "lastly",
    "first of all", "in the first place",
    "on the one hand", "on the other hand",
    # 中文
    "本文首先", "然后", "最后",
    "针对问题一", "针对问题二", "针对问题三",
    "针对问题四", "针对问题五",
]

PROBLEM_LIST = re.compile(
    r"(?:针对问题[一二三四五六七八九十\d]|for problem\s*\d|"
    r"in problem\s*\d|problem\s*\d\s*[:：])", re.I)


# ══════════════════════════════════════════════════════════════════════
#  预处理
# ══════════════════════════════════════════════════════════════════════
def strip_tex(tex: str) -> str:
    """剥掉 LaTeX 命令、数学环境和注释，只留正文。

    为什么不直接搜原文：`\\section{Model}` 里的 "Model" 会干扰句式统计，
    公式里的符号也不是文字。原脚本没做这一步 —— 它搜的是 .tex 原文，
    所以统计里混进了大量命令名。
    """
    s = tex
    # 注释（整行 % 开头，或行内未转义的 %）
    s = re.sub(r"(?<!\\)%.*$", "", s, flags=re.M)
    # 数学环境整体去掉
    for env in ("equation", "equation*", "align", "align*", "gather",
                "gather*", "eqnarray", "displaymath"):
        s = re.sub(rf"\\begin\{{{re.escape(env)}\}}.*?"
                   rf"\\end\{{{re.escape(env)}\}}", " ", s, flags=re.S)
    s = re.sub(r"\$\$.*?\$\$", " ", s, flags=re.S)
    s = re.sub(r"\$[^$]*\$", " ", s)
    # 命令本身去掉，保留花括号里的文字
    s = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", " ", s)
    s = re.sub(r"[{}]", " ", s)
    return s


def _words(s: str) -> int:
    """英文按词数，中文按字数。"""
    en = len(re.findall(r"[A-Za-z][A-Za-z'-]*", s))
    zh = len(re.findall(r"[\u4e00-\u9fff]", s))
    return en + zh


# ══════════════════════════════════════════════════════════════════════
#  五个维度
# ══════════════════════════════════════════════════════════════════════
def check_ai_phrases(t: str) -> dict:
    low = t.lower()
    found = []
    for p in AI_PHRASES:
        c = low.count(p.lower())
        if c:
            found.append(dict(phrase=p, count=c))
    total = sum(f["count"] for f in found)
    return dict(name="AI 高频套话", found=found, total=total,
                score=min(100, total * 5))


def check_template(t: str) -> dict:
    low = t.lower()
    found = []
    for p in TEMPLATE_PHRASES:
        c = low.count(p.lower())
        if c:
            found.append(dict(phrase=p, count=c))
    total = sum(f["count"] for f in found)
    return dict(name="模板化连接词", found=found, total=total,
                score=min(100, total * 3))


def check_problem_list(t: str) -> dict:
    # 先剥掉章节标题再查。
    # 「Problem 1:」出现在 \section{} 里是**结构**，不是套话 ——
    # CUMCM 评委按「逐问一一对应」检查，标题本来就该这么写；
    # 而 abstract.py 还专门要求五处问题锚点。
    # 实测：整份 tex 有 5 处 Problem N:，正文里 0 处，全在标题。
    # 不剥标题的话这一项白扣 30 分，把真问题淹掉了。
    body = re.sub(r"\\(?:section|subsection|subsubsection)\*?\{[^}]*\}",
                  " ", t)
    m = PROBLEM_LIST.findall(body)
    n = len(m)
    return dict(name="问题罗列", found=[dict(phrase=x, count=1) for x in m],
                total=n, score=min(100, max(0, (n - 3) * 10)))


def check_repetition(t: str) -> dict:
    """句式重复：每句开头 4 个词相同就算同一个句式。

    英文用词不用字符 —— 原脚本用 s[:5] 取 5 个字符，
    对英文来说 "The m"/"The r" 这种半截词毫无意义。
    """
    sents = [s.strip() for s in re.split(r"[.。!！?？\n]", t)
             if _words(s) >= 6]
    if len(sents) < 5:
        return dict(name="句式重复", found=[], total=0, score=0)
    starts = []
    for s in sents:
        ws = re.findall(r"[A-Za-z][A-Za-z'-]*|[\u4e00-\u9fff]", s)
        starts.append(" ".join(ws[:4]).lower() if len(ws) >= 4 else "")
    c = Counter(x for x in starts if x)
    rep = {k: v for k, v in c.items() if v >= 3}
    return dict(name="句式重复",
                found=[dict(phrase=k, count=v) for k, v in rep.items()],
                total=sum(rep.values()),
                score=min(100, sum(v - 2 for v in rep.values()) * 5))


def check_paragraphs(t: str) -> dict:
    """段落长度分布。标准差过小 = 段落太均匀 = AI 特征。"""
    paras = [p.strip() for p in re.split(r"\n\s*\n", t)
             if _words(p) >= 20]
    if len(paras) < 3:
        return dict(name="段落长度", found=[], total=0, score=0,
                    note=f"有效段落仅 {len(paras)} 个")
    lens = [_words(p) for p in paras]
    mean = sum(lens) / len(lens)
    var = sum((x - mean) ** 2 for x in lens) / len(lens)
    std = var ** 0.5
    if std < 12:                       # 英文词数，阈值比原脚本的 50 字符小
        return dict(name="段落长度",
                    found=[dict(phrase=f"段落长度标准差={std:.0f} 词（过小）",
                                count=1)],
                    total=1, score=30, std=round(std, 1))
    return dict(name="段落长度", found=[], total=0, score=0,
                std=round(std, 1))


# ══════════════════════════════════════════════════════════════════════


# ══ writing-guard 的 42 条规则（提取自 dsh-plugin-writing-guard 2.0.1）══
_WG = {"rules": None}
_WG_SEV = {"high": 8, "medium": 4, "low": 2}
_WG_CN = {
    "claim_calibration": "声称与证据距离",
    "rhetorical_pattern": "修辞套路",
    "llm_associated": "大模型高频词",
    "academic_style": "学术文风",
    "process_residue": "修改过程残留",
    "formatting": "排版习惯",
}


def _wg_rules():
    if _WG["rules"] is None:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "kb", "ai_rules.json")
        try:
            import json
            _WG["rules"] = json.load(open(p, encoding="utf-8"))["rules"]
        except Exception:                       # noqa: BLE001
            _WG["rules"] = []
    return _WG["rules"]


def check_wg_rules(t: str) -> dict:
    """按 writing-guard 的规则查，按 category 汇总。"""
    rules = _wg_rules()
    if not rules:
        return dict(name="细分规则", found=[], total=0, score=0,
                    by_cat={})
    by_cat, found, score = {}, [], 0
    for r in rules:
        if r.get("disabled"):
            continue
        try:
            cre = re.compile(r["regex"])
        except re.error:
            continue
        ms = cre.findall(t)
        if not ms:
            continue
        # 否定语境不算强主张。
        # 实测 claim-evidence-proximity 的两处命中分别是
        # "these checks **do not** prove" 和 "where that guarantee stops"，
        # 两条都是诚实表达，规则只看关键词就会把它们当缺陷。
        _wl = [str(x).lower() for x in (r.get("technical_whitelist") or [])]
        if _wl:
            ms = [m for m in ms if str(m).lower() not in _wl]
            if not ms:
                continue
        if r.get("negation_guard"):
            _NEG = ("not ", "cannot ", "never ", "no ", "none ",
                    "does not", "do not", "did not", "fail to",
                    "cannot be", "not a ")
            _kept = 0
            for m in cre.finditer(t):
                pre = t[max(0, m.start() - 40):m.start()].lower()
                if any(w in pre for w in _NEG):
                    continue
                if any(w in pre for w in r.get("guard_extra") or []):
                    continue
                _kept += 1
            if _kept == 0:
                continue
            n = min(_kept, r.get("maxHits", 99))
        else:
            n = min(len(ms), r.get("maxHits", 99))
        cat = r.get("category", "?")
        by_cat[cat] = by_cat.get(cat, 0) + n
        # maxHits 是原作者设的容忍线：没超过就不该扣分。
        # 原来只看 severity，于是 rather-than 63 处（容忍线 99）
        # 也照样扣 4 分 —— 那不是诊断，是误报。
        _cap = r.get("maxHits", 99)
        if n >= _cap:   # 到达容忍线就提示，不是超过才提示
            score += _WG_SEV.get(r.get("severity", "low"), 2)
        # report() 按 phrase/count 渲染，这里补上以兼容
        found.append(dict(id=r["id"], cat=cat, n=n,
                          label=r.get("label", ""),
                          phrase=r.get("label") or r["id"],
                          count=n))
    found.sort(key=lambda x: -x["n"])
    return dict(name="细分规则", found=found, total=sum(by_cat.values()),
                score=min(40, score), by_cat=by_cat)




def _strip_envs(tex: str) -> str:
    """剥掉代码块、表格、公式环境，只留正文散文。

    不剥的话 verbatim 里的 Python 代码和 tabular 里的表格内容
    会被当成超长句（实测最长"句"215 词，其实是代码块）。
    """
    b = tex
    # figure / table 环境也要剥：不剥的话
    # "heat sink [H] Figure~ fixes the order…" 会被当成一句（实测 45 词）。
    for env in ("verbatim", "tabular", "equation", "align", "array",
                "figure", "figure*", "table", "table*",
                "verbatim*", "tabular*", "equation*", "align*"):
        e = re.escape(env)
        # 允许 \begin{figure}[H] 这种带位置参数的形式 —— 不加 (\s*\[[^\]]*\])?
        # 的话 [H] 会让整条正则失配，figure 内容就漏进句子统计。
        # 剥成 ". " 而不是 " " —— 环境前后本来是段落边界，
        # 用空格会把「heat sink」和「Figure~… fixes the order」连成一句。
        b = re.sub(r"\\begin\{" + e + r"\}(\s*\[[^\]]*\])?.*?\\end\{"
                   + e + r"\}", " . ", b, flags=re.S)
    b = re.sub(r"\\(?:section|subsection|subsubsection|paragraph|"
               r"caption|label)\*?\{[^}]*\}", " ", b)
    b = re.sub(r"\$[^$]*\$", " X ", b)
    # \item 必须在「删所有命令」之前处理，否则它先被删掉，
    # 一个 itemize 的 8 项就会被当成一整句（实测 66 词）。
    b = re.sub(r"\\item\b", " . ", b)
    b = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^{}]*\})?", " ", b)
    # \textbf / \textit 的 \t 在部分转义路径下会残留成 "extbf"，
    # 兜底清掉，否则会出现在句长报告的句首。
    b = re.sub(r"\\?\b(extbf|extit|extrm|extsc)\b", " ", b)
    b = re.sub(r"[{}]", " ", b)
    # itemize 的项之间是 \item，被替换成 . 之后原内容常以 . 结尾，
    # 于是出现 ".;" —— 这是项边界，当句界处理。
    b = re.sub(r"[.]\s*;", ". ", b)
    # \textbf{} 被删后会留下孤立的冒号/点，清掉行首的
    b = re.sub(r"(?:^|[.])\s*:\s+", ". ", b)
    b = re.sub(r"\s+", " ", b)
    return re.sub(r"\s*([.])\s*\1+", r"\1 ", b)


def check_sentence_length(t: str) -> dict:
    """真句长：按词数判，>60 词 high、41-60 medium。

    替代 overlong-sentence-en —— 那条正则数的是从句连词
    （that 90 处、which 46 处），不是句长。
    """
    b = _strip_envs(t)
    sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+", b)
             if len(x.split()) >= 5]
    if len(sents) < 20:
        return dict(name="句长", found=[], total=0, score=0)
    long40 = [x for x in sents if len(x.split()) > 40]
    long60 = [x for x in sents if len(x.split()) > 60]
    found = []
    for x in sorted(long60, key=lambda z: -len(z.split()))[:5]:
        found.append(dict(phrase=x[:60] + "…",
                          count=len(x.split())))
    for x in sorted(long40, key=lambda z: -len(z.split()))[:5]:
        if x not in long60:
            found.append(dict(phrase=x[:60] + "…",
                              count=len(x.split())))
    # 17 个 >40 词 = 0 分；每多 5 个加 2 分；>60 词每个再 +2
    score = min(20, max(0, (len(long40) - 5) * 2) + len(long60) * 2)
    return dict(name="句长", found=found[:8],
                total=len(long40), score=score)


def analyze(tex: str) -> dict:
    # 章节标题里的「Problem N:」是结构，不是套话。
    # strip_tex 会剥掉命令但保留标题文字，所以必须**先**把标题整段
    # 去掉再统计问题罗列；否则白扣 30 分，把真问题（句式重复）淹掉。
    _notitle = re.sub(
        r"\\(?:section|subsection|subsubsection|chapter)\*?\{[^}]*\}",
        " ", tex)
    body = strip_tex(tex)
    body_nt = strip_tex(_notitle)
    checks = [check_ai_phrases(body), check_template(body),
              check_problem_list(body_nt), check_repetition(body),
              check_paragraphs(body), check_wg_rules(body),
              check_sentence_length(tex)]
    score = min(100, sum(c["score"] for c in checks))
    return dict(score=score, issues=sum(c["total"] for c in checks),
                checks=checks, body_words=_words(body),
                grade=("优秀" if score < 20 else
                       "一般" if score < 50 else "较差"))


def report(r: dict) -> str:
    L = [f"AI 味指数：{r['score']}/100 — {r['grade']}  "
         f"（正文 {r['body_words']} 词，问题 {r['issues']} 处）", ""]
    for c in r["checks"]:
        if c["total"]:
            L.append(f"  {c['name']}（扣 {c['score']} 分）")
            for f in c["found"][:5]:
                L.append(f"    · \"{f['phrase']}\" x{f['count']}")
            if len(c["found"]) > 5:
                L.append(f"    · ... 还有 {len(c['found']) - 5} 个")
        else:
            extra = f"（标准差 {c['std']}）" if c.get("std") else ""
            L.append(f"  {c['name']}：无问题{extra}")
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

    # 干净文本：不该有 AI 味
    clean = ("The residuals show no systematic curvature against fitted "
             "values. Three of the eighty-four observations fall outside "
             "the two-sigma band, which is close to the five percent "
             "expected under normality.\n\n"
             "A quadratic term reduces the cross-validated error by "
             "eighteen percent but costs two extra parameters. On a sample "
             "of this size that trade is not worth making, and the linear "
             "specification is retained throughout.\n\n"
             "Collinearity is mild: the condition number of the design "
             "matrix is 14.2, well below the usual threshold of 30.")
    r = analyze(clean)
    ck("干净文本 AI 味低", r["score"] < 20, f"{r['score']}/100")
    ck("干净文本能数出词数", r["body_words"] > 60, str(r["body_words"]))

    # AI 味重：套话密集
    ai = ("It is worth noting that this plays a crucial role. "
          "In conclusion, it is obvious that the results are of great "
          "significance. As we all know, with the development of modern "
          "society this provides strong support.\n\n"
          "Firstly we note the data. Secondly we note the model. "
          "Thirdly we note the result. Lastly we conclude.")
    r2 = analyze(ai)
    ck("套话密集时指数高", r2["score"] >= 40, f"{r2['score']}/100")
    ck("检出 AI 高频套话", any(c["name"] == "AI 高频套话" and c["total"] > 3
                         for c in r2["checks"]))
    ck("检出模板化连接词", any(c["name"] == "模板化连接词" and c["total"] > 2
                         for c in r2["checks"]))

    # 问题罗列
    r3 = analyze(" ".join(f"For problem {i} we do something." for i in range(1, 8)))
    ck("检出问题罗列", any(c["name"] == "问题罗列" and c["total"] >= 5
                       for c in r3["checks"]))

    # 句式重复
    rep = " ".join("The model is fitted here in a careful way." for _ in range(6))
    r4 = analyze(rep)
    ck("检出句式重复", any(c["name"] == "句式重复" and c["total"] >= 3
                       for c in r4["checks"]),
       str([c for c in r4["checks"] if c["name"] == "句式重复"])[:80])

    # 段落太均匀
    para = " ".join(["word"] * 30)
    uni = "\n\n".join([para] * 5)
    r5 = analyze(uni)
    ck("段落长度过均匀被扣分",
       any(c["name"] == "段落长度" and c["score"] >= 30 for c in r5["checks"]),
       str([c.get("std") for c in r5["checks"] if c["name"] == "段落长度"]))

    # LaTeX 预处理：命令不该被当成文字
    tex = (r"\section{Model}" + "\n\n" + r"\begin{equation}"
           r" y = \beta_0 + \beta_1 x \end{equation}" + "\n\n"
           "The slope is estimated by ordinary least squares on "
           "eighty-four observations, and the intercept absorbs the "
           "reference level of the design.")
    body = strip_tex(tex)
    ck("剥掉 section 命令", "section" not in body.lower())
    ck("剥掉公式内容", "beta" not in body.lower())
    ck("保留正文", "ordinary least squares" in body)

    # 中文词表仍然有效
    r6 = analyze("值得注意的是，随着科技的发展，本文提出了一种新的方法。"
                 "综上所述，具有重要意义。")
    ck("中文套话也检出", r6["score"] > 0, f"{r6['score']}/100")

    print(f"\n{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="AI 味检测")
    ap.add_argument("file", nargs="?", default="")
    ap.add_argument("--dir", default="")
    ap.add_argument("--threshold", type=int, default=50)
    a = ap.parse_args(argv)

    # 注意：位置参数会吃掉 "selftest"，必须先判断
    # （rules.py 踩过一次同样的坑）
    if a.file == "selftest" or (not a.file and not a.dir):
        return selftest()

    files = ([a.file] if a.file else
             [os.path.join(a.dir, f) for f in os.listdir(a.dir)
              if f.endswith(".tex")])
    worst = 0
    for p in files:
        if not os.path.exists(p):
            print(f"  没有 {p}")
            continue
        r = analyze(open(p, encoding="utf-8").read())
        worst = max(worst, r["score"])
        print(f"\n=== {os.path.basename(p)} ===")
        print(report(r))
    return 0 if worst < a.threshold else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
