import ast
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "paper.py")
s = open(P, encoding="utf-8").read()

if '_lang = str(ctx.get("lang") or "en")' not in s:
    m = re.search(r"(\n\s+)L = \[head,", s)
    assert m, "no L = [head,"
    ins = (m.group(1) + '_lang = str(ctx.get("lang") or "en")\n'
           + m.group(1) + '_IS_EN = _i18n.is_en(_lang)\n')
    s = s[:m.start()] + ins + s[m.start():]
    print("  inserted _lang")

# 整个字符串字面量 -> Python 表达式
PAIRS = [
    (r'r"\section\{Limitations\}"',
     '"\\\\section{" + _i18n.sec(_lang, "limitations") + "}"'),
    (r'r"\section\{Introduction\}"',
     '"\\\\section{" + _i18n.sec(_lang, "intro") + "}"'),
    (r'r"\section\{Assumptions and Notations\}"',
     '"\\\\section{" + _i18n.sec(_lang, "assumptions") + "}"'),
    (r'r"\section\{Mechanistic basis\}"',
     '"\\\\section{" + _i18n.sec(_lang, "mech") + "}"'),
    (r'r"\section\{Problem 2: Design selection under constraints\}"',
     '"\\\\section{" + _i18n.sec(_lang, "p2") + "}"'),
    (r'r"\section\{Problem 3: How stable are the conclusions\?\}"',
     '"\\\\section{" + _i18n.sec(_lang, "p3") + "}"'),
    (r'r"\section\{Problem 4: Does the choice survive a change of "\s*\n\s*r"priorities\?\}"',
     '"\\\\section{" + _i18n.sec(_lang, "p4") + "}"'),
    (r'r"\section\{Problem 5: Can this design be manufactured\?\}"',
     '"\\\\section{" + _i18n.sec(_lang, "p5") + "}"'),
    (r'r"\section\{Evaluation\}"',
     '"\\\\section{" + _i18n.sec(_lang, "eval") + "}"'),
    (r'r"\section\{AI Disclosure and Human Verification\}"',
     '"\\\\section{" + _i18n.sec(_lang, "disclosure") + "}"'),
    (r'r"\section\{Core Code\}"',
     '"\\\\section{" + _i18n.sec(_lang, "code") + "}"'),
]
n = 0
for pat, rep in PAIRS:
    s, k = re.subn(pat, rep, s, count=1)
    n += k
print("  replaced %d section literals" % n)

OLD1 = ('    _y_en1 = esc_tex(describe(y)[0]) if y and describe(y) '
        'else "the response"\n'
        '    L += [r"\\section{Problem 1: How the geometry governs " '
        '+ _y_en1 + "}",')
NEW1 = ('    _y_en1 = esc_tex(describe(y)[0]) if y and describe(y) '
        'else "the response"\n'
        '    # 中文版用原名（产量），英文版用英文化名（yield）—— 两种语言\n'
        '    # 各走各的，不共享。\n'
        '    _y1 = _y_en1 if _IS_EN else (esc_tex(y) if y else "响应")\n'
        '    L += ["\\\\section{" + _i18n.sec(_lang, "p1", y=_y1) + "}",')
assert OLD1 in s, "no p1 anchor"
s = s.replace(OLD1, NEW1, 1)
print("  patched p1")

ast.parse(s)
compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  done")