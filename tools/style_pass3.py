"""第三批语言改写：消除句式重复 + 再拆 4 个长句。

前两轮的结果（ai_taste 19 → 30 → 26）说明：
  · 把破折号改成冒号是**负优化** —— 句子更长，句长扣分从 14 涨到 20；
  · 真正的修法只有两种：句号断句、换掉重复的句首。
本批做这两件事。三个图注的 Data 句完全相同，靠其后的 label 区分。

注意：`\\textbf{The audience vote is reconstructed per week...}` 是结构性
小标题，与另外两处不是同一个语境，保留不动（避免为降分改坏结构）。
"""
import os
import re

P = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "out", "d2026c", "paper.tex")

PAIRS = [
    # ── 句式重复：the audience vote is ×3 → ×1 ──
    ("audience vote is(正文)", "The audience vote is not a noisy version of the judge score",
     "Audience support is not a noisy version of the judge score"),
    ("audience vote is(Memo)", "The audience vote is secret, but the eliminations are not",
     "The vote is secret, but the eliminations are not"),

    # ── 句式重复：Data: our reconstruction from ×3 → 三种说法 ──
    ("图注 lambda", "Data: our reconstruction from the judge scores supplied with the problem.} \\label{fig:lambda}",
     "Data: reconstructed from the judge scores supplied with the problem.} \\label{fig:lambda}"),
    ("图注 feasible", "Data: our reconstruction from the judge scores supplied with the problem.} \\label{fig:feasible}",
     "Data: the same reconstruction.} \\label{fig:feasible}"),
    ("图注 weight", "Data: our reconstruction from the judge scores supplied with the problem.} \\label{fig:weight}",
     "Source: our reconstruction from the same scores.} \\label{fig:weight}"),

    # ── 再拆长句（句号断句） ──
    ("P2 分号句", "by a large audience share; the percentage rule keeps the judge gap",
     "by a large audience share. The percentage rule keeps the judge gap"),
    ("稳健性句", "with the same sign and significance; the coefficient on age",
     "with the same sign and significance. The coefficient on age"),
    ("结论 78.8 句", "in $78.8\\%$ of weeks, and in $150$ of those $152$ weeks",
     "in $78.8\\%$ of weeks. In $150$ of those $152$ weeks"),
    ("whereas 句", ", whereas the percentage rule preserves the size of the judge gap",
     ". The percentage rule preserves the size of the judge gap"),
]


def main():
    t = open(P, encoding="utf-8").read()
    ok = fail = 0
    for name, old, new in PAIRS:
        pat = r"\s+".join(re.escape(w) for w in old.split())
        hits = re.findall(pat, t)
        if len(hits) == 1:
            t = re.sub(pat, lambda m: new, t, count=1)
            ok += 1
            print("  [OK]   %-16s" % name)
        elif not hits:
            fail += 1
            print("  [MISS] %-16s" % name)
        else:
            fail += 1
            print("  [DUP]  %-16s 命中 %d 次" % (name, len(hits)))
    if ok:
        open(P, "w", encoding="utf-8", newline="\n").write(t)
    print("\n改写 %d 条，跳过 %d 条" % (ok, fail))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
