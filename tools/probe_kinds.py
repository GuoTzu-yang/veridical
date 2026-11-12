import os, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import kind
print("  kind.py 的题型取值:")
for n in ("KINDS", "NAMES", "LABELS", "_KINDS", "TYPES"):
    v = getattr(kind, n, None)
    if v:
        print("    %s = %s" % (n, list(v)[:14]))
        break
print()
import re
s = open(os.path.join(HERE, "kind.py"), encoding="utf-8").read()
m = re.findall(r'"(mechanism|regression|prediction|evaluation|clustering|multiobjective|simulation|optimization|network|queueing|"[a-z_]+)"', s)
seen = []
for x in m:
    if x not in seen:
        seen.append(x)
print("  源码里出现的题型串（前 16）: %s" % seen[:16])