"""第二批语言改写：把超长句拆成两句（句号断句）。

为什么不用冒号
--------------
第一轮把成对破折号改成冒号/逗号，结果 ai_taste 从 19 掉到 30 —— 因为
冒号让句子更长，触发了「句长」扣分（14 → 20）。真正的修法是在语义断点
处用句号切开，而不是换一个连接符。

每条都是「锚片段 → 断句后的片段」，只动标点与大小写，不删任何内容。
"""
import os
import re

P = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "out", "d2026c", "paper.tex")

PAIRS = [
    ("摘要 certainty 句", "of one, and the bound does not shrink monotonically:",
     "of one. The bound does not shrink monotonically:"),
    ("P4 方法句", "the consistency measure asks: applying",
     "the consistency measure asks. Applying"),
    ("P2 方向句", "the weaker judge score, because it compresses",
     "the weaker judge score. It compresses"),
    ("P2 代数句", "This is what the algebra predicts: the ranking rule converts",
     "This is what the algebra predicts. The ranking rule converts"),
    ("强假设句", "weeks feasible --- a week counts as feasible only if",
     "weeks feasible. A week counts as feasible only if"),
    ("λ 精确句", "and we use it as a check: the exact median width",
     "and we use it as a check. The exact median width"),
    ("结论首句", "under the ranking rule, but the certainty it",
     "under the ranking rule. The certainty it"),
    ("rank 放宽句", "with respect to a poor judge score: it compresses the judge signal",
     "with respect to a poor judge score. It compresses the judge signal"),
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
            print("  [OK]   %-14s" % name)
        elif not hits:
            fail += 1
            print("  [MISS] %-14s" % name)
        else:
            fail += 1
            print("  [DUP]  %-14s 命中 %d 次" % (name, len(hits)))
    if ok:
        open(P, "w", encoding="utf-8", newline="\n").write(t)
    print("\n断句 %d 条，跳过 %d 条" % (ok, fail))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
