import os
import re
import zlib
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(HERE, "external", "github", "li1408__MathModelHub",
                 "competitions", "2026_MCM_Problem_C.pdf")
raw = open(p, "rb").read()
txts = []
for m in re.finditer(rb"stream\r?\n(.*?)endstream", raw, re.S):
    blob = m.group(1)
    try:
        d = zlib.decompress(blob)
    except Exception:
        d = blob
    if b"Tj" in d or b"TJ" in d:
        txts.append(d)
out = []
for d in txts:
    for m2 in re.finditer(rb"\((?:[^()\\]|\\.)*\)", d):
        s = m2.group(0)[1:-1]
        s = s.replace(b"\\(", b"(").replace(b"\\)", b")").replace(b"\\\\", b"\\")
        try:
            out.append(s.decode("latin-1"))
        except Exception:
            pass
txt = " ".join(out)
# 还原：PDF 里每个字符间都有空格 -> 去掉"单字母+空格"模式
txt = re.sub(r"(?<=\b\w) (?=\w\b)", "", txt)
txt = re.sub(r"(?<=\w) (?=\w)", "", txt)
txt = txt.replace("\\251", "C").replace("\\226", "-").replace("\\223", '"').replace("\\224", '"')
txt = re.sub(r"\s+", " ", txt)
open(os.path.join(HERE, "out", "c2026_problem.txt"), "w",
     encoding="utf-8", newline="\n").write(txt)
print("  题面字数: %d" % len(txt))
print()
print(txt[:3200])