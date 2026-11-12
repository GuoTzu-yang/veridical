#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""chapter_coverage.py —— 「结论有没有收束重述声明的每一问」，用可重跑的证据回答。

为什么需要它（第 123 轮）：
`redteam.py` 的 conclusion 板第一条探针原来写「结论是否回应了**题面**的每一问」，
既越界（题面是 restatement 板的输入，而且仓库里没有），又不可机械复核
（靠审核者读一遍下判断）。实测后果：它拿 2026 MCM Problem C 的 10 问去要求
一篇工具论文逐条回应。

改成本工具后，这条探针变成**两次 grep**：
  1. 从 `Restatement` 节的 `\\begin{enumerate}` 里抽出它声明要答的问（取 `\\emph{…}` 标题）
  2. 在 `Conclusion` 节里查每个问的实词是否出现

证据形态：每个问给出「抽到的实词 → 在结论段命中 0/非 0 次 → 结论第几行」。
判据可复核：换一篇论文、换一个结论段，重跑同一条命令即可。

用法：
    python tools/chapter_coverage.py            # 人读
    python tools/chapter_coverage.py --json
退出码：0 = 每一问都在结论里出现；1 = 有问没出现。
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.join(HERE, "out", "final", "paper.tex")

# 英语功能词：不承载「这一问在问什么」的信息，不参与命中判断。
STOP = set("""a an the is are was were be been being of to in on at for with by and or
but if then that this these those it its as which who whom whose what where when why how
does do did can could should would may might must shall will not no nor so than too very
we our us they them their he she his her you your i me my one two three four five""".split())


def sections(tex):
    """返回 [(标题, 正文)]，按 \\section 切。"""
    out = []
    parts = re.split(r"\n\\section\*?\{([^}]*)\}", "\n" + tex)
    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        out.append((title, body))
    return out


def declared_questions(body):
    """从一节里抽 `\\begin{enumerate}` 的每一项，取其中第一个 \\emph{…} 作标题。"""
    qs = []
    for m in re.finditer(r"\\begin\{enumerate\}(.*?)\\end\{enumerate\}",
                         body, re.S):
        block = m.group(1)
        for item in re.split(r"\\item\s+", block)[1:]:
            e = re.search(r"\\emph\{([^{}]*)\}", item)
            title = e.group(1) if e else item.strip()[:60]
            qs.append(dict(title=title.strip(), raw=item.strip()[:160]))
    return qs


def content_words(text):
    """取实词（长度 >= 4 的字母词，去停用词，去 LaTeX 命令参数）。"""
    t = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?\{[^{}]*\}", " ", text)
    ws = re.findall(r"[A-Za-z][A-Za-z\-]{3,}", t)
    return [w for w in ws if w.lower() not in STOP]


def main(argv):
    tex = io.open(PAPER, encoding="utf-8", errors="replace").read()
    secs = sections(tex)
    by = {t.lower(): b for t, b in secs}

    rs = next((b for t, b in secs if "restatement" in t.lower()), "")
    cn = next((b for t, b in secs if t.lower().strip() == "conclusion"), "")
    if not rs or not cn:
        print("找不到 Restatement 或 Conclusion 节")
        return 2

    qs = declared_questions(rs)
    rows = []
    for q in qs:
        words = content_words(q["title"])
        # 词形归一：问句里写 verified、结论里写 verify，是同一个概念。
        # 取前 5 个字母做前缀匹配（verif 覆盖 verify/verified/verification），
        # 否则检测器会把「已收束」误判成「未收束」——这是脚本自己的 bug，
        # 第 123 轮实测踩过：Q1 明明已经写了 What to verify, and where，
        # 而检测器查的完整词 verified 命中 0。
        hits = []
        for w in words:
            stem = w.lower()[:5]
            n = len(re.findall(r"\b" + re.escape(stem), cn, re.I))
            hits.append((w, n))
        covered = any(n > 0 for _w, n in hits)
        line = None
        if covered:
            first = next(w for w, n in hits if n > 0)[:5]
            for i, ln in enumerate(cn.splitlines(), 1):
                if re.search(r"\b" + re.escape(first), ln, re.I):
                    line = i
                    break
        rows.append(dict(question=q["title"], words=words, hits=hits,
                         covered=covered, hit_line=line))

    if "--json" in argv:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0 if all(r["covered"] for r in rows) else 1

    print("重述声明的问：%d 条  结论段词数：%d"
          % (len(rows), len(re.findall(r"[A-Za-z][A-Za-z'-]+", cn))))
    print()
    bad = 0
    for i, r in enumerate(rows, 1):
        flag = "OK  " if r["covered"] else "**未收束**"
        if not r["covered"]:
            bad += 1
        print("%d. %s %s" % (i, flag, r["question"][:78]))
        hitstr = "  ".join("%s=%d" % (w, n) for w, n in r["hits"][:6])
        print("     实词命中：%s%s"
              % (hitstr, ("   结论内行 %d" % r["hit_line"]) if r["hit_line"] else ""))
    print()
    print("结论未收束的问：%d / %d" % (bad, len(rows)))
    if bad:
        print("判据可复核：重跑本命令即可；换论文/换结论段同样适用。")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
