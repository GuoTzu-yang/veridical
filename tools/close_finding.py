#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""close_finding.py —— 把一条 finding 的证据更新为「修复后的文本」，并记录修法。

背景（第 123 轮）：finding 的 evidence 必须**逐字存在**于 where 文件里
（那正是它防造假的方式）。所以修了论文之后，旧 evidence 必然失效，
gate 会报「evidence 找不到」—— 这不是故障，是机制在正确工作。

要关掉它不能靠「删掉这条 finding」，只能靠**把证据指向修复后的文本**，
并把 `resolved` 写成「改了哪个文件哪句话、为什么」。

用法：
    python tools/close_finding.py --section evaluation \
        --old "under five seconds for the" --new "under seven seconds for the" \
        --why "L1122 由 under five 改为 under seven，与 tab_timing.tex 的 6.68 s 对齐"

不带 --apply 时只预演。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

FINAL = os.path.join(HERE, "out", "final")


def arg(argv, name, default=""):
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv):
            return argv[i + 1]
    return default


def main(argv):
    sec = arg(argv, "--section")
    old = arg(argv, "--old")
    new = arg(argv, "--new")
    why = arg(argv, "--why")
    apply = "--apply" in argv
    if not (sec and old and new and why):
        print(__doc__)
        return 2

    p = os.path.join(FINAL, "redteam.json")
    j = json.load(io.open(p, encoding="utf-8"))
    hit = 0
    for r in j["reviews"]:
        if r.get("section") != sec:
            continue
        # 用局部计数器：`hit` 是跨 review 累积的，若直接用它做条件，
        # 第一条命中之后**同一板块的每一条**都会被改成 open（实测把
        # analysis 的 4 条从 fixed 误改成 open，40 条全 open）。
        local = 0
        for pr in r.get("probes") or []:
            if str(pr.get("evidence") or "") == old:
                local += 1
                hit += 1
                pr["evidence"] = new
                # 处置状态写在**这一条 finding** 上，不写整条 review：
                # 一条 review 有 4 条 finding，修 1 条不该把另外 3 条也关掉。
                pr["disposition"] = "fixed"
                pr["note"] = str(pr.get("note") or "") + \
                    "  [第 123 轮已修：%s" % why + "]"
        if local:
            r["resolved"] = ("第 123 轮：" + why
                             + "。其余 finding 的处置见各自的 disposition。")
            # 不在这里写 review 级 disposition —— 那会把同板其他 finding 一起改状态。
    if not hit:
        print("没找到 evidence == %r 的 finding" % old)
        return 1
    print("命中 %d 条，evidence %r → %r" % (hit, old, new))
    if not apply:
        print("（预演。加 --apply 落盘）")
        return 0
    with io.open(p, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(j, fh, ensure_ascii=False, indent=1)
    print("已写 %s" % os.path.relpath(p, HERE))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
