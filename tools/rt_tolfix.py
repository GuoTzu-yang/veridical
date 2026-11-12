#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rt_tolfix.py —— 只读：三种 tol 公式在「边界舍入」与「地板误接受」两头的表现。

T0 = 0.5*10**-dec + 1e-12                 （122 轮前，有绝对地板）
T1 = 0.5*10**-dec                         （当前生产判据，地板已去掉）
T2 = 0.5*10**-dec + 1e-12*max(|v|,|f|)    （建议：按量级松弛，不给 0 附近留窗口）

案例：
  A 组「合法舍入」：f 的最低位恰好是 5（舍入中点），|v-f| 数学上等于半格；
                   浮点表示让实际差比半格多 ~1e-17。正确判据应当接受。
  B 组「地板误接受」：1e-13 量级的论文值 vs 冻结表里的 0.0 或 1e-17。
                   正确判据应当拒绝。
"""
from __future__ import annotations

import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)


def tol0(dec, v, f):
    return 0.5 * (10.0 ** -dec) + 1e-12


def tol1(dec, v, f):
    return 0.5 * (10.0 ** -dec)


def tol2(dec, v, f):
    return 0.5 * (10.0 ** -dec) + 1e-12 * max(abs(v), abs(f))


CASES = [
    ("A 合法舍入", 0.78751, 5, 0.787505),
    ("A 合法舍入", 0.73916, 5, 0.739155),
    ("A 合法舍入", 32.95, 2, 32.945),
    ("A 合法舍入", 0.78751, 5, 0.7875050000000001),
    ("B 地板", 2.0839e-13, 17, 0.0),
    ("B 地板", 1.4792e-13, 17, -2.4671622769447922e-17),
    ("B 地板", 5.481e-13, 16, -2.4671622769447922e-17),
    ("B 地板", 6.7973e-14, 18, -2.4671622769447922e-17),
    ("B 地板", 0.0, -3, -942.6619609415065),
]

print("%-10s %-14s %-4s %-24s %-8s %-8s %-8s"
      % ("组", "v", "dec", "f", "T0", "T1", "T2"))
print("-" * 90)
for label, v, dec, f in CASES:
    d = abs(abs(v) - abs(f))
    r = []
    for fn in (tol0, tol1, tol2):
        t = fn(dec, v, f)
        r.append("%s(%.1e)" % ("Y" if d <= t else "n", t))
    print("%-10s %-14r %-4d %-24r %-10s %-10s %-10s"
          % (label, v, dec, f, r[0], r[1], r[2]))
print()
print("期望：A 组 T2 全 Y；B 组 T2 全 n。")
print("（T1 是当前生产判据；T0 是 122 轮前，T2 是这里的建议）")
