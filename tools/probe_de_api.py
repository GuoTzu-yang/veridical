import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lines = open(os.path.join(HERE, "domain_extra.py"), encoding="utf-8").read().splitlines()
print("  === domain_extra.py 骨架 ===")
for i, ln in enumerate(lines, 1):
    st = ln.strip()
    if st.startswith(("def ", "KINDS", "LABEL", "#")) and len(st) < 92:
        if st.startswith("def ") or st.startswith("KINDS"):
            print("    %4d %s" % (i, st[:88]))