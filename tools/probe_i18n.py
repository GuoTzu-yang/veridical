import os, sys, traceback
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import paper
for lang in ("en", "zh"):
    ctx = dict(ds=None, n=60, y="产量", xs=["反应温度","操作压力"],
               min_cols="产量,能耗", problem="chemical reactor", lang=lang)
    paper.set_overrides(None)
    try:
        t = paper.build(ctx)
        print("  %s: OK, tex %d 字符" % (lang, len(t)))
    except Exception as e:
        print("  %s: 抛异常 %s: %s" % (lang, type(e).__name__, e))
        traceback.print_exc()