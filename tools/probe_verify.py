import os
import re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(HERE, "verify.py"), encoding="utf-8").read()
# 证据来源：哪些目录/文件被读
for kw in ("json", "csv", "out", "glob", "listdir", "walk", "rglob"):
    for m in re.finditer(r"^.*%s.*$" % kw, s, re.M):
        ln = m.group(0).strip()
        if len(ln) < 120 and ("open(" in ln or "glob" in ln or "listdir" in ln or "walk" in ln):
            print("  %s" % ln[:110])