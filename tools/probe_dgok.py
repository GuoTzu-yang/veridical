import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(HERE, "paper.py"), encoding="utf-8").read()
for pat in ("_dg_ok =", "_dg = ctx.get"):
    i = s.find(pat)
    if i < 0:
        print("  没找到 %s" % pat)
        continue
    ln = s[:i].count("\n") + 1
    print("  paper.py:%d" % ln)
    print("    " + s[i:i + 130].splitlines()[0][:110])
# 残差节的条件
j = s.find("What the residuals say")
print()
print("  残差节前 3 行（条件链）:")
for l in s[max(0, j - 300):j].splitlines()[-4:]:
    print("    " + l[:92])