import os
import sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import i18n
import re

print("  en sections (%d):" % len(i18n.LANGS["en"]["sections"]))
for i, s in enumerate(i18n.LANGS["en"]["sections"]):
    print("    %2d %s" % (i, s))
print()
print("  zh sections (%d):" % len(i18n.LANGS["zh"]["sections"]))
for i, s in enumerate(i18n.LANGS["zh"]["sections"]):
    print("    %2d %s" % (i, s))
print()
t = open(os.path.join(HERE, "out", "lang_zh", "paper.tex"),
         encoding="utf-8").read()
secs = re.findall(r"\\section\*?\{([^}]*)\}", t)
print("  tex 实际 %d 个 \\section:" % len(secs))
for i, s in enumerate(secs):
    print("    %2d %s" % (i, s))