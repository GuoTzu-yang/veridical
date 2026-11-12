import os
import re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(HERE, "paper.py"), encoding="utf-8").read()
print("  paper.py 里 \\section 的生成点:")
for m in re.finditer(r'\\section\{([^}]{0,90})\}', s):
    ln = s[:m.start()].count("\n") + 1
    print("    %5d  %s" % (ln, m.group(1)[:80]))
print()
print("  含 'Problem N:' 的字符串（题目相关标题）:")
for m in re.finditer(r'"([^"]*Problem \{?[A-Za-z0-9n ]*\}?:[^"]*)"', s):
    ln = s[:m.start()].count("\n") + 1
    print("    %5d  %s" % (ln, m.group(1)[:86]))