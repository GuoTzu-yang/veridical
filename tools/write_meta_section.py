"""把评审要的三件测量写进论文：时间口径 / 机制消融 / 失败清单（第 113 轮）。

生成两张表 + 插入一节。所有数字取自 out/final/meta_eval.json，
正文不手抄任何数值。
"""
import io
import json
import os

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
OUT = os.path.join(HERE, "out", "final")
M = json.load(io.open(os.path.join(OUT, "meta_eval.json"), encoding="utf-8"))

# ── 表：逐段时间 ───────────────────────────────────────────────────
L = [r"\begin{tabular}{@{}rlrr@{}}", r"\toprule",
     r"Step & Command & Seconds & Exit \\", r"\midrule"]
# 步骤名的英文标签（pdflatex 不支持 CJK，表里不能出现中文）
EN = {"1": "declare type + objectives", "2": "structure horse race",
      "3": "partial-correlation hints", "4": "outline the rewrite points",
      "5": "draw one figure", "6": "trace the numbers",
      "7": "counterexample search", "8": "eight channels + veto",
      "9": "the gate"}
for t in M["timing"]:
    name = EN.get(t["step"], t["step"]).replace("_", r"\_")
    L.append(r"%s & %s & %.2f & %d \\" % (t["step"], name, t["seconds"], t["exit"]))
L += [r"\midrule",
      r"\multicolumn{2}{@{}l}{total, wall clock} & %.2f & \\" % M["timing_total_s"],
      r"\bottomrule", r"\end{tabular}"]
io.open(os.path.join(OUT, "tab_timing.tex"), "w", encoding="utf-8",
        newline="\n").write("\n".join(L) + "\n")

# ── 表：机制消融（三项）────────────────────────────────────────────
ft = M["ablation"]["frozen_table"]
fa = M["ablation"]["falsify"]
st = M["ablation"]["stamp"]
rows = [
    (r"Frozen provenance table",
     r"tracing falls from %s\,\%% to %s\,\%% on five problems" % (
         "/".join("%.1f" % x for x in ft["with_pct"]),
         "/".join("%.1f" % x for x in ft["without_pct"])),
     r"the artifact, not the care"),
    (r"Counterexample search",
     r"runs in %.2f\,s and reports a reversal of the sign claim" % fa["seconds"]
     if fa["reports_reversal"] else r"runs but finds no reversal here",
     r"a local claim that a global coefficient hides"),
    (r"Digest-bound stamp",
     r"editing the source after a verdict turns the check from pass to fail",
     r"a verdict that outlives its object"),
]
L = [r"\begin{tabular}{@{}L{3.2cm}L{6.4cm}L{4.2cm}@{}}", r"\toprule",
     r"Mechanism removed & Measured effect & What it would otherwise hide \\",
     r"\midrule"]
for a, b, c in rows:
    L.append(r"%s & %s & %s \\" % (a, b, c))
L += [r"\bottomrule", r"\end{tabular}"]
io.open(os.path.join(OUT, "tab_mech.tex"), "w", encoding="utf-8",
        newline="\n").write("\n".join(L) + "\n")

# ── 插入一节 ───────────────────────────────────────────────────────
P = os.path.join(OUT, "paper.tex")
s = io.open(P, encoding="utf-8").read()
anchor = r"\subsection{Sensitivity: is the effect attributable to the mechanism?}"
add = (r"""\subsection{Time, and what a speed claim is worth}
\label{sec:timing}

Reports of this work tend to lead with elapsed minutes, and a number like ``a
paper in eighteen minutes'' cannot be checked: it bundles reading the problem,
deciding what to model, writing the prose, and fixing what the checks reject.
Only part of that is measurable. Table~\ref{tab:timing} therefore reports the
nine verified commands and nothing else: %0.2f seconds in total on one machine,
with the slowest step --- the full gate --- at %0.2f seconds. Everything a
reader would call \emph{writing} is excluded, and we make no claim about it.

The useful consequence is not speed but frequency: at this cost the whole
verification chain fits inside a single edit-compile cycle, so it can run on
every draft rather than once at the end. A check that is cheap enough to run
always is a different object from a check that is run once.

\begin{table}[t]
\centering
\small
\caption{The nine verified commands, timed end to end. Step~6 returns 1 by
design: it reports untraced numbers rather than failing to run. Prose writing is
excluded and is not measured anywhere in this paper.}
\label{tab:timing}
\input{tab_timing.tex}
\end{table}

\subsection{What each mechanism is worth}

A mechanism that is present in every paper cannot be credited by counting
successes. Table~\ref{tab:mech} removes three of them in turn and reports what
moves. The provenance table is the strongest: with it, %s\,\%% of numeric tokens
resolve; without it, %s\,\%%. The counterexample search changes no aggregate, and
that is the point --- it acts on individual claims, so its effect is a specific
reversal rather than a percentage. The stamp changes no content at all; it
changes whether a verdict is still about the file it names.

A comparison we cannot make, and do not pretend to: human team against tool
team on the same problem, scored by an independent rater. That would need a
second author and a rater who is not us. The ablation substitutes for it in one
respect only --- it shows the mechanism is what produces the number --- and
substitutes for nothing else.

\begin{table}[t]
\centering
\small
\caption{Three mechanisms removed in turn. Effects are measured outputs, not
scores: this paper reports no score comparison, because there is no independent
rater.}
\label{tab:mech}
\input{tab_mech.tex}
\end{table}

""" % (M["timing_total_s"],
       max(t["seconds"] for t in M["timing"]),
       "%.1f" % min(ft["with_pct"]), "%.1f" % max(ft["without_pct"]),) + anchor)
assert anchor in s
if "Time, and what a speed claim is worth" not in s:
    s = s.replace(anchor, add, 1)
    io.open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("已插入「时间口径 + 机制消融」小节")

print("tab_timing.tex / tab_mech.tex 已写")
print("时间合计 %.2fs；消融 %s -> %s" % (
    M["timing_total_s"],
    "/".join("%.1f" % x for x in ft["with_pct"]),
    "/".join("%.1f" % x for x in ft["without_pct"])))
