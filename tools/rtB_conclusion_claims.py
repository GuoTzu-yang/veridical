# -*- coding: utf-8 -*-
"""conclusion 板只读探针 3：核对结论表「证据列」每条引用是否在正文落地；核对散文段与表段的分工。
只读 out/final/paper.tex，只打印。"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.join(ROOT, "out", "final", "paper.tex")


def load():
    with io.open(PAPER, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read().splitlines()


def span(lines, start_mark):
    s = None
    for i, ln in enumerate(lines):
        if ln.strip().startswith(start_mark):
            s = i
            break
    e = None
    for j in range(s + 1, len(lines)):
        if lines[j].lstrip().startswith(r"\section{"):
            e = j
            break
    return s, e


def main():
    lines = load()
    s, e = span(lines, r"\section{Conclusion}")
    concl = lines[s:e]
    # 散文段：从 section 到第一个 subsection
    sub = None
    for i, ln in enumerate(concl):
        if ln.lstrip().startswith(r"\subsection{"):
            sub = i
            break
    prose = "\n".join(concl[:sub])
    table = "\n".join(concl[sub:])
    print("=== 0. 散文段 vs 表段 ===")
    print("  prose lines: %d  (L%d-L%d)" % (sub, s + 1, s + sub))
    print("  table lines: %d  (L%d-L%d)" % (len(concl) - sub, s + sub + 1, e))

    print("")
    print("=== 1. 散文段是否提到「数字分类 / 分解 / computed」（论文自述 P1）===")
    for w in ["decompos", "four classes", "computed", "classif", "token",
              "structural", "tabulated", "temporal", "configuration"]:
        print("  prose %-14s %d | table %d" % (w, prose.lower().count(w), table.lower().count(w)))

    print("")
    print("=== 2. 结论表「证据列」逐条的正文出处核对 ===")
    targets = [
        ("23/23", "L1177 23/23 problems green"),
        ("reproducible by one command", "L1177"),
        ("One corpus", "L1178 一个语料"),
        ("designed alongside", "L1178 检查与报告同设计"),
        ("two scopes", "L1180 两个口径"),
        ("untraced by construction", "L1181 结构整数天然不溯源"),
        ("five problems", "L1183 五个题消融"),
        ("controlled comparison", "L1184 无有/无对照"),
        ("independent rater", "L1184 无独立评分者"),
        ("7 of 7", "L1186"),
        ("corpus labels", "L1186"),
        ("generalisation to unseen", "L1188"),
        ("30 rounds", "L1189"),
        ("129", "L1189"),
        ("our own reading", "L1190"),
        ("inter-rater", "L1191"),
        ("51 of 51", "L1192"),
        ("three defects", "L1192"),
        ("One project", "L1193"),
        ("not by an independent audit", "L1194"),
    ]
    for t, note in targets:
        rows = [i + 1 for i, ln in enumerate(lines) if t.lower() in ln.lower()]
        inside = [r for r in rows if s + 1 <= r <= e]
        outside = [r for r in rows if not (s + 1 <= r <= e)]
        print("  %-28s provenance=%s%s | %s"
              % (t, outside[:6] if outside else "NONE",
                 "  <== 仅结论出现" if (outside == [] and inside) else "", note))

    print("")
    print("=== 3. tab:taxonomy 是否真给 30 rounds 与 129 kB ===")
    lab = None
    for i, ln in enumerate(lines):
        if r"\label{tab:taxonomy}" in ln:
            lab = i
    print("  label line: %s" % (lab + 1 if lab is not None else "NONE"))
    if lab is not None:
        lo = max(0, lab - 40)
        for i in range(lo, min(len(lines), lab + 6)):
            print("%5d| %s" % (i + 1, lines[i]))

    print("")
    print("=== 4. sec:error 的 two scopes 上下文 ===")
    for i, ln in enumerate(lines):
        if "two scopes" in ln.lower():
            for j in range(max(0, i - 10), min(len(lines), i + 8)):
                print("%5d| %s" % (j + 1, lines[j]))
            break

    print("")
    print("=== 5. sec:sensitivity 的 five problems 是否确是 5 个 ===")
    for i, ln in enumerate(lines):
        if "five problems" in ln.lower():
            for j in range(max(0, i - 12), min(len(lines), i + 10)):
                print("%5d| %s" % (j + 1, lines[j]))
            break

    print("")
    print("=== 6. 结论正文的强度断言 vs 表里的自我限定（内在一致性）===")
    pairs = [
        ("all in the verification code rather than in the mathematics",
         "S2 范围断言（数学洁净）"),
        ("whose passes mean something", "S9 通过有意义"),
        ("only a checker if it can fail", "S6 必要性断言"),
        ("six classes of defect", "S2 六类"),
        ("Six defect classes recur", "表 L1189 recurrence 断言"),
    ]
    for t, note in pairs:
        inprose = prose.replace("\n", " ").count(t)
        intable = table.replace("\n", " ").count(t)
        print("  %-58s prose=%d table=%d | %s" % (t[:58], inprose, intable, note))
    # 检查表里同一行是否自带削弱
    print("")
    print("  表内同一行的自我限定：")
    for i in range(s + sub, e):
        ln = lines[i]
        if "recur" in ln or "mean something" in ln or "designed alongside" in ln:
            print("%5d| %s" % (i + 1, ln.strip()))

    print("")
    print("=== 7. 结论是否出现题面名（DWTS / Problem C / memo / producer / season）===")
    for w in ["Problem C", "DWTS", "Dancing", "memo", "producer", "season",
              "celebrity", "fan"]:
        n = "\n".join(concl).lower().count(w.lower())
        print("  %-12s conclusion_hits=%d" % (w, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
