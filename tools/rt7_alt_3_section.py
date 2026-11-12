# -*- coding: utf-8 -*-
"""红队第二板（主任务）探针：审 out/final/paper.tex L279-476 的 Method 节。

只读，只打印。不写任何产物。

要产出的事实
  1. Table tab:methods 有几行、每行有没有「被否掉的替代」和「什么会改主意」。
  2. Method 节里出现的其他机制（散文里的），有没有被否掉的替代。
  3. 「0.12 s per report」这个成本实测值：能不能复现？复现出来是多少？
  4. 「a handful of tokens」这类形容词成本的原文位置。
  5. Method 节引用的数字（713/11/357/39/15161/1.6%）在纸上是多少（只记录，不判）。
  6. 代码侧证据的字面标记（供 finding 的 where/evidence 复用）。

用法
    python tools/rt7_alt_3_section.py
"""
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

PAPER = os.path.join(HERE, "out", "final", "paper.tex")
L0, L1 = 279, 476


def read_lines():
    return io.open(PAPER, encoding="utf-8").read().splitlines()


def main():
    lines = read_lines()
    sec = lines[L0 - 1:L1]
    print("== [A] 审的对象 ==")
    print("  文件：out/final/paper.tex")
    print("  行范围：L%d–L%d（实测读到 %d 行）" % (L0, L1, len(sec)))
    print("  首行：%s" % lines[L0 - 1].strip()[:70])
    print("  末行：%s" % lines[L1 - 1].strip()[:70])
    print()

    # ── B. 三列对照表的行与「会改主意」────────────────────────────
    print("== [B] Table tab:methods：行数 / 每行的替代 / 每行的 falsifier ==")
    t0 = next(i for i, s in enumerate(sec) if "Mechanism & Rejected alternative" in s)
    t1 = next(i for i, s in enumerate(sec) if "\\end{tabular}" in s
              and i > t0)
    body = "\n".join(sec[t0:t1])
    print("  表体在 L%d–L%d" % (L0 + t0, L0 + t1))
    print("  出现 'Would change if'：%d 次" % body.count("Would change if"))
    print("  出现 'would change our mind'：%d 次"
          % body.count("would change our mind"))
    # 每行以 & 开头，用 \midrule 之后到 \bottomrule 之前切
    try:
        i_mid = body.index("\\midrule")
        i_bot = body.index("\\bottomrule")
    except ValueError:
        print("  没找到 midrule/bottomrule")
        return 1
    rows = [r.strip() for r in body[i_mid + len("\\midrule"):i_bot].split("\n")
            if r.strip()]
    print("  表体行数（去掉空行）：%d" % len(rows))
    for k, r in enumerate(rows, 1):
        has = "Would change if" in body and k == 1
        print("   行%d %s" % (k, r[:96].replace("\n", " ")))
    print()
    print("  → 逐行判定 falsifier（列头承诺 'what would change our mind'）：")
    # 按 markdown 里行首大写的机制名切行
    mech_marks = ["Freeze every computed", "Classify tokens before",
                  "Windowed counterexample", "Eight channels with a veto",
                  "Fail-closed on missing", "Digest-bound stamp"]
    joined = re.sub(r"\s+", " ", body)
    for m in mech_marks:
        i = joined.find(m)
        j = min((joined.find(n, i + 1) for n in mech_marks
                 if joined.find(n, i + 1) > 0), default=len(joined))
        chunk = joined[i:(j if j > 0 else len(joined))]
        has_wci = "Would change if" in chunk
        has_alt = "&" in chunk
        print("   %-30s 替代=%s  falsifier=%s%s"
              % (m[:30], "有" if has_alt else "无",
                 "有" if has_wci else "无",
                 "" if has_wci else "   <== 列头承诺 vs 单元格空缺"))
    print()

    # ── C. 散文里的其他机制有没有被否掉的替代 ─────────────────────
    print("== [C] 散文里出现的机制 vs 是否配了被否掉的替代 ==")
    pats = [
        ("按构造而非搜索", r"by construction rather than by search"),
        ("不放大上下文窗口", r"We do not attempt to fix"),
        ("状态外置到冻结表", r"The state lives outside the context"),
        ("锚定工具只回未溯源句", r"the anchoring tool reads the paper"),
        ("门禁构成 29 项/12 硬", r"Gate composition"),
        ("四天日程分配", r"the first day diagnoses"),
    ]
    for label, pat in pats:
        for i, s in enumerate(sec):
            if re.search(pat, s):
                ln = L0 + i
                ctx = re.sub(r"\s+", " ", s.strip())
                # 该句前后 2 行里有没有「被否掉的替代」信号词
                win = re.sub(r"\s+", " ",
                             " ".join(sec[max(0, i - 2):i + 3]))
                sig = [w for w in ("reject", "instead", "rather than",
                                   "not a straw man", "alternative",
                                   "we do not", "displaced")
                       if w.lower() in win.lower()]
                print("   %-22s L%-4d 替代信号=%s" % (label, ln,
                    sig if sig else "（无 —— 该机制没有配被否掉的替代）"))
                print("       %s" % ctx[:110])
                break
    print()

    # ── D. 成本：形容词 vs 实测值 ─────────────────────────────────
    print("== [D] 成本表述：逐条摘出，标注是数字还是形容词 ==")
    cost_pats = [
        (r"measured at ([\d.]+)\\?,?s per report", "数字"),
        (r"a handful of tokens", "形容词"),
        (r"nothing here is expensive enough", "形容词/判断"),
        (r"needs 11, at 357 tokens", "数字"),
        (r"median among sections that quote any number is ([\d]+)", "数字"),
        (r"no section needs more than ([\d.]+)\\%", "数字"),
        (r"has ([\d]+) entries", "数字"),
    ]
    for pat, kind in cost_pats:
        hit = False
        for i, s in enumerate(sec):
            m = re.search(pat, re.sub(r"\s+", " ", s))
            if m:
                ln = L0 + i
                print("   L%-4d [%s] %s" % (ln, kind, m.group(0)))
                hit = True
        if not hit:
            print("   [没找到] %s" % pat)
    print()

    # ── E. 「0.12 s per report」能不能复现 ────────────────────────
    print("== [E] 复现 0.12 s per report（trace 单篇耗时，23 题）==")
    import verify as V
    RUNS = json.load(io.open(os.path.join(HERE, "runs.json"),
                             encoding="utf-8"))
    ts = []
    for name, it in RUNS.items():
        d = os.path.join(HERE, it["out"])
        tex_p = os.path.join(d, "paper.tex")
        if not os.path.exists(tex_p):
            continue
        tex = io.open(tex_p, encoding="utf-8").read()
        outs = V.load_outputs(d)                      # 读产物（一次性开销）
        t = time.perf_counter()
        V.trace(tex, outs)
        dt = time.perf_counter() - t
        ts.append((name, dt))
    ts.sort(key=lambda x: x[1])
    if ts:
        vals = [x[1] for x in ts]
        print("   n=%d  最小 %.4fs  中位 %.4fs  最大 %.4fs  均值 %.4fs"
              % (len(vals), vals[0], vals[len(vals) // 2], vals[-1],
                 sum(vals) / len(vals)))
        print("   最慢三题：%s" % ", ".join("%s=%.3fs" % (n, v)
                                           for n, v in ts[-3:]))
        print("   论文写的是 0.12 s per report；实测中位 %.3fs，"
              "差值 %.3fs" % (vals[len(vals) // 2],
                              vals[len(vals) // 2] - 0.12))
    print()

    # ── F. 数字侧：713 条冻结表 ──────────────────────────────────
    print("== [F] 本节数字的可核对项（只记录，不判；判是 results 板的事）==")
    fz = json.load(io.open(os.path.join(HERE, "out", "final", "冻结数字.json"),
                           encoding="utf-8")) \
        if os.path.exists(os.path.join(HERE, "out", "final",
                                       "冻结数字.json")) else {}
    print("   out/final/冻结数字.json 存在=%s  条目 n=%s"
          % (bool(fz), fz.get("n")))
    print()

    # ── G. 代码侧字面标记（finding 用）────────────────────────────
    print("== [G] finding 要引用的字面标记是否真的逐字存在 ==")
    marks = [
        ("untraced.py", "if not has_dot and abs(v) <= 1000:"),
        ("untraced.py", "A_struct    行号/表号/章节号/样本量"),
        ("paper.py", "_MAX_FRONT_ROWS = 12"),
        ("paper.py", "列表的意义在于「显示前沿的形状」"),
        ("freeze.py", "全判会制造大量假阳性"),
        ("out/final/paper.tex", "Would change if"),
        ("out/final/paper.tex", "a handful of tokens"),
        ("out/final/paper.tex", "the anchoring tool reads the paper"),
        ("out/final/paper.tex", "What would change our mind"),
    ]
    for f, mk in marks:
        p = os.path.join(HERE, f)
        body = io.open(p, encoding="utf-8", errors="replace").read()
        print("   %-22s %-42s %s" % (f, mk[:42],
                                     "存在" if mk in body else "缺失"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
