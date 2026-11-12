import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(HERE, "mmkit.py"), encoding="utf-8").read()
i = s.find("    a = ap.parse_args()")
j = s.find("\ndef ", i)
seg = s[i:j] if j > 0 else s[i:i + 20000]
print("  === main() 里的分支顺序 ===")
for k, ln in enumerate(seg.splitlines(), 1):
    st = ln.strip()
    if st.startswith('if a.cmd ==') or st.startswith("return run(") or st.startswith("return "):
        print("    %4d %s" % (k, st[:76]))