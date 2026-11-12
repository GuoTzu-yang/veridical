"""把论文正文同步到冻结的实验数据（精确字符串替换）。

为什么用脚本而不是手改：这一次要同步 40 余处数字，手改必然漏；而漏一处
就等于论文里有一个数对不上实验输出。脚本会报告每条是否命中，未命中即报错。
"""
import os
import sys

P = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "out", "arch", "paper.tex")

REPL = [
    # ── 摘要 ──
    ("seven capabilities cost 1.214\\,s in", "seven capabilities cost 1.191\\,s in"),
    ("from 410.3 checks per second down to\n7.3, so", "from 398.4 checks per second down to\n7.6, so"),
    ("accounts for 4.8\\% of a problem's wall time",
     "accounts for 4.7\\% of a problem's wall time"),
    ("with at least 70 self-checks costs 0.908\\,s",
     "with at least 70 self-checks costs 0.886\\,s"),
    ("and 353 would be needed to reach a half-width of 0.05",
     "and 355 would be needed to reach a half-width of 0.05"),
    ("criteria selects DP, queueing and network metrics as the three capabilities worth keeping,\nand that choice survives a $\\pm20\\%$ weight perturbation.",
     "criteria selects DP, network metrics and MIP as the three capabilities worth keeping.\nThat ranking is not as firm as it looks: the second and third differ by 0.003, and a\nre-measurement of the timings swaps them."),

    # ── 引言 ──
    ("Efficiency across\ncapabilities varies by a factor of 56,",
     "Efficiency across\ncapabilities varies by a factor of 52,"),

    # ── 表 1：能力成本 ──
    ("Evaluation (TOPSIS) & 5  & 0.114 & 0.022 & 43.9 \\\\",
     "Evaluation (TOPSIS) & 5  & 0.112 & 0.006 & 44.6 \\\\"),
    ("Statistics          & 13 & 0.037 & 0.006 & 351.4 \\\\",
     "Statistics          & 13 & 0.039 & 0.004 & 333.5 \\\\"),
    ("Queueing            & 16 & 0.039 & 0.005 & 410.3 \\\\",
     "Queueing            & 16 & 0.040 & 0.006 & 398.4 \\\\"),
    ("Networks            & 14 & 0.113 & 0.007 & 123.9 \\\\",
     "Networks            & 14 & 0.117 & 0.006 & 119.4 \\\\"),
    ("Fitting             & 5  & 0.682 & 0.080 & 7.3 \\\\",
     "Fitting             & 5  & 0.656 & 0.032 & 7.6 \\\\"),
    ("MIP                 & 13 & 0.114 & 0.008 & 114.0 \\\\",
     "MIP                 & 13 & 0.114 & 0.005 & 113.8 \\\\"),
    ("Dynamic programming & 27 & 0.115 & 0.008 & 234.8 \\\\",
     "Dynamic programming & 27 & 0.113 & 0.005 & 238.9 \\\\"),
    ("Total               & 93 & 1.214 & --- & 76.6 \\\\",
     "Total               & 93 & 1.191 & --- & 78.1 \\\\"),

    # ── P1 ──
    ("The optimum of \\eqref{eq:ip} costs \\textbf{0.908\\,s}",
     "The optimum of \\eqref{eq:ip} costs \\textbf{0.886\\,s}"),
    ("fitting alone costs 0.682\\,s, which is 75\\% of the total, because it is\nthe only capability that serves the second sub-problem and it is 48 times less\nefficient than queueing.",
     "fitting alone costs 0.656\\,s, which is 74\\% of the total, because it is\nthe only capability that serves the second sub-problem and it is 52 times less\nefficient than queueing."),
    ("Coverage routing is fragile because 75\\% of its time sits in one required but inefficient tool;",
     "Coverage routing is fragile because 74\\% of its time sits in one required but inefficient tool;"),
    ("statistics $\\times3$, fitting $\\times1$, DP $\\times1$ & 71 & 0.908 \\\\",
     "statistics $\\times3$, fitting $\\times1$, DP $\\times1$ & 71 & 0.886 \\\\"),
    ("queueing $\\times15$                                      & 240 & 0.585 \\\\",
     "queueing $\\times15$                                      & 240 & 0.585 \\\\"),

    # ── P2 ──
    ("Efficiency ranges from 410.3 to 7.3 checks per second, a factor of 56.",
     "Efficiency ranges from 398.4 to 7.6 checks per second, a factor of 52."),
    ("Queueing            & 16 & 0.039 & 410.3 \\\\",
     "Queueing            & 16 & 0.040 & 398.4 \\\\"),
    ("Statistics          & 13 & 0.037 & 351.4 \\\\",
     "Statistics          & 13 & 0.039 & 333.5 \\\\"),
    ("Dynamic programming & 27 & 0.115 & 234.8 \\\\",
     "Dynamic programming & 27 & 0.113 & 238.9 \\\\"),
    ("Networks            & 14 & 0.113 & 123.9 \\\\",
     "Networks            & 14 & 0.117 & 119.4 \\\\"),
    ("MIP                 & 13 & 0.114 & 114.0 \\\\",
     "MIP                 & 13 & 0.114 & 113.8 \\\\"),
    ("Evaluation          & 5  & 0.114 & 43.9 \\\\",
     "Evaluation          & 5  & 0.112 & 44.6 \\\\"),
    ("Fitting             & 5  & 0.682 & 7.3 \\\\",
     "Fitting             & 5  & 0.656 & 7.6 \\\\"),

    # ── P2 贪婪表（换成最终数据）──
    ("""0.50 & 192 & 0.468 & \\textbf{196} & statistics $\\times4$, queueing $\\times9$ \\\\
0.585 & 237 & 0.583 & \\textbf{240} & queueing $\\times15$ \\\\
0.60 & 240 & 0.585 & 240 & queueing $\\times15$ \\\\
0.70 & 272 & 0.663 & \\textbf{285} & statistics $\\times1$, queueing $\\times17$ \\\\
0.75 & 304 & 0.741 & 304 & queueing $\\times19$ \\\\
0.80 & 320 & 0.780 & 320 & queueing $\\times20$ \\\\
1.00 & 400 & 0.975 & 400 & queueing $\\times25$ \\\\
1.20 & 480 & 1.170 & \\textbf{481} & statistics $\\times5$, queueing $\\times26$ \\\\""",
     """0.50 & 192 & 0.469 & 192 & queueing $\\times12$ \\\\
0.585 & 224 & 0.584 & 224 & queueing $\\times14$ \\\\
0.60 & 237 & 0.584 & \\textbf{240} & queueing $\\times15$ \\\\
0.70 & 272 & 0.679 & 272 & queueing $\\times17$ \\\\
0.75 & 288 & 0.719 & 288 & queueing $\\times18$ \\\\
0.80 & 320 & 0.799 & 320 & queueing $\\times20$ \\\\
1.00 & 397 & 0.992 & \\textbf{400} & queueing $\\times25$ \\\\
1.20 & 477 & 1.191 & \\textbf{480} & queueing $\\times30$ \\\\"""),
    ("""over eight budgets from
0.50 to $1.20$\\,s the greedy rule never loses more than 13 checks, and at $0.60$,
$0.75$, $0.80$ and $1.00$\\,s it attains the integer optimum exactly
(Table~\\ref{tab:greedy}). The rule fails only where the residual is awkward: at
$0.70$\\,s greedy buys 272 checks while the optimum mixes one statistics run into
seventeen queueing runs for 285, and at $0.50$\\,s it loses four. The gap is at most
4.6\\% and never larger, which is itself the finding: choosing between allocation
heuristics is worth far less than choosing the right objective.""",
     """over eight budgets from
0.50 to $1.20$\\,s the greedy rule never loses more than three checks, and at five
of the eight budgets it attains the integer optimum exactly
(Table~\\ref{tab:greedy}). The rule fails only where the residual is awkward: at
$0.60$\\,s greedy buys 237 checks while the optimum fits fifteen queueing runs for
240, and the same three-check gap reappears at $1.00$ and $1.20$\\,s. The gap is at
most 1.3\\%, which is itself the finding: choosing between allocation heuristics
is worth far less than choosing the right objective.

The gap is also not robust. On an earlier measurement --- ten runs per tool rather
than thirty, with a different set of timings --- the same experiment produced a
thirteen-check gap at $0.70$\\,s. The instability is the point: the allocation
problem is not where the difficulty lives, and a pipeline that spends its
optimisation effort here is optimising the wrong thing."""),

    # ── P3 ──
    ("$n$ needed for half-width $0.05$ & 353 \\\\",
     "$n$ needed for half-width $0.05$ & 355 \\\\"),
    ("Reaching a half-width of 0.05 would require 353 problems, sixteen times what has been\nrun.",
     "Reaching a half-width of 0.05 would require 355 problems, sixteen times what has been\nrun."),
    ("the 353\nfigure assumes the rate stays near 0.36", "the 355\nfigure assumes the rate stays near 0.36"),

    # ── P4 ──
    ("The plugin layer is 1.214\\,s.", "The plugin layer is 1.191\\,s."),
    ("The plugin layer is therefore \\textbf{4.8\\%} of the wall time",
     "The plugin layer is therefore \\textbf{4.7\\%} of the wall time"),
    ("Plugin layer (7 capabilities)   & 1.214\\,s & 4.8\\% \\\\",
     "Plugin layer (7 capabilities)   & 1.191\\,s & 4.7\\% \\\\"),
    ("Verification, excluding compile & 4.6\\,s   & 18\\% \\\\",
     "Verification, excluding compile & 4.6\\,s   & 18.3\\% \\\\"),
    ("Entropy weighting gives $[0.244, 0.490, 0.266]$, with cost dominating.",
     "Entropy weighting gives $[0.202, 0.403, 0.395]$: cost and timing variability\ndominate, and the check count barely matters."),
    ("""Dynamic programming & 0.887 & 1 & yes \\\\
Queueing            & 0.837 & 2 & yes \\\\
Networks            & 0.809 & 3 & yes \\\\
MIP                 & 0.799 & 4 & no \\\\
Statistics          & 0.788 & 5 & no \\\\
Evaluation          & 0.682 & 6 & no \\\\
Fitting             & 0.118 & 7 & no \\\\""",
     """Dynamic programming & 0.898 & 1 & yes \\\\
Networks            & 0.819 & 2 & yes \\\\
MIP                 & 0.816 & 3 & yes \\\\
Statistics          & 0.757 & 4 & no \\\\
Evaluation          & 0.746 & 5 & no \\\\
Queueing            & 0.644 & 6 & no \\\\
Fitting             & 0.327 & 7 & no \\\\"""),
    ("""The ranking is stable: perturbing any weight by $\\pm20\\%$ does not change the top
choice. It also deserves a caveat. Fitting ranks last by a wide margin, yet it is the
only capability that serves the second sub-problem; a ranking of capabilities is not a
ranking of requirements. The three that survive are the three that are efficient and
broad, which is the right answer to ``which three can I keep'' and the wrong answer to
``which three do I need''.""",
     """The ranking needs two caveats, and both matter more than the ranking itself.
First, it is not stable. The second and third places differ by 0.003, and re-running
the timing measurement swaps them; a $\\pm20\\%$ weight perturbation does not change
the top choice, but re-measuring the tools does change the second. Second, fitting
ranks last by a wide margin, yet it is the only capability that serves the second
sub-problem. A ranking of capabilities is not a ranking of requirements. The three
that survive are the three that are efficient and broad, which is the right answer
to ``which three can I keep'' and the wrong answer to ``which three do I need''.

The honest conclusion is narrower than the table suggests: dynamic programming is
the one capability to keep unambiguously; the other two are a coin toss between
network metrics and MIP that would be settled by more measurement rather than by
more analysis."""),

    # ── 结论 ──
    ("The plugin layer costs 1.214\\,s and accounts for 4.8\\% of the time a problem takes.\nSeven capabilities span a 56-fold range in verification efficiency,",
     "The plugin layer costs 1.191\\,s and accounts for 4.7\\% of the time a problem takes.\nSeven capabilities span a 52-fold range in verification efficiency,"),
    ("self-checks costs 0.908\\,s, and a 0.6\\,s budget buys 240 checks from a single tool.",
     "self-checks costs 0.886\\,s, and a 0.6\\,s budget buys 240 checks from a single tool."),
    ("computation, and the three capabilities most worth keeping are dynamic programming,\nqueueing and network metrics.",
     "computation, and the one capability most clearly worth keeping is dynamic\nprogramming, with network metrics and MIP tied behind it."),

    # ── 局限 ──
    ("The TOPSIS ranking depends on\nthe three criteria chosen; adding efficiency as a fourth criterion makes the top two\nindistinguishable (closeness 0.843 against 0.841) and the sensitivity analysis then\nreports a reversal, which is the honest signal that the criterion set is over-determined\nrelative to the spread in the data.",
     "The TOPSIS ranking depends on\nthe three criteria chosen, and on the timings themselves: the second and third\nplaces differ by 0.003, and an independent re-measurement of the same tools swaps\nthem. We report the ranking with that fragility attached rather than presenting it\nas settled."),
]


def main():
    t = open(P, encoding="utf-8").read()
    ok = miss = 0
    for old, new in REPL:
        if old in t:
            t = t.replace(old, new, 1)
            ok += 1
        else:
            miss += 1
            print("  [MISS] %s" % old[:70].replace("\n", " "))
    open(P, "w", encoding="utf-8", newline="\n").write(t)
    print("替换 %d 条，未命中 %d 条" % (ok, miss))
    return 1 if miss else 0


if __name__ == "__main__":
    raise SystemExit(main())
