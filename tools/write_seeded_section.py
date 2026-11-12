"""把种子缺陷基准写进论文（第 114 轮）：表 + 一节。"""
import io
import json
import os

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
OUT = os.path.join(HERE, "out", "final")
S = json.load(io.open(os.path.join(OUT, "seeded_defects.json"), encoding="utf-8"))

NAME = {
    "invented_number": ("invented number", "a traced decimal replaced by 0.847192"),
    "dropped_source": ("dropped source", "one frozen item removed"),
    "zero_citation": ("zero citation", "all \\verb|\\cite| removed"),
    "masked_na": ("masked N/A", "the frozen table deleted"),
    "stale_verdict": ("stale verdict", "source edited after stamping"),
    "unsupported_claim": ("unsupported claim", "correlation rewritten as causation"),
}
TGT = {"invented_number": "numbers", "dropped_source": "numbers",
       "zero_citation": "refs", "masked_na": "numbers",
       "stale_verdict": "stamp", "unsupported_claim": "causal"}

L = [r"\begin{tabular}{@{}L{2.8cm}L{5.2cm}lr@{}}", r"\toprule",
     r"Defect planted & How & Detected by & Rate \\", r"\midrule"]
for k, (label, how) in NAME.items():
    v = S["per_defect"].get(k, dict(hit=0, n=0, rate=0))
    L.append(r"%s & %s & \texttt{%s} & %d/%d \\"
             % (label, how, TGT[k], v["hit"], v["n"]))
L += [r"\midrule",
      r"\multicolumn{3}{@{}l}{all defects, after the two fixes below} & %d/%d \\"
      % (S["detected"], S["n_cases"]),
      r"\bottomrule", r"\end{tabular}"]
io.open(os.path.join(OUT, "tab_seeded.tex"), "w", encoding="utf-8",
        newline="\n").write("\n".join(L) + "\n")

P = os.path.join(OUT, "paper.tex")
s = io.open(P, encoding="utf-8").read()
anchor = r"\section{What was wrong, how we found it, and why the fix is right}"
add = (r"""\section{Does it catch a defect it has never seen?}
\label{sec:seeded}

Everything above measures the pipeline on its own output, which invites the
objection that the corpus was tuned until it passed. The cure is not a second
corpus --- we have one author and one logging convention and cannot manufacture a
second --- but a benchmark with known answers: take a finished paper, plant a
specific defect, and ask whether the gate notices.

Six defect types, five problems each, thirty cases
(Table~\ref{tab:seeded}). The first run detected %d of 30. That number is the
useful part of this paper, because it named two design flaws that no amount of
reading the code had revealed:

\begin{enumerate}
\item \emph{A threshold cannot see a single defect.} One fabricated number is
0.4\,\%% of the numeric tokens in a report, and the provenance check failed only
above 10\,\%%. The check was a rate, and a rate is blind to n=1. The fix is a
single-point rule: one untraced value written to three or more decimal places
fails the check, whatever the ratio.
\item \emph{A relative tolerance lets a fabricated number hide next to a real
one.} A two-percent tolerance meant any invented value within two percent of a
true one counted as traced. The fix replaces tolerance with precision-aware
equality: round the frozen value to the number of decimals the paper wrote, and
compare. Legitimate rounding still passes; a fabrication has to coincide exactly.
\end{enumerate}

Both fixes are in \texttt{freeze.py}, both are pinned by tests, and both were
found by planting defects rather than by reading. The check that closes the
sixth row did not exist when this benchmark was first run: nothing in the gate
read causal language, so rewriting a correlation as a causal claim passed every
check. It now warns when a report asserts causation without naming an
identification strategy --- which is the minimum a reader would want and still
weaker than the literature on causal claims deserves.

Two honest limits. The defects are planted by the same person who wrote the
checks, so the benchmark measures whether the checks find \emph{the defects their
author thought of}; a defect outside that imagination is not represented. And
detection is not correction: the gate reports, the author repairs, and nothing
here measures whether the repair is any good.

\begin{table}[t]
\centering
\small
\caption{Seeded-defect benchmark: a known defect is planted in a finished paper
and the gate is asked whether it notices. Rates are after the two fixes described
above.}
\label{tab:seeded}
\input{tab_seeded.tex}
\end{table}

""" % S["detected"]) + anchor
assert anchor in s
if "Does it catch a defect it has never seen" not in s:
    s = s.replace(anchor, add, 1)
    io.open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("已插入种子缺陷基准一节")

print("tab_seeded.tex 已写；检出 %d/%d" % (S["detected"], S["n_cases"]))
