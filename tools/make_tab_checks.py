"""生成论文表 A：22 项检查（英文说明由我写，状态现场取）。

为什么不用 gate 的原始 detail：那是中文串，而论文用 pdflatex 编译（不支持 CJK）。
说明按检查的**意图**写，状态列仍由现场数据填 —— 数字不手抄。
"""
import io
import json
import os
import subprocess
import sys

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
OUT = os.path.join(HERE, "out", "final")
PY = sys.executable

# id -> (英文说明, 说明这条在防什么)
DESC = {
    "causal": ("a causal assertion names an identification strategy",
               "correlation rewritten as causation with every check green"),
    "stamp": ("the verdict is bound to the digests of the files it judged",
              "a verdict about a file that has since changed"),
    "compile": ("builds without error", "a paper that does not compile is not a paper"),
    "pdf": ("a PDF exists and has pages", "silent failure to ship"),
    "code": ("the disclosure modules import", "claimed reproducibility that does not run"),
    "numbers": ("decimals trace to a computed artifact", "invented numbers"),
    "rules": ("formatting and section rules", "unreadable layout"),
    "rules_apmcm": ("competition-specific rules", "submission-format rejection"),
    "abstract": ("abstract names its quantities", "an abstract with no numbers"),
    "abs_page": ("abstract ends on page one", "a slow opening"),
    "bare_pct": ("percentages carry a base", "'40% better' with no denominator"),
    "refs": ("every citation resolves", "phantom references"),
    "rigor": ("statistical claims carry n and a test", "significance without a sample"),
    "domain": ("the response is physically admissible", "modelling a non-response"),
    "required": ("required evidence per problem part", "an unanswered sub-question"),
    "leakage": ("no predictor is the response in disguise", "a tautological fit"),
    "math": ("symbols are defined and used", "notation drift"),
    "innovation": ("a stated delta against a baseline", "a report with no claim"),
    "ai_taste": ("no template phrasing", "prose a referee recognises as generated"),
    "claims": ("claims are listed and traceable", "conclusions from nowhere"),
    "cross": ("sections do not contradict", "two answers to one question"),
    "figures": ("figures exist, are legible and captioned", "decoration instead of evidence"),
    "falsify": ("claims survived counterexample search", "a claim that reverses locally"),
    "extrap": ("extrapolation boundary is declared", "a straight line past its domain"),
    # 第 111/112 轮新增的五项：五件事 + 分板块红队
    "analysis": ("the object is decomposed into classes with different sources",
                 "an analysis that only restates the problem"),
    "method_argument": ("each method names its rejected alternative and what would overturn it",
                        "a feature list presented as an argument"),
    "self_correction": ("errors are documented as cases: wrong, found, changed, justified",
                        "a fix justified only by a green light"),
    "deployment": ("run modes, time budget and failure playbook are stated",
                   "a method that cannot be operated"),
    "redteam": ("seven distinct specialists answered their own probes, findings closed",
                "one generalist red team that misses whole boards"),
}

code = subprocess.run(
    [PY, "-c",
     "import sys;sys.path.insert(0,'.');import gate,json;"
     "r=gate.run_all('out/runs/queueing');"
     "print(json.dumps([{'id':c['id'],'tier':c['tier'],"
     "'status':c['status']} for c in r['checks']],ensure_ascii=False))"],
    capture_output=True, text=True, encoding="utf-8", errors="replace",
    cwd=HERE)
checks = json.loads(code.stdout)


def esc(s):
    return (s.replace("_", r"\_").replace("%", r"\%")
             .replace("&", r"\&").replace("#", r"\#"))


L = [r"\begin{longtable}{@{}llL{5.0cm}L{4.4cm}@{}}",
     r"\toprule",
     r"Check & Tier & What it verifies & What it exists to catch \\",
     r"\midrule", r"\endhead"]
for c in checks:
    d, why = DESC.get(c["id"], ("(undocumented)", ""))
    # id 也要转义：rules_apmcm 里的下划线在文本模式下非法（第 109 轮踩过）
    L.append(r"\code{%s} & %s & %s & %s \\" % (
        esc(c["id"]), "hard" if c["tier"] == "hard" else "soft",
        esc(d), esc(why)))
L += [r"\bottomrule", r"\end{longtable}"]
io.open(os.path.join(OUT, "tab_checks.tex"), "w", encoding="utf-8",
        newline="\n").write("\n".join(L) + "\n")
missing = [c["id"] for c in checks if c["id"] not in DESC]
print("tab_checks.tex 已写；未写说明的 id:", missing or "无")
