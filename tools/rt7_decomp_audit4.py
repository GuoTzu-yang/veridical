# -*- coding: utf-8 -*-
"""rt7_decomp_audit4.py —— 收尾取证：整数型 D_computed 对 gate 的可见性 + 工件时间戳。

只读：不写任何 .py/.tex/.json，只 print。
"""
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import untraced as U
import verify as V
import freeze


def hr(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def papers():
    cfg = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
    out = []
    for nm, it in cfg.items():
        d = os.path.join(HERE, it["out"])
        if os.path.exists(os.path.join(d, "paper.tex")):
            out.append((nm, d))
    return out


def main():
    hr("1  D_computed 里有多少是整数（gate 完全不看的那一半）")
    ints, decs = [], []
    for nm, d in papers():
        tex = io.open(os.path.join(d, "paper.tex"), encoding="utf-8").read()
        r = V.trace(tex, V.load_outputs(d))
        dv = U.data_values_of(U.find_data_file(d))
        for u in r["untraced"]:
            if U.classify_token(u["token"], dv) != "D_computed":
                continue
            (decs if "." in u["token"] else ints).append(
                (nm, u["token"], (u.get("line") or "")[:70]))
    print("  D_computed 合计 = %d ；其中整数 %d，小数 %d"
          % (len(ints) + len(decs), len(ints), len(decs)))
    print("  -> gate 只判小数（freeze.py:209），这 %d 个整数型 D_computed 不可见"
          % len(ints))
    print("\n  整数型 D_computed 全表：")
    for nm, tok, ctx in ints:
        print("    %-12s %-8s | %s" % (nm, tok, ctx))

    hr("2  单点复核：birth_rate 的 1495 在两条链上的判决")
    cfg = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
    d = os.path.join(HERE, cfg["birth_rate"]["out"])
    tex = io.open(os.path.join(d, "paper.tex"), encoding="utf-8").read()
    print("  untraced.py 口径  classify_token('1495') =",
          U.classify_token("1495"))
    fz = json.load(io.open(os.path.join(d, "冻结数字.json"), encoding="utf-8"))
    dv = U.data_values_of(U.find_data_file(d))
    r = freeze.check_paper(tex, fz, single_point=False, data_values=dv,
                           strict_source=False)
    all_toks = V.extract_numbers(tex, skip_meta=False)
    in_gate = [t for t, _ in all_toks if "." in t]
    print("  freeze.check_paper 的口径：")
    print("     n_numbers（只含小数） =", r["n_numbers"])
    print("     1495 在 gate 候选里吗：", "1495" in in_gate)
    print("     1495 在全部 token 里吗：", any(t == "1495" for t, _ in all_toks))
    print("     check_paper 判决 ok =", r["ok"], " reasons =", r["reasons"])

    hr("3  工件时间戳（我跑 --corpus 之前它是什么，只能看时间）")
    for p in ("out/untraced_corpus.json", "out/final/tab_anatomy.tex",
              "out/final/paper.tex", "out/红队-E-验收.md",
              "out/final/redteam.json"):
        fp = os.path.join(HERE, p)
        if os.path.exists(fp):
            st = os.stat(fp)
            print("  %-32s %s  %d bytes" %
                  (p, time.strftime("%Y-%m-%d %H:%M:%S",
                                    time.localtime(st.st_mtime)), st.st_size))
        else:
            print("  %-32s (不存在)" % p)

    hr("4  有没有第二份 untraced_corpus.json（能看出旧值）")
    for root, dirs, files in os.walk(HERE):
        dirs[:] = [x for x in dirs if x not in ("__pycache__", "external", "kb")]
        for f in files:
            if f == "untraced_corpus.json":
                fp = os.path.join(root, f)
                st = os.stat(fp)
                print("  %-56s %s %d bytes" %
                      (os.path.relpath(fp, HERE),
                       time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime)),
                       st.st_size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
