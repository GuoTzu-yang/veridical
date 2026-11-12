import os
import sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import verify
tex = open(os.path.join(HERE, "out", "runs", "chemical", "_forged.tex"),
           encoding="utf-8").read()
for i, line in enumerate(tex.splitlines(), 1):
    if "0.9999" in line:
        print("  第 %d 行原文: %r" % (i, line[:150]))
        print("  _strip_noise 后: %r" % (verify._strip_noise(line)[:150],))
        print("  该行提取: %s" % verify.extract_numbers(line))
        break