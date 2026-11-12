import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lines = open(os.path.join(HERE, "paper.py"), encoding="utf-8").read().splitlines()
# 找 _mm3 块的结束（下一个缩进 <= 4 的非空行）
start = 1942  # 0-based of line 1943
end = None
for i in range(start + 1, len(lines)):
    ln = lines[i]
    if not ln.strip():
        continue
    if len(ln) - len(ln.lstrip()) <= 4:
        end = i
        break
print("  _mm3 块：%d..%d（%d 行）" % (start + 1, end, end - start))
dep = [(i + 1, lines[i].strip()[:70]) for i in range(start, end)
       if "_mm3" in lines[i]]
print("  块内引用 _mm3：%d 处" % len(dep))
for ln, t in dep[:6]:
    print("    %5d  %s" % (ln, t))