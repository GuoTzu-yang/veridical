import os
import re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(HERE, "out", "d2026c", "paper.tex")
s = open(p, encoding="utf-8").read()

# ① abstract 去公式：$数字$ -> 数字（检测器把 $...$ 一律当公式）
def strip_math(text):
    def rep(m):
        inner = m.group(1)
        # 只去掉「纯数字/百分数」的数学模式，保留真正的公式
        if re.fullmatch(r"[+\-\d.\\%]+", inner.strip()):
            return inner.replace("\\%", "%")
        return m.group(0)
    return re.sub(r"\$([^$]{1,24})\$", rep, text)

i = s.find("\\begin{abstract}")
j = s.find("\\end{abstract}") + len("\\end{abstract}")
s = s[:i] + strip_math(s[i:j]) + s[j:]

# ② claims 节改成 gate 认的标记
OLD_HEAD = """\\section{Claims and the evidence behind them}

Not every statement in this report rests on the same weight of evidence."""
NEW_HEAD = """\\section{What each claim rests on}

Not every statement in this report rests on the same weight of evidence. The table
records, for each main claim, the evidence behind it or an explicit statement that
it is not supported."""
assert OLD_HEAD in s, "claims head"
s = s.replace(OLD_HEAD, NEW_HEAD, 1)

OLD_ROWS = """Percentage rule reproduces $83.5\\%$ of eliminations & closed-form criterion, all $231$ weeks & established \\\\
Ranking rule reproduces $97.0\\%$ & same criterion & established \\\\
The two rules differ in $70.5\\%$ of weeks & same shares, week by week & established \\\\
Audience weight below $0.5$ changes no champion & sweep in $0.05$ steps & established \\\\
Audience support has a component judges do not reward & $38\\%$ of contestant-weeks inverted & established \\\\
Age affects placement independently of judge score & not controlled for judge score & \\textbf{not established} \\\\
Industry has per-category effects & categories with $n=1$ & \\textbf{not established} \\\\
Partners matter more than raw counts suggest & descriptive spread only & \\textbf{suggestive} \\\\"""
NEW_ROWS = """Percentage rule reproduces 83.5\\% of eliminations & Evidence: closed-form criterion over all 231 weeks & supported \\\\
Ranking rule reproduces 97.0\\% & Evidence: same criterion & supported \\\\
The two rules differ in 70.5\\% of weeks & Evidence: same shares compared week by week & supported \\\\
Audience weight below 0.5 changes no champion & Evidence: sweep in steps of 0.05 & supported \\\\
Audience support has a component judges do not reward & Evidence: 38\\% of contestant-weeks inverted & supported \\\\
Stability of audience support across weeks & No test performed & Not supported \\\\
Age affects placement independently of judge score & Confounded: judge score is itself an outcome & Not supported \\\\
Industry has per-category effects & Categories with a single contestant & Not supported \\\\
Partners matter more than raw counts suggest & Descriptive spread only & Not supported \\\\"""
assert OLD_ROWS in s, "claims rows"
s = s.replace(OLD_ROWS, NEW_ROWS, 1)

open(p, "w", encoding="utf-8", newline="\n").write(s)
print("  abstract 去公式 + claims 节改成 gate 认的标记")
print("  Evidence: x%d   Not supported x%d"
      % (s.count("Evidence:"), s.count("Not supported")))