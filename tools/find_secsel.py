import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = open(os.path.join(HERE, "paper.py"), encoding="utf-8").read()
for m in ("sec:selection",):
    i = 0
    while True:
        i = p.find(m, i)
        if i < 0:
            break
        ln = p[:i].count("\n") + 1
        print("  paper.py:%d  %s" % (ln, p[max(0, i - 110):i + 60].splitlines()[-1][:96]))
        i += len(m)
print()
t = open(os.path.join(HERE, "out", "runs", "review_microwave", "paper.tex"),
         encoding="utf-8").read()
print("  tex 里 \\ref{sec:selection} 出现:", t.count(r"\ref{sec:selection}"))
print("  tex 里 \\label{sec:selection} 出现:", t.count(r"\label{sec:selection}"))
i = t.find(r"\ref{sec:selection}")
print("  上下文:", t[max(0, i - 160):i + 40].replace("\n", " ")[-180:])