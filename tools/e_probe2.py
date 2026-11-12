#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""e_probe2.py —— 查「输入表里到底有没有这些数」。

对每道红题：
  1. find_data_file 找到哪个文件
  2. data_values_of 收到多少个值
  3. 论文里被判 D_computed 的整数/科学计数法 token，逐个问「输入表里有没有」
     （用容差 1e-6 和 1e-9 各试一次，判断是不是匹配阈值的问题）

只读，不改。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import untraced as U          # noqa: E402
import verify as V            # noqa: E402


def main(argv):
    cfg = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
    names = argv[1:] or ["age_struct", "nflis", "multiobjective",
                         "icm2006c", "pop_panel"]
    for nm in names:
        d = os.path.join(HERE, cfg[nm]["out"])
        tex = os.path.join(d, "paper.tex")
        fz = os.path.join(d, "冻结数字.json")
        if not os.path.exists(tex):
            print(nm, "no paper.tex")
            continue
        src = ""
        gf = ""
        n_items = 0
        if os.path.exists(fz):
            fj = json.load(io.open(fz, encoding="utf-8"))
            src = str(fj.get("source") or "")
            gf = str(fj.get("generated_from") or "")
            n_items = len(fj.get("items") or [])
        df = U.find_data_file(d)
        dv = U.data_values_of(df) if df else set()
        text = io.open(tex, encoding="utf-8").read()
        r = V.trace(text, V.load_outputs(d))
        unt = r.get("untraced") or []
        # 只挑「像数字表行」的：整数或科学计数法
        ints = []
        for u in unt:
            t = u["token"]
            if "." in t and "e" not in t.lower():
                continue
            try:
                ints.append((t, float(t)))
            except ValueError:
                pass
        hit6 = hit9 = 0
        for _t, v in ints:
            if any(abs(v - x) < 1e-6 for x in dv):
                hit6 += 1
            if any(abs(v - x) < 1e-9 for x in dv):
                hit9 += 1
        print("=" * 74)
        print("%-14s 冻结 %4d 项  source=%r" % (nm, n_items, src))
        print("               generated_from=%r" % gf)
        print("               find_data_file -> %s"
              % (os.path.basename(df) if df else "(空)"))
        print("               data_values    -> %d 个值" % len(dv))
        print("               未溯源 %d，其中整数/科学计数 %d 个；"
              "在输入表里命中 1e-6:%d / 1e-9:%d"
              % (len(unt), len(ints), hit6, hit9))
        if ints and not hit6:
            print("               样例:", [t for t, _ in ints[:8]])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
