#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""e_probe5.py —— 量化三种修法各自的收益（在内存里试算，不改源码）。

现状（gate 口径）：
  freeze._decimals("5.924e+04") 返回 "924e+04" 的长度 = 7
  于是要求论文值精确到 1e-7，而真实写法是 4 位有效数字 → 必然失配

修法 P1（只修科学计数法的书写精度）：
  把 "5.924e+04" 的精度算成「保留到十位」= -1 位小数，
  即 |v - frozen| <= 0.5 * 10^1。这是 verify._near 的语义，不是放宽。

本工具对每道题报：
  · 现状未溯源数
  · 修 P1 后的未溯源数
  · 修 P1 后剩下的每一项是什么（用来判断还要不要动 paper.py）
"""
import io
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import freeze                    # noqa: E402
import untraced as U             # noqa: E402
import verify as V               # noqa: E402


def sci_decimals(tok: str):
    """科学计数法的书写精度 → 小数位数（可为负）。

    "5.924e+04" → 尾数 4 位有效数字，指数 4 → 精度落在 10^(4-4+1)=10^1
                → 小数位 -1（保留到十位）
    "1.96e-11" → 3 位有效数字，指数 -11 → 10^(-11-3+1)=10^-13 → 小数位 13
    """
    m = re.fullmatch(r"(-?)(\d+)(?:\.(\d+))?[eE]([+-]?\d+)", tok.strip())
    if not m:
        return None
    frac = m.group(3) or ""
    mant_digits = len(m.group(2).lstrip("0")) + len(frac)
    if not mant_digits:
        return None
    exp = int(m.group(4))
    # 值 = 尾数 × 10^exp；尾数最高位权重 10^exp，最低位权重
    # 10^(exp - (mant_digits-1))。写作「保留到该位」= 小数位 -(exp-(mant-1))。
    return mant_digits - 1 - exp


def _match(v, dec, fvals):
    """按小数位 dec（可负）判断 v 是否是某个冻结值的合法写法。"""
    tol = 0.5 * (10.0 ** -dec) + 1e-12
    for f in fvals:
        for cv, cf in ((abs(v), abs(f)),
                       (abs(v), abs(f) * 100.0),
                       (abs(v), abs(f) / 100.0)):
            if abs(cv - cf) <= tol:
                return True
    return False


def run(nm, item, fix):
    d = os.path.join(HERE, item["out"])
    tex = os.path.join(d, "paper.tex")
    fz = os.path.join(d, "冻结数字.json")
    if not (os.path.exists(tex) and os.path.exists(fz)):
        return None
    text = io.open(tex, encoding="utf-8").read()
    frozen = json.load(io.open(fz, encoding="utf-8"))
    fvals = [it["value"] for it in frozen.get("items", [])]
    dv = U.data_values_of(U.find_data_file(d))
    t = re.sub(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}",
               " ", text, flags=re.S)
    toks = [tk for tk, _l in V.extract_numbers(t, skip_meta=False)
            if "." in tk]
    seen, uniq = set(), []
    for tk in toks:
        try:
            v = float(tk)
        except ValueError:
            continue
        if "e" in tk.lower():
            dec = sci_decimals(tk) if fix else freeze._decimals(tk)
        else:
            dec = freeze._decimals(tk)
        if dec is None:
            continue
        key = (round(v, 6), dec)
        if key in seen:
            continue
        seen.add(key)
        uniq.append((tk, v, dec))
    traced, unt = [], []
    for tk, v, dec in uniq:
        if _match(v, dec, fvals) if fix else freeze._match_written(
                v, dec, fvals):
            traced.append(tk)
        elif dv and round(v, 6) in dv:
            traced.append(tk)
        else:
            unt.append((tk, dec))
    return dict(n=len(uniq), traced=len(traced), unt=unt)


def main(argv):
    cfg = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
    names = argv[1:] or ["age_struct", "nflis", "multiobjective",
                         "icm2006c", "pop_panel"]
    tot_now = tot_fix = tot_n = 0
    for nm in names:
        a = run(nm, cfg[nm], fix=False)
        b = run(nm, cfg[nm], fix=True)
        if not a:
            continue
        tot_now += len(a["unt"])
        tot_fix += len(b["unt"])
        tot_n += a["n"]
        print("=" * 76)
        print("%-14s %3d token ｜ 现状未溯源 %2d (%.1f%%) ｜ "
              "修 P1 后 %2d (%.1f%%)"
              % (nm, a["n"], len(a["unt"]),
                 100.0 * len(a["unt"]) / a["n"], len(b["unt"]),
                 100.0 * len(b["unt"]) / a["n"]))
        if b["unt"]:
            print("    P1 后仍红：", " ".join(t for t, _ in b["unt"]))
    print("=" * 76)
    print("合计 %d token：现状红 %d (%.1f%%) → 修 P1 后红 %d (%.1f%%)"
          % (tot_n, tot_now, 100.0 * tot_now / tot_n,
             tot_fix, 100.0 * tot_fix / tot_n))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
