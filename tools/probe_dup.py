import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lines = open(os.path.join(HERE, "paper.py"), encoding="utf-8").read().splitlines()
print("  'What the residuals say' 出现位置：")
for i, ln in enumerate(lines, 1):
    if "What the residuals say" in ln:
        print("    %5d  [缩进 %d] %s" % (i, len(ln) - len(ln.lstrip()),
                                        ln.strip()[:70]))
print()
print("  '_sp = ' / '_dg_ok' / 'if _sp' 位置：")
for i, ln in enumerate(lines, 1):
    st = ln.strip()
    if st.startswith("_sp =") or st.startswith("_dg_ok") or st == "if _sp:" or st.startswith("if _sp or"):
        print("    %5d  [缩进 %d] %s" % (i, len(ln) - len(ln.lstrip()), st[:70]))