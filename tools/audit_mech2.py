import os
import re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(HERE, "paper.py"), encoding="utf-8").read()
i = s.find("The specification used later is not chosen by convenience")
print("  === paper.py 里这段的生成条件 ===")
seg = s[max(0, i - 2600):i + 120]
for ln in seg.splitlines():
    st = ln.strip()
    if st.startswith("if ") or st.startswith("# ---") or "Mechanistic" in st:
        print("    %s" % st[:86])
print()
print("  === 上下文 ===")
print(s[max(0, i - 700):i + 120])