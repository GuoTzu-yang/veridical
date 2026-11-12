import os
import re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for n, p in (("evaluation", "out/domains/evaluation/paper.tex"),
              ("prediction", "out/domains/prediction/paper.tex"),
              ("real C2023", "out/real/paper.tex")):
    t = open(os.path.join(HERE, p), encoding="utf-8").read()
    i = t.find(r"\section{Mechanistic basis}")
    if i < 0:
        i = t.find(r"\section{机理基础}")
    j = t.find(r"\section{", i + 10)
    seg = t[i:j]
    plain = re.sub(r"\\begin\{(table|tabular|figure|verbatim|itemize)\}.*?"
                   r"\\end\{\1\}", " ", seg, flags=re.S)
    plain = re.sub(r"\\[a-zA-Z]+(\[[^\]]*\])?(\{[^}]*\})?", " ", plain)
    plain = " ".join(plain.split())
    print("  === %s 机理节正文 %d 字 ===" % (n, len(plain)))
    print("     %s" % plain[:300])
    print()