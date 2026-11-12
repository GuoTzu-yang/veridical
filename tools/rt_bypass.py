#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rt_bypass.py —— 只读（只写临时目录）：A2「自我冻结」护栏的绕过测试。

三个样本，同一张"论文自己写的数"伪造冻结表：
  S1 所有 path = "self"           → 期望 FAIL（护栏生效）
  S2 混一条 path = "x"            → ？
  S3 所有 path = ""               → 期望 FAIL
每个样本同时跑 gate.chk_numbers 与 verify.trace。
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

import gate      # noqa: E402
import verify as V   # noqa: E402

TEX = ("We report 0.9123 and 0.4501 and 0.7777 and 1.2345 here "
       "(plus 42 and 2019 as integers).\n")
VALS = [0.9123, 0.4501, 0.7777, 1.2345]


def make(td, paths):
    io.open(os.path.join(td, "paper.tex"), "w", encoding="utf-8").write(TEX)
    items = [dict(path=p, value=v) for p, v in zip(paths, VALS)]
    json.dump(dict(n=len(items), items=items),
              io.open(os.path.join(td, "冻结数字.json"), "w",
                      encoding="utf-8"), ensure_ascii=False)


def run(label, paths):
    td = tempfile.mkdtemp(prefix="rt_bypass_")
    make(td, paths)
    r = gate.chk_numbers(td)
    rv = V.trace(TEX, V.load_outputs(td))
    print("%-24s gate=%-5s verify=%d/%d 可溯源(%.1f%%)  detail=%s"
          % (label, r["status"], rv["n_numbers"] - rv["n_untraced"],
             rv["n_numbers"], rv["traced_ratio"] * 100, r["detail"][:64]))
    return r, rv


print("论文数字（全部编造）:", VALS)
run("S1 path 全为 self", ["self"] * 4)
run("S2 混一条 path=x", ["x", "self", "self", "self"])
run("S3 path 全为空串", [""] * 4)
run("S4 path 全为 x1..x4", ["x1", "x2", "x3", "x4"])
