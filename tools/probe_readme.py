import os
p = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "tools", "pack.py")
lines = open(p, encoding="utf-8").read().splitlines()
start = None
for i, ln in enumerate(lines):
    if ln.startswith("README = "):
        start = i
        break
print("  README 变量在第 %d 行" % (start + 1))
# 打印它之后的所有非缩进行（看有没有写文件）
for i in range(start, len(lines)):
    st = lines[i]
    if st.startswith("README") or "open(" in st or "write(" in st or st.startswith("#"):
        print("  %4d  %s" % (i + 1, st[:88]))