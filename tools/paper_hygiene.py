#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""paper_hygiene.py —— 论文文件本身的卫生检查（第 123 轮）。

这里查的三件事，**都是我自己踩过的**，而且都逃过了 `gate`：

1. **CRLF**
   我用 PowerShell 的 `[IO.File]::WriteAllLines` 批量改论文，它默认写 `\\r\\n`。
   结果 `paper.tex` 多了 1448 个字节（正好等于行数），而 `data2.paper_bytes`
   是 `io.open(...).read()` 算的 —— 它把 CRLF 归一成 LF。两边差 1448，
   `fence_acceptance` 报「S8 paper_bytes 工件过期」，我查了三轮才发现是自己写坏的。
   **gate 不看这个**：它比的是「采集时的数」与「当时的数」，不检查换行符。

2. **自指量**
   「frozen table has 792 entries」这类句子，登记它自己就会改它 ——
   加一条 derived，冻结表 792 → 793，论文永远差一。**这个量不可自洽。**
   已经踩过三层：`n_frozen`、`paper_tokens`、冻结表条目数。
   规矩：论文里不写会随写作变化的量，只写不受影响的关系（如百分比）。

3. **没有 declaration.json**
   目录里有 `paper.tex`，却没有 `declaration.json` —— 于是所有交付标准
   （文献下限、图数下限、敏感性、红队分板）**静默豁免**。
   `out/d2026c` 就是这样瞒了四道门，补上声明后立刻暴露 5 个真缺陷。

用法：
    python tools/paper_hygiene.py out/final
    python tools/paper_hygiene.py --all          # 扫 out/ 下所有有 paper.tex 的目录
退出码：0 = 干净；1 = 有 CRLF 或自指量。
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 自指量的模式：这些数会随「论文怎么写」而变化，写进正文就永远对不上
SELF_REF = [
    (r"frozen table has\s+\d+\s+entries",
     "冻结表条数：登记它自己会改它（792 → 793）"),
    (r"\b\d+\s+tokens of paper\b",
     "论文词数：删一个词就变（17167 → 17161）"),
    (r"\b\d+\s+gate checks\b",
     "门数：加一道门就变，应由 data.json 的 n_gate_checks 供数"),
]


def check_dir(d):
    tex = os.path.join(d, "paper.tex")
    problems, notes = [], []
    if not os.path.exists(tex):
        return None
    raw = io.open(tex, "rb").read()
    crlf = raw.count(b"\r\n")
    if crlf:
        problems.append(f"CRLF {crlf} 处（应为 0）—— "
                        f"`io.open().read()` 会归一成 LF，使 paper_bytes 差 {crlf} 字节；"
                        f"用 [IO.File]::WriteAllText 而非 WriteAllLines")
    text = raw.decode("utf-8", "replace")
    for pat, why in SELF_REF:
        for m in re.finditer(pat, text, re.I):
            line = text[:m.start()].count("\n") + 1
            problems.append(f"L{line} 自指量「{m.group(0)}」—— {why}")
    # declaration.json
    if not os.path.exists(os.path.join(d, "declaration.json")):
        notes.append("没有 declaration.json —— 所有交付标准（文献下限/图数/"
                     "敏感性/红队分板）都会静默豁免。若这是交稿，必须写 "
                     '{\"deliverable\": true}')
    else:
        import json
        try:
            j = json.load(io.open(os.path.join(d, "declaration.json"),
                                  encoding="utf-8"))
            if not j.get("deliverable"):
                notes.append("declaration.json 里没有 deliverable=true —— "
                             "交付标准对它不生效（这是设计如此，但要确认是有意的）")
        except Exception as e:                      # noqa: BLE001
            problems.append(f"declaration.json 读不了：{e}")
    return dict(dir=d, problems=problems, notes=notes)


def main(argv):
    if "--all" in argv:
        dirs = []
        for root, _ds, fs in os.walk(os.path.join(HERE, "out")):
            if "paper.tex" in fs:
                dirs.append(root)
    else:
        dirs = [a for a in argv[1:] if not a.startswith("-")] or \
               [os.path.join(HERE, "out", "final")]
    rows = [r for r in (check_dir(d) for d in dirs) if r]
    bad = [r for r in rows if r["problems"]]
    for r in rows:
        tag = "脏" if r["problems"] else "净"
        print(f"  [{tag}] {os.path.relpath(r['dir'], HERE)}")
        for p in r["problems"]:
            print(f"       ✗ {p}")
        for n in r["notes"]:
            print(f"       · {n}")
    print()
    print(f"检查 {len(rows)} 个目录：脏 {len(bad)}，干净 {len(rows) - len(bad)}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
