import os
import sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import paper

KEY = "This report models chemical reactor arou"
NEW = ("We treat the reactor as a two-input response system and put every "
       "claim on one yardstick: out-of-fold error.")

# ① 不注入：拿到模板原文
paper.set_overrides(None)
ctx = dict(ds=None, n=60, y="产量", xs=["反应温度", "操作压力"],
           min_cols="产量,能耗", problem="chemical reactor", lang="en")
try:
    paper.build(ctx)
except Exception:
    pass
base = dict(paper.dump_skeleton())
print("  模板段落数: %d" % len(base))
print("  目标 key 在不在: %s" % (KEY in base))
print("  模板原文: %r" % base.get(KEY, "")[:80])

# ② 注入
paper.set_overrides({KEY: NEW})
try:
    paper.build(ctx)
except Exception:
    pass
after = dict(paper.dump_skeleton())
print()
print("  注入后该段: %r" % after.get(KEY, "")[:80])
print("  ★ 注入生效:", after.get(KEY) == NEW)