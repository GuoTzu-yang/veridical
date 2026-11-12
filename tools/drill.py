"""比赛流程演练：按顺序跑一遍关键命令并计时。

为什么需要它
------------
比赛是 96 小时（2026 年 APMCM 英文赛项：11/26 06:00 - 11/30 09:00）。
「流程能跑通」和「流程来得及」是两件事 —— 后者只能用计时回答。

用法
    python tools/drill.py --name mcm2020c          # 计时一遍（只读命令）
    python tools/drill.py --name mcm2020c --race   # 额外跑模型赛马（会落盘）
    python tools/drill.py --list                  # 列出可演练的题

安全性
------
默认只跑**不写产物**的命令（profile / advise / gate / verify）。
--race 会重跑模型赛马并可能覆盖 out/runs/<题>，所以单独开关，且先备份产物目录。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable


def sh(args, cwd=HERE, timeout=1800):
    t0 = time.time()
    p = subprocess.run([PY] + args, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return time.time() - t0, p.returncode, (p.stdout or "") + (p.stderr or "")


def main(argv=None):
    ap = argparse.ArgumentParser(description="比赛流程演练（计时）")
    ap.add_argument("--name", default="")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--race", action="store_true",
                    help="额外跑模型赛马（会落盘，先备份）")
    ap.add_argument("--full", action="store_true",
                    help="跑完整出稿链路：mmkit run + 编译 + 验收（写 out/drill/<题>）")
    a = ap.parse_args(argv)

    cfg = json.load(open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
    if a.list:
        for k, c in cfg.items():
            d = os.path.join(HERE, c["out"])
            ok = os.path.isdir(d)
            print("%-18s data=%-22s out=%-28s %s"
                  % (k, c.get("data", ""), c.get("out", ""),
                     "产物在" if ok else "无产物"))
        return 0
    if not a.name:
        ap.error("需要 --name 或 --list")
    if a.name not in cfg:
        print("没有这道题：%s" % a.name)
        return 2

    c = cfg[a.name]
    data = os.path.join(HERE, "out", "data", c.get("data", ""))
    outdir = os.path.join(HERE, c["out"])
    y = c.get("y") or ""
    x = c.get("x") or ""

    steps = []
    print("=== 演练：%s ===" % a.name)
    print("数据 %s" % data)
    print("产物 %s\n" % outdir)

    def run(label, args, **kw):
        dt, rc, out = sh(args, **kw)
        steps.append((label, dt, rc))
        head = [x for x in out.splitlines() if x.strip()][:1]
        print("  %-12s %7.1fs  rc=%d  %s" % (label, dt, rc,
                                           (head[0][:60] if head else "")))
        return dt, rc, out

    # 1) 数据体检
    run("profile", ["mmkit.py", "profile", "--data", data, "--json"])
    # 2) 定题
    if y and x:
        run("advise", ["mmkit.py", "advise", "--data", data, "--y", y,
                       "--x", x, "--json"])
    # 3) 全链路出稿（--full）：建目录 -> mmkit run -> 编译 -> 验收
    if a.full:
        drill_dir = os.path.join(HERE, "out", "drill", a.name)
        if os.path.isdir(drill_dir):
            shutil.rmtree(drill_dir)
        os.makedirs(drill_dir, exist_ok=True)
        # 注意：--out 是**报告文件路径**，--tex 是 paper.tex 路径，
        # 两者都不是目录。传目录会得到 Permission denied。
        cmd = ["mmkit.py", "run", "--data", data, "--y", y, "--x", x,
               "--out", os.path.join(drill_dir, "report.md"),
               "--tex", os.path.join(drill_dir, "paper.tex"), "--compile"]
        if c.get("min"):
            cmd += ["--min", c["min"]]
        if c.get("problem"):
            cmd += ["--problem", c["problem"]]
        run("run+compile", cmd)
        pdf = os.path.join(drill_dir, "paper.pdf")
        if os.path.exists(pdf):
            print("      产出 PDF %.0f KB" % (os.path.getsize(pdf) / 1024.0))
        run("gate", ["gate.py", drill_dir, "--data", data])
    # 4) 验收既有产物
    if os.path.isdir(outdir):
        run("gate", ["gate.py", outdir])
        tex = os.path.join(outdir, "paper.tex")
        if os.path.exists(tex):
            run("verify", ["verify.py", tex, "--out-dir", outdir])
    else:
        print("  （无产物目录，跳过 gate / verify）")

    total = sum(d for _, d, _ in steps)
    print("\n=== 汇总 ===")
    for label, dt, rc in steps:
        print("  %-12s %7.1fs  rc=%d" % (label, dt, rc))
    print("  %-12s %7.1fs  (%.2f h)" % ("总计", total, total / 3600.0))
    print("\n参考：APMCM 英文赛项 2026-11-26 06:00 → 11-30 09:00 = 99 小时")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
