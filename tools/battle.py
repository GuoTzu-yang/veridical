#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""最后会战：按 runs.json 把每道题从数据跑到 PDF，再逐题过 gate。

为什么要脚本化
--------------
手工敲 14 条命令，漏一条就少一道题，而且 y/x/min 记在聊天里、
下次又要重新推。配置写进 runs.json 之后，这里是幂等的：
可以重复跑，也可以只跑某几道（给参数）。

不中断：某道题失败就记下来继续跑下一道，最后统一报告。
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
DATA = os.path.join(HERE, "out", "data")


def load():
    return json.load(open(os.path.join(HERE, "runs.json"), encoding="utf-8"))


def _is_deliverable(d: str) -> bool:
    """这个目录是不是交稿（有 declaration.json 且 deliverable 为真）。"""
    p = os.path.join(d, "declaration.json")
    if not os.path.exists(p):
        return False
    try:
        with open(p, encoding="utf-8") as fh:
            return bool((json.load(fh) or {}).get("deliverable"))
    except Exception:                                   # noqa: BLE001
        return False


# 模板卷的合法落点。第 122 轮的教训：`runs.json` 里 dwts2026c 的 out
# 指向 `out/d2026c`，那是**人工精修的交付稿**（含 evidence.json /
# model_stats.json / paper.before_style.tex 等只有人手才有的产物）。
# 全量跑一次 battle 就会用 `mmkit run` 把它覆盖成模板，而 battle
# 自己还报「OK」。
#
# 只靠 declaration.json 判不够 —— 实测那份文件里**没有** `deliverable`
# 字段（只写了 no_dataset），于是 `_is_deliverable` 返回 False，
# 保护形同虚设，第二次覆盖仍然发生。
# 所以用一道不依赖内容声明的硬边界：**battle 只写 out/runs/ 下面。**
_ONLY_UNDER = os.path.join(HERE, "out", "runs")


def _outside_template_root(d: str) -> str:
    """返回空串表示可以写；否则返回拒绝理由。"""
    od = os.path.abspath(d)
    root = os.path.abspath(_ONLY_UNDER)
    if od != root and not od.startswith(root + os.sep):
        return ("跳过：模板批次只写出 out/runs/ 下的目录，"
                "而该题配的是 %s（人工稿/交付稿不在批量重跑范围内）"
                % os.path.relpath(od, HERE))
    if _is_deliverable(od):
        return "跳过：该目录声明为交付稿（declaration.json deliverable）"
    return ""


def run_one(name, cfg, quiet=True):
    data = cfg.get("data")
    dp = os.path.join(DATA, data) if data else None
    if data and not os.path.exists(dp):
        return False, "数据缺失 %s" % data, 0.0
    tex = os.path.join(HERE, cfg["out"], "paper.tex")
    why = _outside_template_root(os.path.dirname(tex))
    if why:
        # 第 123 轮（红队 deployment 板的 P0）：这里原来返回 False，
        # 于是「保护生效」与「编译失败」在统计里不可区分 —— 全量跑永远
        # exit 1、永远打不出 ALL GREEN，红灯从此不带信息。
        # 跳过是**预期行为**，必须与失败分开记。
        return "skip", why, 0.0
    os.makedirs(os.path.dirname(tex), exist_ok=True)
    cmd = [PY, "mmkit.py", "run",
           "--y", cfg["y"], "--x", cfg["x"], "--min", cfg["min"],
           "--tex", tex, "--team", "2612345",
           "--problem", cfg["problem"], "--compile", "--no-gate"]
    if dp:
        cmd[3:3] = ["--data", dp]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=HERE)
    dt = time.time() - t0
    pdf = os.path.join(os.path.dirname(tex), "paper.pdf")
    if not os.path.exists(pdf):
        tail = (r.stdout or "").strip().splitlines()[-3:]
        return False, "没有 PDF | " + " / ".join(tail), dt
    return True, "", dt


def gate_one(cfg):
    d = os.path.join(HERE, cfg["out"])
    r = subprocess.run([PY, "gate.py", d], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=HERE)
    out = r.stdout or ""
    line = [x.strip() for x in out.splitlines() if "质量门" in x]
    warn = [x.strip() for x in out.splitlines() if "[WARN]" in x and "项" in x]
    fail = [x.strip() for x in out.splitlines() if "[FAIL]" in x]
    return (line[0] if line else "?"), (warn[0] if warn else ""), fail


def main():
    want = sys.argv[1:]
    cfg = load()
    names = [n for n in cfg if not want or n in want]
    print("=" * 78)
    print("最后会战：%d 道题" % len(names))
    print("=" * 78)
    rows = []
    skipped = []
    for i, n in enumerate(names, 1):
        ok, why, dt = run_one(n, cfg[n])
        if ok == "skip":
            skipped.append((n, why))
            print("  [%d/%d] %-16s %-5s %5.1fs"
                  % (i, len(names), n, "SKIP", dt))
            print("        %s" % why[:110])
            continue
        g, warn, fail = gate_one(cfg[n]) if ok else ("-", "", [])
        good = ok and g.startswith("质量门：通过")
        rows.append((n, ok, g, warn, fail, dt, why))
        print("  [%d/%d] %-16s %-5s %5.1fs  %s"
              % (i, len(names), n, "OK" if good else "FAIL", dt, g[:26]))
        if why:
            print("        %s" % why[:100])
        for f in fail[:2]:
            print("        %s" % f[:100])
    print()
    okn = sum(1 for r in rows if r[1] and r[2].startswith("质量门：通过"))
    print("=" * 78)
    tail = ("（另跳过 %d 道，不计入分母）" % len(skipped)) if skipped else ""
    print("  %d/%d 通过%s" % (okn, len(rows), tail))
    bad = [r for r in rows
           if not (r[1] and r[2].startswith("质量门：通过"))]
    if skipped:
        print("  跳过（保护：只写 out/runs/ 下）：")
        for n, why in skipped:
            print("    %-16s %s" % (n, why[:80]))
    if bad:
        print("  未通过：")
        for n, ok, g, warn, fail, dt, why in bad:
            print("    %-16s %s %s" % (n, g[:30], (why or "")[:60]))
    print("  ALL GREEN" if not bad else "  有 %d 项未通过" % len(bad))
    print("=" * 78)
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
