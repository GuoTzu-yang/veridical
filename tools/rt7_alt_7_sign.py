# -*- coding: utf-8 -*-
"""红队第二板探针 7：abs(v) 对 abs(f) 掩盖的 16 个 token —— 逐个给出对照。

只读，只打印。输出：题 / 论文里的 token / 命中它的冻结值 / 论文原文行。
不给结论，只给原始对照（结论在报告里，读的人可以自己判）。

用法
    python tools/rt7_alt_7_sign.py
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import verify as V          # noqa: E402

RUNS = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))


def main():
    print("== 只靠 abs() 才能匹配的 token：论文值 vs 冻结值 vs 原文 ==")
    n = 0
    for name, it in RUNS.items():
        d = os.path.join(HERE, it["out"])
        tp = os.path.join(d, "paper.tex")
        fp = os.path.join(d, "冻结数字.json")
        if not (os.path.exists(tp) and os.path.exists(fp)):
            continue
        tex = io.open(tp, encoding="utf-8").read()
        fz = json.load(io.open(fp, encoding="utf-8"))
        items = fz.get("items") or []
        fv = [(it2.get("value"), it2.get("path")) for it2 in items]
        seen = set()
        for tok, line in V.extract_numbers(tex, skip_meta=False):
            if "." not in tok:
                continue
            try:
                v = float(tok)
            except ValueError:
                continue
            dec = V._written_decimals(tok)
            tol = 0.5 * (10.0 ** -dec) * (1 + 1e-9)
            key = (round(v, 6), dec)
            if key in seen:
                continue
            seen.add(key)

            def hit(use_abs):
                out = []
                vv = abs(v) if use_abs else v
                for f, p in fv:
                    ff = abs(f) if use_abs else f
                    for cf in (ff, ff * 100.0, ff / 100.0):
                        if abs(vv - cf) <= tol:
                            out.append((f, p))
                return out

            with_abs = hit(True)
            without = hit(False)
            if with_abs and not without:
                n += 1
                f0, p0 = with_abs[0]
                print("  %-15s token=%-12s dec=%-2d  冻结值=%-14.6g 符号%s"
                      "  路径=%s"
                      % (name, tok, dec, f0,
                         "相反" if (v * f0) < 0 else "相同", p0))
                print("      原文：%s" % line[:96])
    print()
    print("  合计 %d 个（范围：23 篇全部带小数 token；判据 direct/x100/div100）"
          % n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
