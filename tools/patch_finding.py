#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_finding.py —— 按「板块 + 探针序号」改一条 finding 的证据/状态。

为什么需要它：`close_finding.py` 用 `--old <evidence>` 匹配，而
**PowerShell 5.1 把含双引号的参数传给原生程序时会吃掉引号**
（`n_rounds": 8` 变成 `n_rounds: 8`），于是 `--old` 永远匹配不上。
按序号定位可以完全绕开 shell 引号问题。

用法：
    python tools/patch_finding.py --section results --index 3 \
        --set-evidence 'n_rounds": 9' --disp fixed \
        --why "重采集后 vacuous-check 8->9，论文与工件同步"

    # 只改状态，不动证据
    python tools/patch_finding.py --section claims --index 1 --disp blocked \
        --blocked "现存工件无法裁决：..." --why "..."
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINAL = os.path.join(HERE, "out", "final")


def arg(argv, name, default=None):
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv):
            return argv[i + 1]
    return default


def main(argv):
    sec = arg(argv, "--section")
    idx = arg(argv, "--index")
    ev = arg(argv, "--set-evidence")
    # PowerShell 5.1 传原生程序时会吃掉参数里的双引号
    # （`n_rounds": 9` → `n_rounds: 9`），所以再给一个 base64 入口：
    #   [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($s))
    # 里面没有任何 shell 元字符，传递无损。
    ev_b64 = arg(argv, "--set-evidence-b64")
    if ev_b64:
        import base64
        try:
            ev = base64.b64decode(ev_b64).decode("utf-8")
        except Exception as e:                      # noqa: BLE001
            print("--set-evidence-b64 解码失败：%s" % e)
            return 2
    disp = arg(argv, "--disp")
    blocked = arg(argv, "--blocked")
    rejected = arg(argv, "--rejected")
    falsifier = arg(argv, "--falsifier")
    set_probe = arg(argv, "--set-probe")
    why = arg(argv, "--why")
    apply_ = "--apply" in argv

    if not (sec and idx is not None and why):
        print(__doc__)
        return 2
    try:
        idx = int(idx)
    except ValueError:
        print("--index 必须是整数（探针序号，从 0 开始）")
        return 2
    if disp and disp not in ("fixed", "blocked", "open", "rejected"):
        print("--disp 只能是 fixed / blocked / open / rejected")
        return 2

    p = os.path.join(FINAL, "redteam.json")
    j = json.load(io.open(p, encoding="utf-8"))
    target = None
    for r in j["reviews"]:
        if r.get("section") == sec:
            probes = r.get("probes") or []
            if 0 <= idx < len(probes):
                target = probes[idx]
            break
    if target is None:
        print("没找到 section=%r index=%d" % (sec, idx))
        return 1
    if target.get("verdict") != "finding":
        print("该探针不是 finding（verdict=%r），不改" % target.get("verdict"))
        return 1

    print("改前：evidence=%r disp=%r"
          % (str(target.get("evidence"))[:40], target.get("disposition")))
    if ev is not None:
        target["evidence"] = ev
    if disp:
        target["disposition"] = disp
    if blocked:
        target["blocked_reason"] = blocked
    if rejected:
        target["rejected_reason"] = rejected
    if falsifier:
        target["falsifier"] = falsifier
    if set_probe:
        target["probe"] = set_probe
    target["note"] = str(target.get("note") or "") + \
        "  [第 123 轮：%s]" % why

    print("改后：evidence=%r disp=%r"
          % (str(target.get("evidence"))[:40], target.get("disposition")))
    if not apply_:
        print("（预演。加 --apply 落盘）")
        return 0
    with io.open(p, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(j, fh, ensure_ascii=False, indent=1)
    print("已写 %s" % os.path.relpath(p, HERE))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
