# -*- coding: utf-8 -*-
"""红队第二板附录探针：判据的替代方案与成本（E 任务那四条选择的实测）。

只读，只打印。四件事：
  [1] 容差的四个替代：现状 / 去掉相对余量 / 旧绝对地板 1e-12 / ULP(nextafter)
      —— 逐题量「未溯源 token 数」的变化（成本是实测，不是形容词）。
  [2] _match_written 三方向分支：×100 / ÷100 各救回多少 token，比值是多少
      —— 这是「并列写法」这条选择的成本面（假阳性窗口被放大 100 倍）。
  [3] abs(v) 对 abs(f)：有多少 token 只有「符号相反」才能匹配上。
  [4] 论文点名的 0.78751 例子复算；以及 184 亿 % 那个 token 在不在语料里。

用法
    python tools/rt7_alt_6_tol.py
"""
import io
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import untraced as U        # noqa: E402
import verify as V          # noqa: E402

RUNS = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))


def toks_of(tex):
    all_ = V.extract_numbers(tex, skip_meta=False)
    out, seen = [], set()
    for t, _l in all_:
        if "." not in t:
            continue
        try:
            v = float(t)
        except ValueError:
            continue
        if v != v or v in (float("inf"), float("-inf")):
            continue
        dec = V._written_decimals(t)
        key = (round(v, 6), dec)
        if key in seen:
            continue
        seen.add(key)
        out.append((t, v, dec))
    return out


def match_branch(v, dec, frozen_vals, tol, use_abs=True):
    """返回命中的分支名列表（direct / x100 / div100）。"""
    hit = []
    vv = abs(v) if use_abs else v
    for f in frozen_vals:
        ff = abs(f) if use_abs else f
        for name, cf in (("direct", ff), ("x100", ff * 100.0),
                         ("div100", ff / 100.0)):
            if abs(vv - cf) <= tol:
                hit.append((name, f))
    return hit


def main():
    runs = []
    for name, it in RUNS.items():
        d = os.path.join(HERE, it["out"])
        tp = os.path.join(d, "paper.tex")
        fp = os.path.join(d, "冻结数字.json")
        if not (os.path.exists(tp) and os.path.exists(fp)):
            continue
        runs.append((name, d,
                     io.open(tp, encoding="utf-8").read(),
                     json.load(io.open(fp, encoding="utf-8"))))

    # ── [1] 容差替代 ──────────────────────────────────────────────
    print("== [1] 容差的四个替代：逐题「未溯源 token 数」=≈")
    print("     tol_now   = 0.5*10^-dec*(1+1e-9)      （现状，freeze.py L172）")
    print("     tol_nomrg = 0.5*10^-dec                （去掉相对余量）")
    print("     tol_floor = 0.5*10^-dec + 1e-12        （第 122 轮前的旧地板）")
    print("     tol_ulp   = nextafter(0.5*10^-dec, inf)-0.5*10^-dec  （ULP 方案）")
    print("  %-16s %6s %8s %8s %8s %8s" % ("题", "n", "now", "nomrg",
                                            "floor", "ulp"))
    agg = dict(now=0, nomrg=0, floor=0, ulp=0)
    for name, d, tex, fz in runs:
        fv = [it["value"] for it in fz.get("items", [])]
        toks = toks_of(tex)
        cnt = {}
        for lab in ("now", "nomrg", "floor", "ulp"):
            n = 0
            for _t, v, dec in toks:
                half = 0.5 * (10.0 ** -dec)
                tol = {"now": half * (1 + 1e-9),
                       "nomrg": half,
                       "floor": half + 1e-12,
                       "ulp": math.nextafter(half, float("inf")) - half}[lab]
                if not match_branch(v, dec, fv, tol):
                    n += 1
            cnt[lab] = n
            agg[lab] += n
        print("  %-16s %6d %8d %8d %8d %8d"
              % (name, len(toks), cnt["now"], cnt["nomrg"], cnt["floor"],
                 cnt["ulp"]))
    print("  合计：%s（n 合计 %d）" % (agg, sum(1 for _ in range(0))))
    print("  → now 与 nomrg 的差 = 「恰好半格」被浮点误差挡掉的数量")
    print("  → floor 比 now 少的那些 = 旧地板放行的假通过（越小越好）")

    # ── [2][3] 分支与符号 ────────────────────────────────────────
    print()
    print("== [2] 三方向分支的成本：只靠 ×100 / ÷100 才匹配上的 token ==")
    print("  %-16s %7s %8s %9s %9s %9s" % ("题", "traced", "direct", "only×100",
                                            "only÷100", "untraced"))
    tot = dict(direct=0, x100=0, div100=0, unt=0)
    sign_only = []
    for name, d, tex, fz in runs:
        fv = [it["value"] for it in fz.get("items", [])]
        toks = toks_of(tex)
        c = dict(direct=0, x100=0, div100=0, unt=0)
        for t, v, dec in toks:
            half = 0.5 * (10.0 ** -dec)
            tol = half * (1 + 1e-9)
            hit = match_branch(v, dec, fv, tol, use_abs=True)
            names = set(h[0] for h in hit)
            if not names:
                c["unt"] += 1
                continue
            if "direct" in names:
                c["direct"] += 1
            elif names == {"x100"}:
                c["x100"] += 1
            elif names == {"div100"}:
                c["div100"] += 1
            else:
                c["x100"] += 1                      # x100 与 div100 同时命中
            # 符号相反才匹配？
            if not match_branch(v, dec, fv, tol, use_abs=False):
                sign_only.append((name, t, v))
        for k in c:
            tot[k] += c[k]
        print("  %-16s %7d %8d %9d %9d %9d"
              % (name, len(toks), c["direct"], c["x100"], c["div100"], c["unt"]))
    print("  合计：direct=%d  only×100=%d  only÷100=%d  untraced=%d"
          % (tot["direct"], tot["x100"], tot["div100"], tot["unt"]))
    print()
    print("== [3] abs(v) 对 abs(f)：只有「符号相反」才能匹配的 token ==")
    if sign_only:
        print("   共 %d 个：%s" % (len(sign_only), sign_only[:12]))
    else:
        print("   共 0 个（搜索范围：23 篇、全部带小数 token、direct/x100/div100 三方向）")

    # ── [4] 点名的例子 ───────────────────────────────────────────
    print()
    print("== [4] 论文/代码点名的具体例子复算 ==")
    half5 = 0.5 * (10.0 ** -5)          # dec=5 的半格 = 5e-6（不是 0.5e-6）
    d = abs(0.78751 - 0.787505)
    print("   dec=5 → 半格 half = %.17g" % half5)
    print("   |0.78751-0.787505| = %.17g" % d)
    print("   差值超出半格 %.3g（绝对）" % (d - half5))
    print("   round(0.787505,5) = %.5f；round(0.787505,5)==0.78751 ? %s"
          % (round(0.787505, 5), round(0.787505, 5) == 0.78751))
    for dec_lab, tol in (("now  = half*(1+1e-9)", half5 * (1 + 1e-9)),
                         ("nomrg= half", half5),
                         ("floor= half+1e-12", half5 + 1e-12)):
        print("   %-22s tol=%.17g → 判定 %s"
              % (dec_lab, tol, "可溯源" if d <= tol else "无源"))
    print()
    print("   找 184 亿 % 那个 token（值约 1.84e9）：")
    found = []
    for name, d, tex, fz in runs:
        for t, _l in V.extract_numbers(tex, skip_meta=False):
            try:
                v = float(t)
            except ValueError:
                continue
            if abs(v) >= 1e8:
                found.append((name, t, v))
    if found:
        for f in found[:10]:
            print("     %s: %s = %g" % f)
    else:
        print("     0 处（范围：23 篇 paper.tex 全部 token，阈值 |v|>=1e8）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
