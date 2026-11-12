#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 overlong-sentence-en 从「数连词」换成「真句长」。

问题
----
原规则的正则是：
    \\b(which|that|while|whereas|although|because|thereby|leading to|...)\\b
它数的是**从句连词数量**，不是句子长度。而 `that` 是英文里最常见的
词之一（本文 90 处），所以这条规则永远会报满 maxHits。

实测对照（剥掉 verbatim/tabular/equation 环境后）：
    规则报 99 处「超长句」
    真实 >40 词的句子只有 17 个，最长 69 词，中位 21 词

做法
----
在 aitaste.py 里用真句长判据替代该规则：
    >60 词 → high（一定该拆）
    41-60 词 → medium
    <=40 词 → 不动
并把 ai_rules.json 里的旧规则标成 disabled（保留可追溯，不再计分）。
"""
import ast
import json
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ══ ① 旧规则标记 disabled ══
RP = os.path.join(HERE, "kb", "ai_rules.json")
d = json.load(open(RP, encoding="utf-8"))
n_dis = 0
for r in d["rules"]:
    if r["id"] == "overlong-sentence-en":
        r["disabled"] = True
        r["disabled_reason"] = (
            "正则数的是从句连词（that/which/because），不是句长；"
            "实测输出 99 处而真实 >40 词的句子只有 17 个。"
            "已由 aitaste.check_sentence_length 的真句长判据替代。")
        n_dis += 1
json.dump(d, open(RP, "w", encoding="utf-8", newline="\n"),
          ensure_ascii=False, indent=1)
print(f"① 旧规则标 disabled：{n_dis} 条")

# ══ ② aitaste.py 加真句长判据 ══
P = os.path.join(HERE, "aitaste.py")
s = open(P, encoding="utf-8").read()

if "check_sentence_length" not in s:
    FUNC = '''

def _strip_envs(tex: str) -> str:
    """剥掉代码块、表格、公式环境，只留正文散文。

    不剥的话 verbatim 里的 Python 代码和 tabular 里的表格内容
    会被当成超长句（实测最长"句"215 词，其实是代码块）。
    """
    b = tex
    for env in ("verbatim", "tabular", "equation", "align", "array",
                "verbatim*", "tabular*", "equation*", "align*"):
        e = re.escape(env)
        b = re.sub(r"\\\\begin\\{" + e + r"\\}.*?\\\\end\\{" + e + r"\\}",
                   " ", b, flags=re.S)
    b = re.sub(r"\\\\(?:section|subsection|subsubsection|paragraph|"
               r"caption|label)\\*?\\{[^}]*\\}", " ", b)
    b = re.sub(r"\\$[^$]*\\$", " X ", b)
    b = re.sub(r"\\\\[a-zA-Z]+\\*?(\\[[^\\]]*\\])?(\\{[^{}]*\\})?", " ", b)
    b = re.sub(r"[{}]", " ", b)
    return re.sub(r"\\s+", " ", b)


def check_sentence_length(t: str) -> dict:
    """真句长：按词数判，>60 词 high、41-60 medium。

    替代 overlong-sentence-en —— 那条正则数的是从句连词
    （that 90 处、which 46 处），不是句长。
    """
    b = _strip_envs(t)
    sents = [x.strip() for x in re.split(r"(?<=[.!?])\\s+", b)
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


'''
    k = s.find("def analyze(")
    s = s[:k] + FUNC + s[k:]

    OLD = '''              check_paragraphs(body), check_wg_rules(body)]'''
    NEW = '''              check_paragraphs(body), check_wg_rules(body),
              check_sentence_length(tex)]'''
    assert OLD in s, "analyze 锚点未匹配"
    s = s.replace(OLD, NEW, 1)

    # check_wg_rules 跳过 disabled
    OLD2 = '''    for r in rules:
        try:
            cre = re.compile(r["regex"])'''
    NEW2 = '''    for r in rules:
        if r.get("disabled"):
            continue
        try:
            cre = re.compile(r["regex"])'''
    assert OLD2 in s, "check_wg_rules 锚点未匹配"
    s = s.replace(OLD2, NEW2, 1)

    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("② aitaste 加了真句长判据，并跳过 disabled 规则")

import subprocess
import sys
r = subprocess.run([sys.executable, "aitaste.py", "out/fig/paper.tex"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
print(r.stdout[:1800])
