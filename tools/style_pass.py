"""对 paper.tex 做一批精确文本替换（去 AI 味）。

只用**精确字符串**匹配，不用正则；每条报告命中次数，未命中即失败并列出，
避免「以为改了其实没改」。改完由外部流程重新编译 + gate 验证。

依据：out/d2026c/review/style.md 的 R1/R4/R12/R18/R28/R30/R50 等条目，
但行号已随前几轮修改漂移，故这里以**原文片段**为锚，不依赖行号。
"""
import os
import sys

P = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "out", "d2026c", "paper.tex")

# (说明, 原片段, 新片段)
PAIRS = [
    # ── 空洞强调副词 ──
    ("itself(自评式)", "and that the size of the bound is itself the answer to the certainty question",
     "and that the size of the bound answers the certainty question"),
    ("itself(元评论)", "which is itself worth stating", "which is worth stating"),
    ("genuinely(1)", "support and judge support genuinely diverge",
     "support and judge support point in opposite directions"),
    ("genuinely(2)", "what a genuinely inverted vote produces",
     "what an inverted vote produces"),
    ("genuinely(3)", "are genuinely different systems", "are different systems"),
    ("genuinely(4)", "the judges genuinely disagree", "the judges disagree"),

    # ── 过度连接词 ──
    ("more importantly", "and, more importantly, the transformation discards",
     "and the transformation discards"),

    # ── 破折号（把成对插入语改成逗号/括号/冒号，保留三对） ──
    ("破折号1", "never given --- that is precisely why it has to be reconstructed --- so every",
     "never given. That is precisely why it has to be reconstructed, so every"),
    ("破折号2", "is popular --- exactly the controversial case --- no value",
     "is popular (exactly the controversial case), no value"),
    ("破折号3", "share of range --- but the range now depends on $N$",
     "share of range, but the range now depends on $N$"),
    ("破折号4", "It is not --- the median feasible width of $\\lambda$ is $0.494$ --- and the residual",
     "It is not: the median feasible width of $\\lambda$ is $0.494$, and the residual"),
    ("破折号5", "the optimum is narrow --- $95.9\\%$ of reconstructable weeks reproduced there against $66.3\\%$ at $0.45$ and $79.8\\%$ at $0.55$ --- so no",
     "the optimum is narrow: $95.9\\%$ of reconstructable weeks are reproduced there, against $66.3\\%$ at $0.45$ and $79.8\\%$ at $0.55$, so no"),
    ("破折号6", "not rescalings of one another --- they name different",
     "not rescalings of one another: they name different"),
]


def main():
    import re
    t = open(P, encoding="utf-8").read()
    ok = fail = 0
    for name, old, new in PAIRS:
        # 原文在 LaTeX 源里被硬换行切开，所以不能按原样匹配。
        # 把片段按空白切成词，用 \s+ 连接 —— 既能跨行匹配，又不会误伤。
        pat = r"\s+".join(re.escape(w) for w in old.split())
        hits = re.findall(pat, t)
        if len(hits) == 1:
            # 用函数做替换：new 里含 \lambda、\% 等，直接当替换串会被当转义
            t = re.sub(pat, lambda m: new, t, count=1)
            ok += 1
            print("  [OK]   %-16s" % name)
        elif not hits:
            fail += 1
            print("  [MISS] %-16s  未找到片段（可能已被前轮改写）" % name)
        else:
            fail += 1
            print("  [DUP]  %-16s  命中 %d 次，跳过（需人工确认）" % (name, len(hits)))
    if ok:
        open(P, "w", encoding="utf-8", newline="\n").write(t)
    print("\n替换成功 %d 条，跳过 %d 条" % (ok, fail))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
