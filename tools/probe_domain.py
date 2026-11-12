import os
import re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(HERE, "domain_extra.py")
s = open(p, encoding="utf-8").read()
print("  domain_extra.py %d 行" % len(s.splitlines()))
labels = re.findall(r"\\label\{([^}]+)\}", s)
print("  提供的公式 label: %s" % labels)
print()
# 论文里用到这些 label 吗
import json
cfg = json.load(open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
use = {}
for name, c in cfg.items():
    tp = os.path.join(HERE, c["out"], "paper.tex")
    if not os.path.exists(tp):
        continue
    t = open(tp, encoding="utf-8").read()
    hit = [l for l in labels if l in t]
    use[name] = hit
ok = {k: v for k, v in use.items() if v}
print("  22 道题里用到 domain_extra 公式的：%d 道" % len(ok))
for k, v in list(ok.items())[:6]:
    print("    %-16s %s" % (k, v))