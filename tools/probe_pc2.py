import os, sys, traceback
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import mm
ds = mm.DS(os.path.join(HERE, "out", "data", "scope_test.xlsx"))
try:
    pc = mm.partial_corr(ds, "产量", "反应温度", ["操作压力"])
    print("  返回类型:", type(pc))
    print("  值:", str(pc)[:200])
except Exception as e:
    print("  partial_corr 抛:", type(e).__name__, e)
    traceback.print_exc()