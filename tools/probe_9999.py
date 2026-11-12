import os
import sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import verify

tex = open(os.path.join(HERE, "out", "runs", "chemical", "_forged.tex"),
           encoding="utf-8").read()
outs = verify.load_outputs(os.path.join(HERE, "out", "runs", "chemical"))
nums = verify.extract_numbers(tex)
print("  论文里提取到 %d 个数字" % len(nums))
print("  含 0.9999:", [n for n in nums if n in ("0.9999", "9999", "0.999")])
r = verify.trace(tex, outs)
print("  trace 结果键:", list(r.keys()))
un = r.get("unmatched") or []
print("  未溯源 %d 个" % len(un))
print("  其中含 9999 的:", [u for u in un if "9999" in str(u)])
# 看看 0.9999 被匹配到谁了
import re
for m in re.finditer(r"0\.9999|9999", tex):
    print("  原文命中:", tex[max(0, m.start() - 40):m.start() + 20].replace("\n", " "))