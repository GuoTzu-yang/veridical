import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "tests", "probe_precision.py")
BODY = r"""#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe 匹配的精确性测试。

两层问题，两个方向都要测
------------------------
假阳性（该报没做却报做了）：ward 命中 towards、dual 命中 residual。
    这一层最危险 —— claims 这一节存在的意义就是不许把「没做」当成「做了」。
假阴性（做了却报没做）：词干 probe（feasib / diagnos / normalis）两边界都加 \\b
    就匹配不到 feasible / diagnostics / normalised，实测 15 条一下全变不命中。

所以正确的规则是**左边界 + 前缀**：
    \\bward    不匹配 towards（前面是字母），匹配 ward（独立词）
    \\bfeasib  匹配 feasible
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import paper  # noqa: E402

CASES = [
    # (probe, text, 期望命中, 说明)
    ("ward", "the design shrinks towards zero", False, "towards 里的 ward 不算"),
    ("ward", "Ward linkage was used", True, "独立出现的 ward 算"),
    ("dual", "residual diagnostics leave no room", False, "residual 里的 dual 不算"),
    ("dual", "the dual of the programme", True, "独立出现的 dual 算"),
    ("feasib", "every candidate is feasible", True, "词干要能匹配 feasible"),
    ("diagnos", "residual diagnostics", True, "词干要能匹配 diagnostics"),
    ("normalis", "after normalising the indicators", True, "词干要能匹配 normalising"),
    ("standardis", "after standardising the factors", True, "词干要能匹配 standardising"),
    ("seed", "three random seeds were used", True, "复数也要匹配"),
    ("outlier", "individual outliers are drawn", True, "复数也要匹配"),
    ("condition number", "the condition number is 92.86", True, "多词短语按子串"),
    ("np-hard", "this is np-hard", True, "含连字符的按子串"),
]


def main():
    bad = 0
    for pr, text, want, why in CASES:
        got = paper._probe_hit(pr, text.lower())
        ok = got == want
        if not ok:
            bad += 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {pr!r:<18}"
              f"want={want} got={got}  ({why})")
    print()
    print(f"{'ALL PASS' if bad == 0 else 'FAILED'}  "
          f"{len(CASES) - bad}/{len(CASES)}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
"""
enc = __import__("codecs").getencoder("utf-8")
with open(P, "w", encoding="utf-8", newline="\n") as f:
    f.write(BODY)
print("  wrote tests/probe_precision.py")