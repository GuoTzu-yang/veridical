#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""e_probe7.py —— 定位 age_struct 的 5.95e+05，并核对 cond_* 的返回类型。只读。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)


def main():
    d = os.path.join(HERE, "out", "runs", "age_struct")
    j = json.load(io.open(os.path.join(d, "冻结数字.json"), encoding="utf-8"))
    items = j["items"]
    target = 595000.0
    near = sorted(items, key=lambda it: abs(it["value"] - target))[:5]
    print("### age_struct 冻结表里离 5.95e+05 最近的 5 项")
    for it in near:
        print("   %-34s %-22r 差 %g"
              % (it["path"], it["value"], it["value"] - target))
    print("\n### 论文里 5.95e+05 的原文")
    tex = io.open(os.path.join(d, "paper.tex"), encoding="utf-8").read()
    for line in tex.splitlines():
        if "5.95e+05" in line:
            print("  ", line.strip()[:220])
            break

    print("\n### cond_scaled / cond_raw 的返回类型")
    import mmkit
    import mm
    cfg = json.load(io.open(os.path.join(HERE, "runs.json"),
                            encoding="utf-8"))
    for nm in ("age_struct", "multiobjective"):
        it = cfg[nm]
        ds = mm.DS(os.path.join(HERE, "out", "data", it["data"]))
        xs = ds.pick(it.get("x") or []) if it.get("x") else []
        if not xs:
            xs = ds.num_names[:3]
        try:
            a = mmkit._cond_scaled(ds, list(xs))
            b = mmkit._cond_raw(ds, list(xs))
            print("   %-14s cond_scaled=%r (%s)  cond_raw=%r (%s)"
                  % (nm, a, type(a).__name__, b, type(b).__name__))
        except Exception as e:                        # noqa: BLE001
            print("   %-14s 失败: %s" % (nm, e))


if __name__ == "__main__":
    main()
