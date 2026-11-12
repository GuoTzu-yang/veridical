#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rt_equiv.py —— 只读：`_match_written` 是否**恰好**等于「半格 + 绝对值 + 百分比」？

第 122 轮复核版。上一版拿 `1e-9` 绝对容差当"教科书判据"，那个对照本身太松
（dec=10 时半格是 5e-11，1e-9 宽 20 倍），于是差异率随生产判据变严而**上升**，
看着像"判据出问题"，其实是尺子不准。这一版用严格半格：

  S = |v - f|            <= 0.5*10**-dec           同号半格
  H = |abs(v) - abs(f)|  <= 0.5*10**-dec           半格 + 绝对值
  P = H or |v - f*100| <= tol or |v - f/100| <= tol   半格 + abs + 百分比
  A = freeze._match_written(v, dec, [f])           生产判据

要验证的是 A == P（逐例），以及 S 与 H 的差（= 仅凭「反号」通过的例数）。
"""
from __future__ import annotations

import random
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import freeze as F      # noqa: E402

random.seed(20261111)
N = 20000
bad_ph = 0
flip = 0
ex_ph = []
ex_flip = []
for _ in range(N):
    dec = random.choice([-4, -3, -2, -1, 0, 1, 2, 3, 4, 6, 10, 15])
    mag = random.choice([1e-14, 1e-6, 1e-2, 1.0, 1e2, 1e4, 1e6])
    f = random.uniform(-mag, mag)
    r = round(f, dec)
    pick = random.random()
    if pick < 0.4:
        v = r
    elif pick < 0.7:
        v = round(-f, dec)              # 反号：专门喂给 abs 分支
    else:
        v = r + random.choice([-1, 1]) * (10 ** (-dec))
    tol = 0.5 * (10.0 ** -dec)
    A = F._match_written(v, dec, [f])
    S = abs(v - f) <= tol
    H = abs(abs(v) - abs(f)) <= tol
    P = H or abs(abs(v) - abs(f) * 100.0) <= tol or \
        abs(abs(v) - abs(f) / 100.0) <= tol
    if A != P:
        bad_ph += 1
        if len(ex_ph) < 6:
            ex_ph.append((v, dec, f, A, P))
    if H and not S:
        flip += 1
        if len(ex_flip) < 4:
            ex_flip.append((v, dec, f))

print("随机样本 %d 例" % N)
print("A(生产) vs P(半格+abs+百分比): 不一致 %d (%.4f%%)"
      % (bad_ph, 100.0 * bad_ph / N))
for e in ex_ph:
    print("   v=%r dec=%r f=%r  A=%s P=%s" % e)
print("仅凭「反号」通过（H 真、S 假）: %d 例 (%.2f%%)"
      % (flip, 100.0 * flip / N))
for e in ex_flip:
    print("   v=%r dec=%r f=%r" % e)
