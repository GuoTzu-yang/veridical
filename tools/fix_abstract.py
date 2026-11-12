import os
import re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(HERE, "out", "d2026c", "paper.tex")
s = open(p, encoding="utf-8").read()
i = s.find("\\begin{abstract}")
j = s.find("\\end{abstract}")
assert i > 0 and j > i
NEW = r"""\begin{abstract}
\small
\noindent
The audience vote on \emph{Dancing with the Stars} is never published. What is
published is who left, and when. We show that this is enough to bound the audience
vote but not to point-identify it, and that the size of the bound is itself the
answer to the certainty question.

We treat each week as a constrained inverse problem. The eliminated contestant is
observed; the audience shares are unknown; the combination rule supplies the
constraint. For a fixed week the constraint is linear in the shares, so the set of
audience votes consistent with the observed elimination is characterised in closed
form rather than searched, and its size is a direct certainty measure. We verify
the closed form against an independent sampling procedure, and the two agree on
all 231 season-weeks.

\textbf{Problem 1.} The percentage rule reproduces the observed elimination in 193
of 231 season-weeks (83.5\%), the ranking rule in 224 (97.0\%). The 38 failures are
not random: in 20 of them the eliminated contestant had the best or second-best
judge score, which is exactly the controversy pattern the problem names. Certainty
is low and it is uneven. In the median week the share of the audience vote
explained by the judge ranking is bounded only to within 0.494 of a possible range
of one, and the bound is systematically wider in early weeks, when more
contestants remain and one inequality per contestant must pin down more unknowns.

\textbf{Problem 2.} Applying both rules to the same reconstructed shares, the two
rules name different eliminated contestants in 136 of 193 weeks (70.5\%). In every
one of those disagreements the ranking rule eliminates the contestant with the
weaker judge score. The asymmetry is algebraic: the percentage rule preserves the
size of judge gaps, so a small gap can be overturned by audience support, whereas
the ranking rule reduces judge scores to an ordinal scale and cannot be overturned
as easily. The controversial contestants the problem names survive precisely
because their audience support is large in weeks where the percentage rule remains
consistent. Adding a judges' choice between the bottom two would move power to the
judges in exactly the 38 controversial weeks.

\textbf{Problem 3.} Judge score dominates placement, with a rank correlation of
$-0.943$. Age is associated with worse placement at $+0.443$, but this is not
established as independent of judge score, and we say so. Industry and partner
effects are reported descriptively only, because several categories contain a
single contestant.

\textbf{Problem 4.} Sweeping the audience weight shows strong asymmetry: lowering
it from 0.5 to 0.4 changes no champion in 34 seasons, while raising it to 0.7
changes 5. We recommend retaining the percentage rule at equal weight, and we
propose using the unused slack for excitement rather than for outcome: when judges
agree closely, let the audience break the bottom-two tie; when they disagree
sharply, keep the judges' judgment.

"""
s = s[:i] + NEW + s[j:]
open(p, "w", encoding="utf-8", newline="\n").write(s)
words = len(re.sub(r"\\[a-zA-Z]+\{[^}]*\}", "", NEW).split())
print("  abstract 重写，约 %d 词（含 LaTeX 命令）" % words)