"""收尾：修 4 处残留数字，并把三张图插入正文。"""
import os

P = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "out", "arch", "paper.tex")

FIX = [
    ("\\caption{TOPSIS ranking over three criteria. Entropy weights $[0.244, 0.490, 0.266]$.}",
     "\\caption{TOPSIS ranking over three criteria. Entropy weights $[0.202, 0.403, 0.395]$."),
    ("differ by a factor of 56 in verification efficiency",
     "differ by a factor of 52 in verification efficiency"),
    ("agent. The plugin layer is 4.8\\% of the wall time; compilation dominates.}",
     "agent. The plugin layer is 4.7\\% of the wall time; compilation dominates.}"),
    ("routing is fragile because 75\\% of its time sits in one required but inefficient tool;",
     "routing is fragile because 74\\% of its time sits in one required but inefficient tool;"),
]

FIG2 = r"""
\begin{figure}[htbp]
\centering
\includegraphics[width=0.88\textwidth]{fig_greedy.png}
\caption{Greedy allocation by efficiency against the integer optimum, over eight
time budgets. The two coincide at five of the eight and never differ by more than
three checks. An earlier ten-run measurement produced a thirteen-check gap at
$0.70$\,s, so even this small gap is not robust; the allocation problem is simply
not where the difficulty lives.}
\label{fig:greedy}
\end{figure}

"""

FIG3 = r"""
\begin{figure}[htbp]
\centering
\includegraphics[width=0.88\textwidth]{fig_rate.png}
\caption{Width of the 95\% Wilson interval for the failure rate as a function of
the number of problems run. At the 22 problems actually run the interval is
0.373 wide; a half-width of 0.05 would need 355.}
\label{fig:rate}
\end{figure}

"""

FIG4 = r"""
\begin{figure}[htbp]
\centering
\includegraphics[width=0.88\textwidth]{fig_topsis.png}
\caption{TOPSIS closeness for each capability over three criteria: self-check count
(benefit), cost (cost) and timing variability (cost). The top three are shaded.
The second and third differ by 0.003, so the cut between them is not resolved by
the data.}
\label{fig:topsis}
\end{figure}

"""

INS = [
    ("\\section{Problem 3: how well is the failure rate known?}", FIG2),
    ("\\section{Problem 4: the bottleneck}", FIG3),
    ("The honest conclusion is narrower than the table suggests:", FIG4),
]


def main():
    t = open(P, encoding="utf-8").read()
    for old, new in FIX:
        if old in t:
            t = t.replace(old, new, 1)
            print("  [OK]   %s" % old[:56].replace("\n", " "))
        else:
            print("  [MISS] %s" % old[:56].replace("\n", " "))
    for anchor, fig in INS:
        if anchor in t:
            t = t.replace(anchor, fig.lstrip("\n") + anchor, 1)
            print("  [FIG]   %s" % anchor[:52])
        else:
            print("  [MISS] anchor %s" % anchor[:52])
    open(P, "w", encoding="utf-8", newline="\n").write(t)
    print("done")


if __name__ == "__main__":
    main()
