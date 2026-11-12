import io
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(HERE, "out", "d2026c", "paper.tex")
s = open(p, encoding="utf-8").read()

OLD1 = ("""Third, the two rules mostly agree ---
they produce the same elimination order in $24$ of $34$ seasons --- but they
disagree in a systematic direction, because the percentage rule rescales judge
scores to the unit interval while the ranking rule does not.""")
NEW1 = ("""Third, the two rules are far from
interchangeable: on the same reconstructed shares they name different eliminated
contestants in $136$ of $193$ season-weeks ($70.5\\%$), and in every one of those
$136$ disagreements the ranking rule eliminates the contestant with the weaker
judge score. The ranking rule is systematically more favourable to the judges,
because the percentage rule rescales judge scores to a common range while the
ranking rule discards the size of the judge gaps.""")
assert OLD1 in s, "abstract block not found"
s = s.replace(OLD1, NEW1, 1)

OLD2 = ("""Applying both rules to the reconstructed shares, the two rules produce the same
elimination order in $24$ of $34$ seasons and different orders in the remaining
$10$. They agree most of the time, so a blanket claim that one rule ``favours the
audience'' would be too strong. But the disagreement is not symmetric. In the
weeks where they disagree, the ranking rule eliminates the contestant with the
weaker judge score more often, because it cannot let a large audience share
compensate as far as the percentage rule can.""")
NEW2 = ("""Applying both rules to the same reconstructed shares, week by week, the two
rules name the same eliminated contestant in $57$ of $193$ season-weeks
($29.5\\%$) and different ones in the remaining $136$ ($70.5\\%$). Agreement is
therefore the exception, not the rule: an equal-weight percentage rule and an
equal-weight ranking rule are genuinely different systems, and describing one as
a rescaling of the other would be wrong.

The direction of the disagreement is not symmetric. In all $136$ weeks where the
rules disagree, the contestant the ranking rule eliminates is the one with the
weaker judge score. This is what the algebra predicts: the ranking rule converts
judge scores to an ordinal scale, so a contestant who is marginally the worst
with the judges cannot be rescued by a large audience share, whereas the
percentage rule preserves the size of the judge gap and therefore permits a
rescue when the gap is small.""")
assert OLD2 in s, "p2 block not found"
s = s.replace(OLD2, NEW2, 1)

OLD3 = ("""\\textbf{Answer to Problem 2, first part.} The rules agree in $24$ of $34$ seasons.
Where they differ, the percentage rule favours audience support and the ranking
rule favours judge scores.""")
NEW3 = ("""\\textbf{Answer to Problem 2, first part.} The rules differ in $70.5\\%$ of weeks
($136$ of $193$). The difference is one-directional: in every disagreement the
ranking rule eliminates the contestant with the weaker judge score, so the
percentage rule is the rule that gives audience support more room.""")
assert OLD3 in s, "answer block not found"
s = s.replace(OLD3, NEW3, 1)

open(p, "w", encoding="utf-8", newline="\n").write(s)
print("  论文已改：三处 24/34 -> 57/193 与 136/193")