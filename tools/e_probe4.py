#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""e_probe4.py —— 按 **gate 的真实口径**（freeze.check_paper）逐项取证。

gate 的 numbers 用的是 freeze.check_paper：
  · 只取**带小数点**的 token（"56"、"968"、"2015" 不进）
  · 每个 token 按书写精度四舍五入，必须等于某个冻结值
  · 否则再看它是否在输入表里（精确 6 位成员）
  · 否则 = untraced

本工具复刻这条链，并把每个 untraced token 的
     值 / 书写精度 / 是否含科学计数 / 是否能在输入表里按容差命中
全部打印出来。只读。
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import freeze                    # noqa: E402
import untraced as U             # noqa: E402
import verify as V               # noqa: E402


def _decimals(tok):
    if "." not in tok:
        return 0
    return len(tok.split(".")[1])


def run(nm, item):
    d = os.path.join(HERE, item["out"])
    tex = os.path.join(d, "paper.tex")
    fz = os.path.join(d, "冻结数字.json")
    if not (os.path.exists(tex) and os.path.exists(fz)):
        return None
    text = io.open(tex, encoding="utf-8").read()
    frozen = json.load(io.open(fz, encoding="utf-8"))
    fvals = [it["value"] for it in frozen.get("items", [])]
    dv = U.data_values_of(U.find_data_file(d))

    # 复刻 check_paper 的抽取
    t = re.sub(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}",
               " ", text, flags=re.S)
    allt = V.extract_numbers(t, skip_meta=False)
    toks = [tk for tk, _l in allt if "." in tk]
    pairs = []
    for tk in toks:
        try:
            v = float(tk)
        except ValueError:
            continue
        if abs(v) < 1e6 or "e" in tk.lower():
            pairs.append((tk, v, _decimals(tk)))
    seen, uniq = set(), []
    for tk, v, dec in pairs:
        key = (round(v, 6), dec)
        if key in seen:
            continue
        seen.add(key)
        uniq.append((tk, v, dec))

    traced = []
    untraced = []
    n_data = 0
    for tk, v, dec in uniq:
        if freeze._match_written(v, dec, fvals):
            traced.append(tk)
        elif dv and round(v, 6) in dv:
            traced.append(tk)
            n_data += 1
        else:
            untraced.append((tk, v, dec))
    return dict(name=nm, n=len(uniq), n_traced=len(traced),
                n_data=n_data, untraced=untraced, dv=dv)


def main(argv):
    cfg = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
    names = argv[1:] or ["age_struct", "nflis", "multiobjective",
                         "icm2006c", "pop_panel"]
    for nm in names:
        r = run(nm, cfg[nm])
        if not r:
            print(nm, "缺 paper.tex 或 冻结数字.json")
            continue
        ratio = 100.0 * len(r["untraced"]) / max(1, r["n"])
        print("=" * 76)
        print("%-14s 带小数 token %d，可溯源 %d（其中来自输入表 %d）"
              "未溯源 %d = %.1f%%"
              % (nm, r["n"], r["n_traced"], r["n_data"],
                 len(r["untraced"]), ratio))
        sci = lng = near_dv = 0
        for tk, v, dec in r["untraced"]:
            if "e" in tk.lower():
                sci += 1
            elif dec >= 3:
                lng += 1
            if r["dv"] and any(abs(abs(v) - abs(x)) <= 0.5 * 10 ** -dec + 1e-12
                               for x in r["dv"]):
                near_dv += 1
        print("   科学计数法 %d ｜ ≥3 位小数 %d ｜ 输入表里容差内命中 %d"
              % (sci, lng, near_dv))
        for tk, v, dec in r["untraced"][:40]:
            flag = ""
            if "e" in tk.lower():
                flag = " [sci]"
            elif dec >= 3:
                flag = " [hp]"
            print("   %-16s dec=%d%s" % (tk, dec, flag))
        if len(r["untraced"]) > 40:
            print("   … 还有 %d" % (len(r["untraced"]) - 40))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
