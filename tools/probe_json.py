import os
import re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(HERE, "mmkit.py"), encoding="utf-8").read()
print("  === json.dumps 出现位置 ===")
for m in re.finditer(r"print\(json\.dumps|json\.dump\(", s):
    ln = s[:m.start()].count("\n") + 1
    print("    :%-5d %s" % (ln, s[m.start():m.start() + 60].splitlines()[0]))
print()
print("  === print 总数 / 其中提示类 ===")
allp = len(re.findall(r"\bprint\(", s))
hint = len(re.findall(r'print\(f?"[ ·=\-]', s))
print("    print 总数: %d   明显提示类（·/=/空格开头）: %d" % (allp, hint))