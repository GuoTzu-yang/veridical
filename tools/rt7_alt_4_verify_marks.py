# -*- coding: utf-8 -*-
"""红队第二板探针 4：把 finding 的证据串逐字核对 + 缺失项的搜索范围。

只读，只打印。凡是「没有 X」的结论，都在这里打印搜索范围与排除规则。

用法
    python tools/rt7_alt_4_verify_marks.py
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
PAPER = os.path.join(HERE, "out", "final", "paper.tex")
L0, L1 = 279, 476


def main():
    body = io.open(PAPER, encoding="utf-8").read()
    lines = body.splitlines()
    sec = "\n".join(lines[L0 - 1:L1])

    print("== [1] finding 的证据串：逐字存在性（file:line:col）==")
    marks = [
        (PAPER, "states for each what would change our"),
        (PAPER, "Would change if"),
        (PAPER, "measured at 0.12"),
        (PAPER, "a handful of tokens"),
        (PAPER, "Two mechanisms apply the same move"),
        (PAPER, "the anchoring tool reads the paper"),
        (PAPER, "classes need different sources"),
        (os.path.join(HERE, "freeze.py"), "判决仍只用带小数的 token"),
        (os.path.join(HERE, "untraced.py"), "abs(v) <= 1000"),
        (os.path.join(HERE, "paper.py"), "_MAX_FRONT_ROWS = 12"),
    ]
    bad = 0
    for p, s in marks:
        t = io.open(p, encoding="utf-8", errors="replace").read()
        i = t.find(s)
        if i < 0:
            bad += 1
            print("   [缺] %-22s %r" % (os.path.basename(p), s))
            continue
        ln = t.count("\n", 0, i) + 1
        col = i - (t.rfind("\n", 0, i) + 1) + 1
        print("   [有] %-22s L%-5d C%-3d %r" % (os.path.basename(p), ln, col, s))
    print("   缺失 %d 条" % bad)
    print()

    print("== [2] 「本节里没有 falsifier」的搜索范围与排除规则 ==")
    print("   范围：out/final/paper.tex 的 L%d–L%d（含表体 tab:methods 全 6 行）" % (L0, L1))
    print("   方法：小写化后正则子串搜索，允许跨行（先把 \\s+ 折成单空格）")
    flat = re.sub(r"\s+", " ", sec).lower()
    for pat in ("would change", "change if", "falsif", "refut",
                "we would revise", "unless", "fails if", "counter-evidence",
                "disconfirm"):
        n = flat.count(pat)
        print("     %-18s 命中 %d 次" % (pat, n))
    print("   → 'would change' 的全部命中位置（可核对）：")
    for m in re.finditer(r"would change", flat):
        print("       …%s…" % flat[max(0, m.start() - 48):m.end() + 40])
    print()

    print("== [3] 「锚定工具没有被否掉的替代」的搜索范围 ==")
    print("   范围：out/final/paper.tex 全文（1358 行），不限于本节")
    whole = re.sub(r"\s+", " ", body)
    for kw in ("anchor", "anchoring"):
        print("     关键词 %-10s 全文出现 %d 次" % (kw, len(re.findall(kw, body, re.I))))
    for m in re.finditer(r"anchor\w*", body, re.I):
        ln = body.count("\n", 0, m.start()) + 1
        ctx = re.sub(r"\s+", " ", body[max(0, m.start() - 90):m.end() + 90])
        print("       L%-5d …%s…" % (ln, ctx))
    print("   → 在这些上下文里搜被否掉的替代信号词：")
    for w in ("instead", "rather than", "reject", "we do not", "alternative",
              "displaced"):
        hits = [m.start() for m in re.finditer(re.escape(w), sec, re.I)]
        print("     本节里 %-12s 命中 %d 次" % (w, len(hits)))
    print()

    print("== [4] Table tab:methods 六行：每行第三个单元格的原文（判 falsifier 用）==")
    i0 = next(i for i, s in enumerate(lines) if "Mechanism & Rejected alternative" in s)
    i1 = next(i for i, s in enumerate(lines) if "\\bottomrule" in s and i > i0)
    tbl = re.sub(r"\s+", " ", " ".join(lines[i0:i1]))
    cells = [c.strip() for c in tbl.split("&")]
    # 用行尾 \\ 切记录
    recs = [r.strip() for r in tbl.split(r"\\") if r.strip()]
    print("   记录数（按 \\\\ 切）：%d" % len(recs))
    for k, r in enumerate(recs[1:], 1):     # 跳过表头
        parts = [p.strip() for p in r.split("&")]
        third = parts[-1] if parts else ""
        print("   行%d 第3格：%s" % (k, third[:150]))
        print("       falsifier=%s" % ("有" if "Would change if" in third
                                       else "无"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
