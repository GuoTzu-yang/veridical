"""把 chapters.selftest 的「合格样本」换成真有结构的迷你论文（第 118 轮）。

原来那版是堆词的，已经被反糊弄判据否掉 —— 说明判据有效，但也说明
「合格样本」必须换成真结构，否则自检永远红。
"""
import io

P = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch\chapters.py"
s = io.open(P, encoding="utf-8").read()

i = s.index("    good = (")
j = s.index('    io.open(os.path.join(td3, "paper.tex"), "w", encoding="utf-8").write(good)')

GOOD = [
    r"\begin{document}",
    r"\section{Analysis of the problem}",
    ("We decompose the object into five classes; the classification is an "
     "anatomy of the object and we ask where does each number come from. "
     "The structural, configuration, temporal, tabulated and computed classes "
     "differ in what a checker can ask, which is why the decomposition decides "
     "where checks go."),
    r"\begin{table}\centering\begin{tabular}{@{}ll}",
    r"Class & Source \\",
    r"structural & layout \\",
    r"configuration & method \\",
    r"temporal & input \\",
    r"computed & artifact \\",
    r"\end{tabular}\end{table}",
    r"\section{Method and why}",
    ("Each mechanism carries a rejected alternative; we explain why this rather "
     "than that, and what would change our mind before we kept it."),
    r"\begin{table}\centering\begin{tabular}{@{}lll}",
    r"Mechanism & Rejected alternative & Why \\",
    r"freeze & inline quotes & checkable \\",
    r"classify & trace all & inflation \\",
    r"veto & score & outvoting \\",
    r"\end{tabular}\end{table}",
    r"\section{What was wrong}",
    r"\subsection{Case 1: the tokenizer}",
    ("It was wrong; how found: a count of 199 against 1293; the change; why "
     "this is right, because the count moved while the reports did not."),
    r"\subsection{Case 2: the gate}",
    ("Wrong again; how found: a paper with zero citations passed; the change; "
     "why this is right, because a check must be able to fail on its object."),
    r"\section{Deployment}",
    ("Three modes, a playbook, a time budget and a cost that separates machine "
     "time from editorial time; the failure table is the part that gets used."),
    r"\begin{table}\centering\begin{tabular}{@{}ll}",
    r"Mode & Cost \\",
    r"cli & none \\",
    r"service & a daemon \\",
    r"ci & a stamp \\",
    r"\end{tabular}\end{table}",
    r"\end{document}",
]

body = "    good = (\n" + "".join(
    "        " + repr(line) + " +\n" for line in GOOD[:-1]) + \
    "        " + repr(GOOD[-1]) + ")\n"

s = s[:i] + body + s[j:]
io.open(P, "w", encoding="utf-8", newline="\n").write(s)
print("合格样本已换成 %d 行真结构" % len(GOOD))
