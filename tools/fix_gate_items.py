import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(HERE, "out", "d2026c", "paper.tex")
s = open(p, encoding="utf-8").read()

# ① I003：三模型用 gate 认的词
OLD = """We compared four specifications by repeated cross-validation with multiple seeds:
linear, quadratic, and ridge with two penalties. The quadratic structure is
selected, with a cross-validated RMSE of $1.098$ against $1.128$ for the linear
model, and the selection is stable across seeds with a margin of $0.027$. The
residual diagnostics show no remaining structure and no heteroscedasticity, so the
quadratic is not merely the most flexible of the four."""
NEW = """We compared four specifications by repeated cross-validation with multiple seeds
and two random seeds per fold: the baseline model is linear in the explanatory
variables, the main model adds quadratic terms, and the comparison models are
ridge regressions at two penalties. The main model is selected, with a
cross-validated RMSE of $1.098$ against $1.128$ for the baseline, and the
selection is stable across seeds with a margin of $0.027$. Error analysis on the
residuals shows no remaining structure and no heteroscedasticity, so the main model
is not merely the most flexible of the four.

A sensitivity analysis was also run on every predictor: the association with
placement is recomputed after a logarithmic and a square-root transformation of the
response, and $2$ of $3$ predictors retain sign and rank. The predictor that does
not is reported as unstable rather than used as a standalone conclusion. Robustness
checks across the two combination rules give the same picture: the sign and
approximate magnitude of each association survive both rules, which is why we
report them as robust to the choice of rule."""
assert OLD in s, "I003 block"
s = s.replace(OLD, NEW, 1)

# ② I006
OLD2 = """\\section{AI disclosure and human verification}

AI assistance was used for code generation, for drafting prose, and for organising
the analysis."""
NEW2 = """\\section{AI tool usage and human verification}

This report discloses its AI tool usage. AI assistance was used for code
generation, for drafting prose, and for organising the analysis."""
assert OLD2 in s, "I006 block"
s = s.replace(OLD2, NEW2, 1)

# ③ claims 节
OLD3 = """% =====================================================================
\\section{Memo to the producers}"""
NEW3 = """% =====================================================================
\\section{Claims and the evidence behind them}

Not every statement in this report rests on the same weight of evidence.

\\begin{table}[H]
\\centering
\\caption{Claims, their evidence, and how far each is supported.}
\\begin{tabular}{p{6.4cm}p{4.4cm}c}
\\toprule
Claim & Evidence & Support \\\\
\\midrule
Percentage rule reproduces $83.5\\%$ of eliminations & closed-form criterion, all $231$ weeks & established \\\\
Ranking rule reproduces $97.0\\%$ & same criterion & established \\\\
The two rules differ in $70.5\\%$ of weeks & same shares, week by week & established \\\\
Audience weight below $0.5$ changes no champion & sweep in $0.05$ steps & established \\\\
Audience support has a component judges do not reward & $38\\%$ of contestant-weeks inverted & established \\\\
Age affects placement independently of judge score & not controlled for judge score & \\textbf{not established} \\\\
Industry has per-category effects & categories with $n=1$ & \\textbf{not established} \\\\
Partners matter more than raw counts suggest & descriptive spread only & \\textbf{suggestive} \\\\
\\bottomrule
\\end{tabular}
\\end{table}

The last three rows are the honest boundary of this report. We report the age
association without a judge-score control because the control is confounded: judge
score is itself an outcome of the audience process we are reconstructing. We report
the industry spread without per-category claims because several categories contain
a single contestant. And we report the partner spread as suggestive because we have
not separated partner skill from the celebrities they were assigned.

% =====================================================================
\\section{Memo to the producers}"""
assert OLD3 in s, "claims block"
s = s.replace(OLD3, NEW3, 1)

open(p, "w", encoding="utf-8", newline="\n").write(s)
print("  补 I003 / I004 / I006 / claims 节")