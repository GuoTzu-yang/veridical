import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lines = open(os.path.join(HERE, "gate.py"), encoding="utf-8").read().splitlines()
i = next(k for k, l in enumerate(lines) if "_admits" in l)
print("  _admits 在第 %d 行" % (i + 1))
# 往上找最近的 def
for k in range(i, 0, -1):
    if lines[k].startswith("def "):
        print("  所在函数: %s (第 %d 行)" % (lines[k][:60], k + 1))
        break
# 该函数签名
print("  签名:", lines[k][:110])
# tex 在这个函数里是参数吗
print()
print("  _admits 附近 12 行:")
for k2 in range(i - 6, i + 12):
    print("  %5d %s" % (k2 + 1, lines[k2][:88]))