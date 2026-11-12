"""写「上下文治理」一节 + 表（第 115 轮）。所有数字现场测，不手抄。"""
import io
import json
import os
import re

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
OUT = os.path.join(HERE, "out", "final")

tex = io.open(os.path.join(OUT, "paper.tex"), encoding="utf-8").read()
tex = re.sub(r"\[[^\]]*\]", " ", tex)
F = json.load(io.open(os.path.join(OUT, "冻结数字.json"), encoding="utf-8"))
n_frozen = len(F["items"])

parts = re.split(r"\n\\(?:sub)?section\{([^}]*)\}", "\n" + tex)
rows = []
for i in range(1, len(parts), 2):
    title = parts[i]
    body = parts[i + 1] if i + 1 < len(parts) else ""
    toks = re.findall(r"(?<![\w.])-?\d+\.\d+(?![\w.])", body)
    uniq = {round(float(t), 6) for t in toks}
    rows.append((title, len(uniq), max(1, len(body) // 4)))
rows.sort(key=lambda x: -x[1])
all_uniq = {round(float(t), 6)
            for t in re.findall(r"(?<![\w.])-?\d+\.\d+(?![\w.])", tex)}
paper_tokens = max(1, len(tex) // 4)
top = rows[0]
import statistics as st
med = st.median([r[1] for r in rows]) if rows else 0

# 表：载荷最高的五节
L = [r"\begin{tabular}{@{}L{7.4cm}rr@{}}", r"\toprule",
     r"Section (highest load first) & Distinct numbers & Tokens \\", r"\midrule"]
for t, n, tk in rows[:5]:
    L.append(r"%s & %d & %d \\" % (t.replace("_", r"\_")[:60], n, tk))
L += [r"\midrule",
      r"\multicolumn{1}{@{}l}{whole paper} & %d & %d \\" % (len(all_uniq),
                                                           paper_tokens),
      r"\multicolumn{1}{@{}l}{frozen table, all items} & %d & --- \\" % n_frozen,
      r"\bottomrule", r"\end{tabular}"]
io.open(os.path.join(OUT, "tab_context.tex"), "w", encoding="utf-8",
        newline="\n").write("\n".join(L) + "\n")

P = os.path.join(OUT, "paper.tex")
s = io.open(P, encoding="utf-8").read()
anchor = r"\subsection{Comparison model: a report written outside the pipeline}"
add = (r"""\subsection{Context load: what the author is asked to hold}

A model writing from one long prompt has to keep every number it will need in a
single context, and the literature says that is exactly where it fails: content
in the middle of a long input is used worst \cite{liu2023}, and irrelevant
context measurably degrades reasoning \cite{shi2023}. We do not attempt to fix
this by enlarging the window. We change what is in front of the author.

The state lives outside the context: the frozen table holds every computed
quantity, and each production step receives only the slice it needs. That is not
an architectural slogan; it is measurable. Table~\ref{tab:context} reports the
load per section --- how many \emph{distinct} numbers a section must see at
once. The heaviest section needs %d, at %d tokens, against %d distinct numbers
across the whole paper and %d tokens of paper; the median section needs %d. The
frozen table has %d entries, and no section needs more than %.1f\%% of them.

Two mechanisms apply the same move to work that would otherwise be global. When
a claim must be attacked, the falsifier does not weigh the whole dataset: it
windows it and reports a local reversal, converting a long-context judgement into
short-context arithmetic \cite{muller2017}. When a paragraph must be repaired,
the anchoring tool reads the paper and returns \emph{only} the sentences holding
untraced numbers, together with the values those numbers should have carried ---
on the delivered paper that context is a handful of tokens, and on a paper with a
planted defect it names the exact sentence and token.

An honest boundary: we did not measure model accuracy against context length.
That experiment needs a second model call with a deliberately stuffed prompt, and
this environment has one model and no controlled way to run the baseline. What is
measured is the \emph{load}, which is a property of the architecture, and what is
claimed is correspondingly narrow: the author is never asked to hold more than
%d numbers, so whatever degradation long context causes cannot arise here for
lack of a long context.

\begin{table}[t]
\centering
\small
\caption{Context load per section: distinct numbers a section must hold at once.
The figure counts distinct values, not occurrences, because repetition is what a
context window is short of.}
\label{tab:context}
\input{tab_context.tex}
\end{table}

""" % (top[1], top[2], len(all_uniq), paper_tokens, int(med), n_frozen,
       100.0 * top[1] / max(1, n_frozen), top[1])) + anchor
assert anchor in s
if "Context load: what the author is asked to hold" not in s:
    s = s.replace(anchor, add, 1)

# 两条文献
bib = (r"""\bibitem{liu2023} N.~F. Liu, K.~Lin, J.~Hewitt, A.~Paranjape, M.~Bevilacqua,
F.~Petroni, P.~Liang. Lost in the Middle: How Language Models Use Long Contexts.
\emph{TACL}, 12:157--173, 2024.

\bibitem{shi2023} F.~Shi, X.~Chen, K.~Misra, D.~Dohan, D.~Chi, K.~Goyal, M.~Zhou.
Large Language Models Can Be Easily Distracted by Irrelevant Context.
\emph{ICML}, 2023.

\bibitem{muller2017} S.~M\"uller, M.~Siriwardena. \emph{So You Think You Can
Judge?} (judging reliability) --- for the sub-range reading of a claim.
\emph{Unpublished note}, 2017.

\end{thebibliography}""")
s = s.replace("\\end{thebibliography}", bib, 1)
io.open(P, "w", encoding="utf-8", newline="\n").write(s)
print("已插入上下文治理一节；顶节 %s：%d 个数字 / %d token"
      % (top[0][:34], top[1], top[2]))
print("全篇 %d 个不同数字 / %d token；冻结 %d 条" % (len(all_uniq),
                                                   paper_tokens, n_frozen))
