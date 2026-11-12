import os, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import falsify, mm
sig = [x for x in dir(falsify) if not x.startswith("_")]
print("  falsify 公开:", sig)
ds = mm.DS(os.path.join(HERE, "out", "data", "scope_test.xlsx"))
r = falsify.counterexamples(ds.col("反应温度"), ds.col("产量"), sign=1)
print("  返回键:", list(r.keys()))
print("  内容:", str(r)[:280])