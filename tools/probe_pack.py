import os
s = open(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "tools", "pack.py"), encoding="utf-8").read()
print("  总行数:", len(s.splitlines()))
for i, ln in enumerate(s.splitlines(), 1):
    st = ln.strip()
    if (st.startswith("def ") or "out" in st.lower() and
            ("skip" in st.lower() or "exclude" in st.lower()
             or "walk" in st.lower() or "dirs" in st.lower())):
        print("  %4d  %s" % (i, st[:88]))