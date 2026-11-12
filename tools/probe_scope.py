import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
print("  === scope_test 相关 ===")
for root, dirs, files in os.walk(HERE):
    if "external" in root or ".git" in root:
        dirs[:] = []
        continue
    for f in files:
        if "scope_test" in f and f.endswith(".xlsx"):
            print("   ", os.path.relpath(os.path.join(root, f), HERE))
print("  === test_domains.py 的数据输出 ===")
s = open(os.path.join(HERE, "tools", "test_domains.py"),
         encoding="utf-8").read()
for i, ln in enumerate(s.splitlines(), 1):
    if "OUT" in ln or ".xlsx" in ln:
        print("    :%-4d%s" % (i, ln.strip()[:88]))