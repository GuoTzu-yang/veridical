import os, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import paper

KEY = "This report models chemical reactor arou"
NEW = "We treat the reactor as a two-input response system."
ctx = dict(ds=None, n=60, y="产量", xs=["反应温度","操作压力"],
           min_cols="产量,能耗", problem="chemical reactor", lang="en")

def tex_of(ov):
    paper.set_overrides(ov)
    try:
        return paper.build(ctx)
    except Exception:
        return ""

t0 = tex_of(None)
t1 = tex_of({KEY: NEW})
print("  模板 tex 长度: %d" % len(t0))
print("  注入 tex 长度: %d" % len(t1))
print("  注入句在 tex 里: %s" % (NEW in t1))
print("  模板原句还在:   %s" % ("around a single yardstick" in t1))
print("  ★ 注入生效:     %s" % ((NEW in t1) and t0 != t1))