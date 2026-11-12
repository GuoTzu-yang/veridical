import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYS = ("fig2", '"fig_mpl"', "figcheck_selftest", "lang", "--lang")
for f in sorted(os.listdir(HERE)):
    if not f.endswith(".py"):
        continue
    p = os.path.join(HERE, f)
    lines = open(p, encoding="utf-8", errors="replace").read().splitlines()
    for no, ln in enumerate(lines, 1):
        if "fig2" in ln or "figcheck_selftest" in ln:
            print("  %-22s:%-5d%s" % (f, no, ln.strip()[:84]))
print("  --- 多语言目录名从哪来 ---")
for f in ("mmkit.py", "paper.py"):
    p = os.path.join(HERE, f)
    lines = open(p, encoding="utf-8", errors="replace").read().splitlines()
    for no, ln in enumerate(lines, 1):
        if re.search(r'"out",\s*lang|out["\x27],\s*lang|lang\s*\)\s*,', ln):
            print("  %-22s:%-5d%s" % (f, no, ln.strip()[:84]))