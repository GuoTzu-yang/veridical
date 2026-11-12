import os
import sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import verify
import inspect
print(inspect.getsource(verify._near))
print("-" * 60)
tex = open(os.path.join(HERE, "out", "runs", "chemical", "_forged.tex"),
           encoding="utf-8").read()
outs = verify.load_outputs(os.path.join(HERE, "out", "runs", "chemical"))
pool = verify.collect_output_numbers(outs)
print("  outputs 池 %d 个数" % len(pool))
hit = [p for p in pool if verify._near(0.9999, p)]
print("  0.9999 匹配到:", hit)
hit2 = [p for p in pool if verify._near(0.000123, p)]
print("  0.000123 匹配到:", hit2)