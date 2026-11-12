import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()

# 纯字符串替换（不用正则 —— \section 里的 \s 会被当成空白类）
PAIRS = [
    ('r"\\section{Limitations}"',
     '"\\\\section{" + _i18n.sec(_lang, "limitations") + "}"'),
    ('r"\\section{Introduction}"',
     '"\\\\section{" + _i18n.sec(_lang, "intro") + "}"'),
    ('r"\\section{Assumptions and Notations}"',
     '"\\\\section{" + _i18n.sec(_lang, "assumptions") + "}"'),
    ('r"\\section{Mechanistic basis}"',
     '"\\\\section{" + _i18n.sec(_lang, "mech") + "}"'),
    ('r"\\section{Problem 2: Design selection under constraints}"',
     '"\\\\section{" + _i18n.sec(_lang, "p2") + "}"'),
    ('r"\\section{Problem 3: How stable are the conclusions?}"',
     '"\\\\section{" + _i18n.sec(_lang, "p3") + "}"'),
    ('r"\\section{Problem 5: Can this design be manufactured?}"',
     '"\\\\section{" + _i18n.sec(_lang, "p5") + "}"'),
    ('r"\\section{Evaluation}"',
     '"\\\\section{" + _i18n.sec(_lang, "eval") + "}"'),
    ('r"\\section{AI Disclosure and Human Verification}"',
     '"\\\\section{" + _i18n.sec(_lang, "disclosure") + "}"'),
    ('r"\\section{Core Code}"',
     '"\\\\section{" + _i18n.sec(_lang, "code") + "}"'),
]
n = 0
for old, new in PAIRS:
    if old in s:
        s = s.replace(old, new, 1)
        n += 1
    else:
        print("  [miss] %s" % old[:52])
print("  replaced %d" % n)

# p4 跨两行
OLD4 = ('r"\\section{Problem 4: Does the choice survive a change of "\n'
        '              r"priorities?}"')
if OLD4 in s:
    s = s.replace(OLD4,
                  '"\\\\section{" + _i18n.sec(_lang, "p4") + "}"', 1)
    print("  patched p4")
else:
    i = s.find("Problem 4: Does the choice survive")
    print("  [miss p4] 实际上下文:")
    print("   ", repr(s[max(0, i - 90):i + 90]))

ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  done")