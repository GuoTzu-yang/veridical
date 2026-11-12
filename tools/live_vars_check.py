#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""live_vars_check.py —— 论文里的「活变量」还跟工件一致吗。

问题（第 123 轮实测）：论文有一批数字**会随工作变** —— 轮数、记录体量、
带 selftest 的模块数、gate 项数、缺陷分类计数、每题溯源率。
它们全是**整数**或不便匹配的形式，所以 `freeze.check_paper` 的
「只判带小数的 token」这条口径**看不见它们**。

实测后果：一轮工作之后，论文里 `29 checks` / `51 of 51` / `30 rounds` /
`129 kB` 全部过时，而 gate 只报一句「37/37 可溯源」，一个都不提。

本工具把「活变量」和「论文里的字面量」逐项比一遍。它**不是判据**，
是警报器：命中不一致时给出论文行号，由人决定改哪边。

用法：
    python tools/live_vars_check.py            # 人读
    python tools/live_vars_check.py --json     # 结构化
退出码：0 = 全部一致；1 = 有不一致。
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "out", "final")


def load():
    d = json.load(io.open(os.path.join(OUT, "data.json"), encoding="utf-8"))
    tex = io.open(os.path.join(OUT, "paper.tex"),
                  encoding="utf-8", errors="replace").read()
    lines = tex.splitlines()
    return d, tex, lines


def find(lines, pat, group=1, skip=None):
    """返回 [(行号, 命中的数字)]。

    `skip` 是跳过词：正文里会引用**曾经的错误值**（Case 5 的「128 recorded
    rounds」是故事里的假数），把它当成活变量会误报。含跳过词的行不参与比对。
    """
    out = []
    rx = re.compile(pat)
    for i, ln in enumerate(lines, 1):
        if skip and any(s in ln for s in skip):
            continue
        for m in rx.finditer(ln):
            try:
                out.append((i, int(m.group(group))))
            except (IndexError, ValueError):
                pass
    return out


def main(argv):
    d, tex, lines = load()
    tax = d.get("defect_taxonomy") or {}
    rules = [
        # (名字, 期望值, 正则, 取第几组)
        ("gate 项数", d.get("n_gate_checks"),
         r"(\d+)\s+checks", 1),
        ("gate 项数（图注）", d.get("n_gate_checks"),
         r"The (\d+) gate checks", 1),
        ("带 selftest 的模块", d.get("n_modules_with_selftest"),
         r"all (\d+) of \d+", 1),
        ("带 selftest 的模块（图引）", d.get("n_modules_with_selftest"),
         r"(\d+) of \d+ \(Figure", 1),
        ("记录轮数", d.get("n_record_rounds"),
         r"over (\d+) repair", 1),
        ("记录轮数（taxonomy 节）", d.get("n_record_rounds"),
         r"(\d+) recorded", 1),
        ("记录轮数（claims 表）", d.get("n_record_rounds"),
         r"(\d+) rounds of a", 1),
        ("记录体量 kB", round((d.get("record_bytes") or 0) / 1024.0),
         r"(\d+)\\,kB", 1),
    ]
    for cls, label in (("silent-default", "silent default"),
                       ("duplicate-logic", "duplicated logic"),
                       ("vacuous-check", "vacuous check"),
                       ("self-report", "self-report inflation"),
                       ("contract-unenforced", "unenforced contract"),
                       ("self-test-broken", "self-test broken")):
        v = (tax.get(cls) or {}).get("n_rounds")
        if v is not None:
            rules.append((label, v, label + r"s? \((\d+)", 1))

    rows = []
    for name, want, pat, grp in rules:
        # Case 5 讲的是「曾经的错误值」，那里的数字不是活变量。
        hits = find(lines, pat, grp, skip=("earlier abstract", "case 5"))
        for line, got in hits:
            rows.append(dict(name=name, want=want, got=got,
                             ok=(want is not None and got == want), line=line))

    bad = [r for r in rows if not r["ok"]]
    if "--json" in argv:
        print(json.dumps(dict(rows=rows, mismatches=len(bad)),
                         ensure_ascii=False, indent=1))
    else:
        print("活变量比对：%d 处命中，%d 处不一致" % (len(rows), len(bad)))
        for r in rows:
            flag = "OK  " if r["ok"] else "**不一致**"
            print("  %-11s %-26s 论文 L%-5d 写 %-6s 工件 %-6s"
                  % (flag, r["name"], r["line"], r["got"], r["want"]))
        if bad:
            print()
            print("提示：这些数不在 numbers 门的判定范围内（整数不进候选），")
            print("所以 gate 全绿也可能有它们。改哪边由人定：")
            print("  · 论文过时 → 改 paper.tex，然后 编译×2 → freeze → gate --stamp")
            print("  · 工件过时 → 重跑 tools/collect_paper_data.py")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
