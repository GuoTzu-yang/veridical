import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for f in sorted(os.listdir(HERE)):
    if not f.endswith(".py"):
        continue
    p = os.path.join(HERE, f)
    lines = open(p, encoding="utf-8", errors="replace").read().splitlines()
    for no, ln in enumerate(lines, 1):
        if "fig_mpl" in ln and "out" in ln:
            print("  %-16s:%-5d%s" % (f, no, ln.strip()[:86]))
print("  --- lang 目录 ---")
for f in sorted(os.listdir(HERE)):
    if not f.endswith(".py"):
        continue
    p = os.path.join(HERE, f)
    lines = open(p, encoding="utf-8", errors="replace").read().splitlines()
    for no, ln in enumerate(lines, 1):
        if '"out",' in ln and ("lang" in ln or "argv" in ln):
            print("  %-16s:%-5d%s" % (f, no, ln.strip()[:86]))
        if re.search(r'out["\x27],\s*(a|zh|en|de|fr|ru)\b', ln):
            print("  %-16s:%-5d%s" % (f, no, ln.strip()[:86]))