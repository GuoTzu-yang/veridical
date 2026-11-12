#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rt_intgap.py —— 只读（只写临时目录）：整数 token 免检通道的实际宽度。

样本：3 个可溯源的小数 + N 个**编造**的大整数。
gate 的 numbers 判 PASS 吗？verify 怎么看？
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import gate          # noqa: E402
import verify as V   # noqa: E402

TRACED = [0.9123, 0.4501, 0.7777]
FAKE_INTS = [1123, 2234, 3345, 4456, 5567, 6678, 7789, 8890, 9901, 1012]
tex = ("We report %.4f and %.4f and %.4f, then "
       % tuple(TRACED)
       + ", ".join(str(x) for x in FAKE_INTS)
       + " as further counts.\n")

td = tempfile.mkdtemp(prefix="rt_intgap_")
io.open(os.path.join(td, "paper.tex"), "w", encoding="utf-8").write(tex)
items = [dict(path="x%d" % i, value=v) for i, v in enumerate(TRACED)]
json.dump(dict(n=len(items), items=items),
          io.open(os.path.join(td, "冻结数字.json"), "w", encoding="utf-8"))

r = gate.chk_numbers(td)
rv = V.trace(tex, V.load_outputs(td))
print("论文：3 个真数 + %d 个编造整数" % len(FAKE_INTS))
print("gate.numbers : %-5s %s" % (r["status"], r["detail"]))
print("verify.trace : %d/%d 可溯源，未溯源 %d 个"
      % (rv["n_numbers"] - rv["n_untraced"], rv["n_numbers"],
         rv["n_untraced"]))
print("verify 判红的 token: %s"
      % [u["token"] for u in rv["untraced"]][:12])
