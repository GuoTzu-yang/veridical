#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mark_finding.py —— 按「板块 + 证据」给一条 finding 标处置状态。

`close_finding.py` 是「证据变了、把它指到新文本」；本工具是「证据没变，
但这条已经处理完了」。两者分开，是因为混在一起会让人以为每次都要改 evidence。

用法：
    python tools/mark_finding.py --section claims --evidence "frozen table" \
        --disp fixed --why "L1243 已改为分口径陈述（37/184），并补了重冻步骤"
    python tools/mark_finding.py --section results --evidence "xxx" \
        --disp blocked --why "现存工件无法裁决：..." --apply

不带 --apply 只预演。
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
    ev = arg(argv, "--evidence")
    disp = arg(argv, "--disp")
    why = arg(argv, "--why")
    apply_ = "--apply" in argv
    if not (sec and ev and disp in ("fixed", "blocked", "open") and why):
        print(__doc__)
        return 2

    p = os.path.join(FINAL, "redteam.json")
    j = json.load(io.open(p, encoding="utf-8"))
    hit = 0
    for r in j["reviews"]:
        if r.get("section") != sec:
            continue
        for pr in r.get("probes") or []:
            if pr.get("verdict") != "finding":
                continue
            if str(pr.get("evidence") or "") != ev:
                continue
            hit += 1
            pr["disposition"] = disp
            if disp == "blocked":
                pr["blocked_reason"] = why
            pr["note"] = str(pr.get("note") or "") + \
                "  [第 123 轮 %s：%s]" % (disp, why)

    if not hit:
        print("没找到 section=%r evidence=%r 的 finding" % (sec, ev))
        return 1
    print("命中 %d 条 → %s" % (hit, disp))
    if not apply_:
        print("（预演。加 --apply 落盘）")
        return 0
    with io.open(p, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(j, fh, ensure_ascii=False, indent=1)
    print("已写 %s" % os.path.relpath(p, HERE))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
