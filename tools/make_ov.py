import json
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 用之前 skeleton 导出过的真实 key（内容寻址：原文前 40 字）
OV = {
  "This report models chemical reactor arou":
    "We treat the reactor as a two-input response system and measure every "
    "claim against one yardstick: out-of-fold prediction error. The choice "
    "is deliberate -- comparing quantities on different scales lets a weak "
    "conclusion borrow credibility from a strong one.",
}
p = os.path.join(HERE, "out", "overrides_demo.json")
json.dump(OV, open(p, "w", encoding="utf-8", newline="\n"),
          ensure_ascii=False, indent=1)
print("  写好 overrides：%s" % os.path.basename(p))
for k in OV:
    print("    key = %r" % k)