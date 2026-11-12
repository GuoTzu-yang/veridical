import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
t = open(os.path.join(HERE, "out", "lang_zh", "paper.tex"),
         encoding="utf-8").read()
print("  === 中文版 tex 里哪些是英文（应当独立的证据）===")
# 表头
for m in re.finditer(r"\\begin\{tabular\}\{[^}]*\}\s*\n(.{0,400}?)\\end\{tabular\}",
                     t, re.S):
    head = m.group(1).split("\\midrule")[0].split("\\toprule")[-1]
    head = " ".join(x.strip() for x in head.splitlines() if x.strip())
    print("    表头: %s" % head[:110])
    break
print()
for pat, tag in ((r"\\caption\{([^}]{0,80})", "图注"),
                  (r"\\label\{([^}]*)\}", "label")):
    hits = re.findall(pat, t)[:4]
    print("    %s: %s" % (tag, hits))
print()
secs = re.findall(r"\\section\*?\{([^}]*)\}", t)
print("    章节: %s" % secs)
print()
# 正文里的英文句
body = t[t.find(r"\end{abstract}"):]
sent = re.findall(r"[A-Z][a-z]+(?: [a-z]+){6,}", body)
print("    正文里 7 词以上的英文串: %d 处，例:" % len(sent))
for x in sent[:4]:
    print("      %s" % x[:88])