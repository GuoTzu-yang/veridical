import os
import sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import verify
p = os.path.join(HERE, "out", "runs", "chemical", "_forged.tex")
tex = open(p, encoding="utf-8").read()
nums = verify.extract_numbers(tex)
toks = [t for t, _ in nums]
print("  整篇提取 %d 个" % len(nums))
print("  含 9999 的:", [t for t in toks if "9999" in t])
print("  含 000123 的:", [t for t in toks if "000123" in t])
print("  前 12 个:", toks[:12])
# trace 内部怎么调的
i = verify.trace.__code__.co_consts
import inspect
src = inspect.getsource(verify.trace)
print()
print("  === trace 源码前 20 行 ===")
for ln in src.splitlines()[:20]:
    print("   " + ln[:90])