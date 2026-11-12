import os
import sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import domain as dom
xs = ["到达人数", "服务台数"]
det = dom.detect(xs, "queuing waiting time", None)
print("  queueing 判定:", det.get("key"))
print("  有 eq:", bool(det["domain"].get("equation")))
print("  eq 里的 label:", [l for l in str(det["domain"].get("equation")).split()
                          if "label" in l][:2])
for k in ("queueing", "evaluation"):
    d = dom.DOMAINS.get(k) or {}
    print("  DOMAINS[%s] 存在=%s eq=%s" % (k, bool(d), bool(d.get("equation"))))