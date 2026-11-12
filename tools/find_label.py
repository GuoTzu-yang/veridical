import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = open(os.path.join(HERE, "paper.py"), encoding="utf-8").read()
# 「模型选择 / Model selection」小节的 label
for kw in ("Model selection", "model selection", "sec:model", "sec:select"):
    i = 0
    while True:
        i = p.find(kw, i)
        if i < 0:
            break
        ln = p[:i].count("\n") + 1
        line = p[i:i + 200].splitlines()[0]
        print("  %5d  %s" % (ln, line[:96]))
        i += len(kw)
print()
# 所有已有 label
import re
labs = sorted(set(re.findall(r'\\label\{([^}]+)\}', p)))
print("  paper.py 里的 label（%d 个）: %s" % (len(labs), labs))