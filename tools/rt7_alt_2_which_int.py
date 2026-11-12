# -*- coding: utf-8 -*-
"""红队第二板探针 2：把「整数纳入判决会让 N 道题变红」里的 N 与那份名单查清。

只读，只打印。

要回答三件事
  1. V1（整数全判）里，pop_panel / life_exp 变红，靠的是哪些整数？它们是不是
     lead 说的 Pareto 前沿表 Design 行号（1009/1016/1037）？
  2. `1009 / 1016 / 1037` 这三个字面量在 23 篇 paper.tex 里到底出现过没有？
  3. 「4 道题变红」这个数字，换哪些判决参数能凑出 4？换哪些凑不出？

用法
    python tools/rt7_alt_2_which_int.py
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import freeze as F          # noqa: E402
import untraced as U        # noqa: E402
import verify as V          # noqa: E402

RUNS = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))


def dirs():
    out = []
    for name, it in RUNS.items():
        d = os.path.join(HERE, it["out"])
        if os.path.exists(os.path.join(d, "paper.tex")):
            out.append((name, d))
    return out


def judge(tex, frozen, data_values=None, must=3, max_untraced=0.10,
          single_point=False, tok_keep=None, tol_fn=None):
    tok_keep = tok_keep or (lambda t: "." in t)
    if tol_fn is None:
        tol_fn = lambda dec: 0.5 * (10.0 ** -dec) * (1.0 + 1e-9)   # noqa: E731
    _all = V.extract_numbers(tex, skip_meta=False)
    toks = [t for t, _line in _all if tok_keep(t)]
    pairs = []
    for tok in toks:
        try:
            v = float(tok)
        except ValueError:
            continue
        if v != v or v in (float("inf"), float("-inf")):
            continue
        pairs.append((tok, v, V._written_decimals(tok)))
    seen, uniq = set(), []
    for tok, v, dec in pairs:
        key = (round(v, 6), dec)
        if key in seen:
            continue
        seen.add(key)
        uniq.append((tok, v, dec))

    frozen_vals = [it["value"] for it in frozen.get("items", [])]

    def match(v, dec):
        tol = tol_fn(dec)
        for f in frozen_vals:
            for cv, cf in ((abs(v), abs(f)), (abs(v), abs(f) * 100.0),
                           (abs(v), abs(f) / 100.0)):
                if abs(cv - cf) <= tol:
                    return True
        return False

    traced, untraced = [], []
    for tok, v, dec in uniq:
        if match(v, dec):
            traced.append(tok)
        elif data_values and round(v, 6) in data_values:
            traced.append(tok)
        else:
            untraced.append((tok, v, dec))
    n = len(uniq)
    ratio = (len(untraced) / n) if n else 0.0
    hp = [(t, v, d) for t, v, d in untraced if d >= 3]
    reasons = []
    if n < must:
        reasons.append("few")
    if ratio > max_untraced:
        reasons.append("ratio>%.0f%%" % (100 * max_untraced))
    if single_point and hp:
        reasons.append("single_point(%d)" % len(hp))
    return dict(ok=not reasons, reasons=reasons, n=n, n_traced=len(traced),
                ratio=round(ratio, 4), untraced=untraced, hp=hp)


def load(name, d):
    tex = io.open(os.path.join(d, "paper.tex"), encoding="utf-8").read()
    fz = json.load(io.open(os.path.join(d, "冻结数字.json"),
                           encoding="utf-8"))
    return tex, fz, U.data_values_of(U.find_data_file(d))


def main():
    rows = dirs()

    # ── 1. V1 里整数未溯源的明细 ─────────────────────────────────────
    print("== [1] V1（整数全判）里，各题新增的未溯源整数是哪些值 ==")
    print("    判据：tok_keep=全部，dec=_written_decimals，整数 dec=0，tol=0.5")
    for name, d in rows:
        tex, fz, dv = load(name, d)
        r = judge(tex, fz, dv, tok_keep=lambda t: True)
        ints = [(t, v) for t, v, dec in r["untraced"] if dec == 0]
        if not ints:
            continue
        print("  %-16s %-4s ratio=%5.1f%%  未溯源整数 %3d 个"
              % (name, "PASS" if r["ok"] else "FAIL", 100 * r["ratio"],
                 len(ints)))
        vals = [v for _t, v in ints]
        print("     值域 [%s, %s]；样例：%s"
              % (("%.0f" % min(vals)) if vals else "-",
                 ("%.0f" % max(vals)) if vals else "-",
                 ", ".join(t for t, _v in ints[:24])))
        # 这些整数是否落在「前沿表行号」区间（1000~3000）
        in_win = [v for v in vals if 1000 <= v <= 3000]
        print("     其中 1000<=v<=3000 的：%d 个" % len(in_win))

    # ── 2. lead 点名的三个字面量 ─────────────────────────────────────
    print()
    print("== [2] 字面量 1009 / 1016 / 1037 在 23 篇 paper.tex 里出现过吗 ==")
    print("    搜索范围：out/runs/*/paper.tex + out/d2026c/paper.tex")
    print("    排除规则：无（整文件原文检索，正则 \\\\b 词边界）")
    hit = {}
    for pat in ("1009", "1016", "1037"):
        where = []
        for name, d in rows:
            raw = io.open(os.path.join(d, "paper.tex"),
                          encoding="utf-8").read()
            for m in re.finditer(r"(?<![0-9.])" + pat + r"(?![0-9.])", raw):
                where.append((name, raw.count("\n", 0, m.start()) + 1))
        hit[pat] = where
        if where:
            print("  %s: 命中 %d 次 → %s" % (pat, len(where),
                                             where[:8]))
        else:
            print("  %s: 0 次（23 篇里都找不到）" % pat)

    # ── 3. 「4 道题变红」能不能凑出来 ────────────────────────────────
    print()
    print("== [3] 扫判决参数，看「由绿转红」的题数 ==")
    print("    基线：tok_keep=带小数 → 全部 PASS（见探针 1 的 [1]）")
    print("  %-28s %-8s %s" % ("参数组", "转红题数", "名单"))

    def run(label, keep, single_point, max_untraced=0.10):
        base = {}
        red = []
        for name, d in rows:
            tex, fz, dv = load(name, d)
            b = judge(tex, fz, dv)                       # 基线
            r = judge(tex, fz, dv, tok_keep=keep,
                      single_point=single_point,
                      max_untraced=max_untraced)
            base[name] = b
            if b["ok"] and not r["ok"]:
                red.append("%s(%s)" % (name, ",".join(r["reasons"])))
        print("  %-28s %-8d %s" % (label, len(red),
                                   red if len(red) <= 6 else "%d 题" % len(red)))
        return red

    all_tok = lambda t: True                              # noqa: E731

    def not_a_struct(T):
        def keep(t):
            if "." in t:
                return True
            try:
                v = float(t.strip())
            except ValueError:
                return False
            return not (abs(v) <= T)
        return keep

    run("整数全判, sp=off, thr=10%", all_tok, False)
    run("整数全判, sp=on,  thr=10%", all_tok, True)
    run("整数全判, sp=off, thr=20%", all_tok, False, 0.20)
    run("整数全判, sp=off, thr=5%", all_tok, False, 0.05)
    run("整数全判, sp=on,  thr=5%", all_tok, True, 0.05)
    run("非A_struct整数, T=1000, sp=off", not_a_struct(1000), False)
    run("非A_struct整数, T=2000, sp=off", not_a_struct(2000), False)
    run("非A_struct整数, T=1000, sp=on", not_a_struct(1000), True)
    run("非A_struct整数, T=2000, sp=on", not_a_struct(2000), True)
    print()
    print("  sp = single_point（dec>=3 未溯源即判死）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
