"""第 4 批改写：压缩摘要，使其真正止于第 1 页。

背景
----
2026-11-10 视觉检查发现：摘要末两句 + Keywords 溢出到第 2 页，第 2 页 90% 空白。
而 gate 的 abs_page 用的是「几个固定短语」判据，全部没命中，一直报 PASS。
修好判据后它立刻红了。

原则
----
只删冗余表达与重复限定，**所有数字、所有小问的答案、所有因果链保持不变**。
摘要的四问锚点与量化结果不能动（abstract 检查依赖它们）。
"""
import os
import re

P = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "out", "d2026c", "paper.tex")

PAIRS = [
    ("首段压缩",
     "We show that this is enough to bound the audience vote but not to point-identify it, and that the size of the bound answers the certainty question.",
     "We show that this bounds the audience vote without point-identifying it, and that the size of the bound answers the certainty question."),
    ("验证句压缩",
     "We verify the closed form against an independent sampling procedure, and the two agree on all 231 season-weeks.",
     "An independent sampling procedure agrees on all 231 season-weeks."),
    ("确定度句",
     "Certainty is low and it is uneven.",
     "Certainty is low and uneven."),
    ("争议案例句",
     "The controversial contestants the problem names survive precisely because their audience support is large in weeks where the percentage rule remains consistent.",
     "The named controversial contestants survive because their audience support is large in weeks the percentage rule still explains."),
    ("行业伙伴句",
     "Industry and partner effects are reported descriptively only, because several categories contain a single contestant.",
     "Industry and partner effects are descriptive only: several categories hold a single contestant."),
    ("P4 建议句",
     "We recommend retaining the percentage rule at equal weight, and we propose using the unused slack for excitement rather than for outcome: when judges agree closely, let the audience break the bottom-two tie; when they disagree sharply, keep the judges' judgment.",
     "We recommend retaining the percentage rule at equal weight, and propose spending the slack on excitement: when judges agree closely, let the audience break the bottom-two tie; when they disagree, keep the judges' judgment."),
]


def main():
    t = open(P, encoding="utf-8").read()
    ok = fail = 0
    saved = 0
    for name, old, new in PAIRS:
        pat = r"\s+".join(re.escape(w) for w in old.split())
        hits = re.findall(pat, t)
        if len(hits) == 1:
            t = re.sub(pat, lambda m: new, t, count=1)
            ok += 1
            saved += len(old.split()) - len(new.split())
            print("  [OK]   %-12s 省 %d 词" % (name, len(old.split()) - len(new.split())))
        elif not hits:
            fail += 1
            print("  [MISS] %-12s" % name)
        else:
            fail += 1
            print("  [DUP]  %-12s 命中 %d 次" % (name, len(hits)))
    if ok:
        open(P, "w", encoding="utf-8", newline="\n").write(t)
    print("\n压缩 %d 处，共省 %d 词，跳过 %d 处" % (ok, saved, fail))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
