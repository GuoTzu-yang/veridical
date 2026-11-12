# -*- coding: utf-8 -*-
"""红队第二板（alternative-auditor）探针 1：判据的判决语义复刻 + 变体对照。

只读。不写任何产物，只打印。

目的
----
1. 复刻 freeze.check_paper 的判决回路，并**证明复刻等价**（同一批 23 题上，
   ok / n_numbers / n_traced 与真函数逐题一致）。不等价就退出，后面全部作废。
2. 在同一回路上换「纳入哪些 token」这一条判据，量出代价：
   V0 现状（只判带小数）
   V1 全判（整数也判）
   V2 整数判，但 classify_token 判为 A_struct 的跳过；A_struct 门槛可扫
3. 顺带把「D_computed 里到底是谁」数出来（Design 列行号 vs 别的）。

用法
    python tools/rt7_alt_1_judge.py
"""
import io
import json
import os
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


# ── 复刻：与 freeze.check_paper 同语义，token 选择与容差可注入 ──────────
def judge(tex, frozen, data_values=None, must=3, max_untraced=0.10,
          tok_keep=None, dec_of=None, tol_fn=None):
    """freeze.check_paper 的判决回路，可注入 tok_keep / tol_fn。"""
    tok_keep = tok_keep or (lambda t: "." in t)
    dec_of = dec_of or V._written_decimals
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
        pairs.append((v, dec_of(tok)))
    seen, uniq = set(), []
    for v, dec in pairs:
        key = (round(v, 6), dec)
        if key in seen:
            continue
        seen.add(key)
        uniq.append((v, dec))

    frozen_vals = [it["value"] for it in frozen.get("items", [])]

    def match(v, dec):
        tol = tol_fn(dec)
        for f in frozen_vals:
            for cand_v, cand_f in ((abs(v), abs(f)),
                                   (abs(v), abs(f) * 100.0),
                                   (abs(v), abs(f) / 100.0)):
                if abs(cand_v - cand_f) <= tol:
                    return True
        return False

    traced, untraced = [], []
    n_data = 0
    for v, dec in uniq:
        if match(v, dec):
            traced.append(v)
        elif data_values and round(v, 6) in data_values:
            traced.append(v)
            n_data += 1
        else:
            untraced.append((v, dec))

    n = len(uniq)
    ratio = (len(untraced) / n) if n else 0.0
    hp = [(v, d) for v, d in untraced if d >= 3]
    reasons = []
    if n < must:
        reasons.append("few")
    if ratio > max_untraced:
        reasons.append("ratio")
    return dict(ok=not reasons, reasons=reasons, n=n, n_traced=len(traced),
                ratio=round(ratio, 4), n_data=n_data,
                untraced=untraced, hp=hp,
                n_all=len(_all),
                n_int=sum(1 for t, _l in _all if "." not in t))


def main():
    rows = dirs()
    print("语料：%d 题（runs.json 有 paper.tex 的目录）" % len(rows))
    print()

    # ── 0. 复刻等价性：必须逐题一致，否则停止 ─────────────────────────
    print("== [0] 复刻等价性（我的 judge vs freeze.check_paper 原件）==")
    mism = 0
    data_pool = {}
    for name, d in rows:
        tex = io.open(os.path.join(d, "paper.tex"), encoding="utf-8").read()
        fz = json.load(io.open(os.path.join(d, "冻结数字.json"),
                               encoding="utf-8"))
        dv = U.data_values_of(U.find_data_file(d))
        data_pool[name] = dv
        real = F.check_paper(tex, fz, single_point=False,
                             data_values=dv, strict_source=False)
        mine = judge(tex, fz, dv)
        same = (real["ok"] == mine["ok"]
                and real["n_numbers"] == mine["n"]
                and real["n_traced"] == mine["n_traced"])
        if not same:
            mism += 1
            print("  [MISMATCH] %-16s real=%s/%s/%s mine=%s/%s/%s"
                  % (name, real["ok"], real["n_numbers"], real["n_traced"],
                     mine["ok"], mine["n"], mine["n_traced"]))
    print("  不一致 %d 题 / %d 题" % (mism, len(rows)))
    if mism:
        print("  → 复刻不等价，后续变体结论作废")
        return 2

    # ── 1. 基线：V0 ────────────────────────────────────────────────
    print()
    print("== [1] V0 基线（只判带小数的 token；= 现状）==")
    base = {}
    for name, d in rows:
        tex = io.open(os.path.join(d, "paper.tex"), encoding="utf-8").read()
        fz = json.load(io.open(os.path.join(d, "冻结数字.json"),
                               encoding="utf-8"))
        r = judge(tex, fz, data_pool[name])
        base[name] = r
        print("  %-16s %-4s n=%-4d traced=%-4d untraced=%-3d ratio=%5.1f%%  "
              "整数token=%d"
              % (name, "PASS" if r["ok"] else "FAIL", r["n"], r["n_traced"],
                 len(r["untraced"]), 100 * r["ratio"], r["n_int"]))
    n_red0 = sum(1 for r in base.values() if not r["ok"])
    print("  合计：红 %d 题 / %d 题" % (n_red0, len(rows)))

    # ── 2. V1：整数也判 ─────────────────────────────────────────────
    print()
    print("== [2] V1 变体：整数 token 也纳入判决 ==")
    v1 = {}
    flipped = []
    for name, d in rows:
        tex = io.open(os.path.join(d, "paper.tex"), encoding="utf-8").read()
        fz = json.load(io.open(os.path.join(d, "冻结数字.json"),
                               encoding="utf-8"))
        r = judge(tex, fz, data_pool[name], tok_keep=lambda t: True)
        v1[name] = r
        flag = ""
        if base[name]["ok"] and not r["ok"]:
            flag = "  <== 由绿转红"
            flipped.append(name)
        print("  %-16s %-4s n=%-4d traced=%-4d untraced=%-4d ratio=%5.1f%%%s"
              % (name, "PASS" if r["ok"] else "FAIL", r["n"], r["n_traced"],
                 len(r["untraced"]), 100 * r["ratio"], flag))
    n_red1 = sum(1 for r in v1.values() if not r["ok"])
    print("  合计：红 %d 题 / %d 题；由绿转红 %d 题 → %s"
          % (n_red1, len(rows), len(flipped), flipped))

    # ── 3. 转红/新增未溯源的整数到底是谁 ────────────────────────────
    print()
    print("== [3] V1 里新冒出来的未溯源整数（前 20 个，按题）==")
    for name, d in rows:
        newints = [(v, dec) for v, dec in v1[name]["untraced"]
                   if "." not in repr(v)]
        if not newints:
            continue
        print("  %-16s 新增未溯源 %d 个：%s"
              % (name, len(newints),
                 ", ".join("%.0f" % v for v, _dec in newints[:20])))
    print()
    print("  说明：判据里整数 dec=0，tol=0.5；单点严判（dec>=3）对整数永不触发，"
          "所以整数只能通过 untraced_ratio>10% 这一条把题判红。")

    # ── 4. V2：整数判，但 A_struct 的跳过 —— A_struct 门槛扫描 ──────
    print()
    print("== [4] V2 变体：整数判，但 classify_token 判 A_struct 的跳过；"
          "A_struct 门槛 |v|<=T 扫描 ==")
    print("      （A_struct 现状 T=1000；若门槛「太窄」，放大 T 应能让红题消失）")
    print("  %-10s %-8s %s" % ("T", "红题数", "转红的题"))
    for T in (1000, 1500, 2000, 5000, 10000, 100000, 1000000, 10 ** 12):
        red = []
        for name, d in rows:
            tex = io.open(os.path.join(d, "paper.tex"),
                          encoding="utf-8").read()
            fz = json.load(io.open(os.path.join(d, "冻结数字.json"),
                                   encoding="utf-8"))

            def keep(t, T=T):
                if "." in t:
                    return True
                try:
                    v = float(t)
                except ValueError:
                    return False
                return not (abs(v) <= T)      # A_struct 的整数跳过
            r = judge(tex, fz, data_pool[name], tok_keep=keep)
            if not r["ok"]:
                red.append(name)
        print("  %-10s %-8d %s" % (T, len(red), red if len(red) <= 8 else
                                   "%d 题" % len(red)))
    print()
    print("  注：T=1000 那一行应等于「整数里凡是 A_struct 的都跳过」，"
          "可与 [2] V1 对照 —— 两者差的就是 A_struct 挡下的整数。")

    # ── 5. D_computed 到底是谁（untraced.analyse 口径）────────────────
    print()
    print("== [5] untraced.analyse 口径：整数 token 的分类分布 ==")
    print("  %-16s %-6s %-6s %-6s %s" % ("题", "整数", "A_struct", "D_comp",
                                        "被判 D_computed 的整数样例"))
    tot_int = tot_a = tot_d = 0
    for name, d in rows:
        tex = io.open(os.path.join(d, "paper.tex"), encoding="utf-8").read()
        outs = V.load_outputs(d)
        r = V.trace(tex, outs)
        ints = [u for u in (r.get("untraced") or []) if "." not in u["token"]]
        a = [u for u in ints if U.classify_token(u["token"]) == "A_struct"]
        dc = [u for u in ints if U.classify_token(u["token"]) == "D_computed"]
        tot_int += len(ints); tot_a += len(a); tot_d += len(dc)
        samp = ", ".join(u["token"] for u in dc[:6])
        print("  %-16s %-6d %-6d %-6d %s" % (name, len(ints), len(a), len(dc),
                                             samp))
    print("  合计：整数未溯源 %d，A_struct %d，D_computed %d"
          % (tot_int, tot_a, tot_d))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
