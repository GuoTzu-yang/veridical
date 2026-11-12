#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨领域样本：file / http 也要有自己的数据

前二十九轮所有样本都来自 SQL 领域。三态前置检查写了 file / http 两个实现，
但它们一条实际样本都没有——**实现了不等于验证过**。

这一批十四个任务全在 Windows 本机跑，不碰 WSL：

  file  读/写/列目录/建目录，成功 = 操作真的完成
  http  HEAD 请求，成功 = 拿到 < 400 的状态码

前置检查与执行是两件事：precheck 说"路径在不在 / 域名解析不解析得开"，
执行才是"真读一下 / 真发一次请求"。两者不一致的地方才是有信息量的地方。

跑法：
  python collect_io.py --dry-run
  python collect_io.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 架构本体所在目录
sys.path.insert(0, ROOT)

from harness import Claim, run_gates, detect_env, derive_e3  # noqa: E402
import ledger as L  # noqa: E402
import precheck as P
from probe import do_exec as _do_exec   # 共享执行器  # noqa: E402

TMP = os.path.join(tempfile.gettempdir(), "m1_io_probe")

# (id, 领域, 任务说明, 检查入参, 执行函数名, e1, e3_source, 期望判定)
TASKS = [
    # ---- file ----
    ("F1", "file", "读 harness.py",
     {"path": os.path.join(ROOT, "harness.py"), "op": "read"}, "read", 2, "measured", "pass"),
    ("F2", "file", "读不存在的文件",
     {"path": os.path.join(ROOT, "no_such_file.py"), "op": "read"}, "read", 2, "measured", "reject"),
    ("F3", "file", "列 model1-arch 目录",
     {"path": ROOT, "op": "dir"}, "listdir", 2, "measured", "pass"),
    ("F4", "file", "写一个临时文件",
     {"path": os.path.join(TMP, "w1.txt"), "op": "create"}, "write", 2, "measured", "pass"),
    ("F5", "file", "读系统 hosts",
     {"path": r"C:\Windows\System32\drivers\etc\hosts", "op": "read"}, "read", 2, "measured", "pass"),
    ("F6", "file", "在不存在的目录里建文件",
     {"path": r"C:\no_such_root_xyz\a.txt", "op": "create"}, "write", 2, "measured", "reject"),
    ("F7", "file", "把目录当文件读",
     {"path": ROOT, "op": "read"}, "read", 2, "measured", "reject"),

    # ---- http ----
    # 注意 H1/H6：本机到 github.com:443 是被拒的（WinError 10061），
    # 所以期望值是 reject 而不是 pass。第一次写的时候我以为"知名站点就该通"，
    # 实测推翻了这个假设——期望值也要服从证据。
    ("H1", "http", "访问 github.com", {"url": "https://github.com"}, "head", 2, "measured", "reject"),
    ("H2", "http", "访问 example.com", {"url": "https://example.com"}, "head", 2, "measured", "pass"),
    ("H3", "http", "访问不存在的域",
     {"url": "https://no-such-host-xyz-12345.invalid/"}, "head", 2, "measured", "reject"),
    ("H4", "http", "协议不支持", {"url": "ftp://example.com/x"}, "head", 2, "measured", "reject"),
    ("H5", "http", "URL 没有主机名", {"url": "not-a-url"}, "head", 2, "measured", "reject"),
    ("H6", "http", "访问 404 路径",
     {"url": "https://github.com/oceanbase/no-such-repo-xyz-999"}, "head", 2, "measured", "reject"),
]

# http 判 reject 时不该真发请求；判 pass 才试


def main() -> int:
    L.bind_production("采集脚本：真实 file/http 任务")  # 本脚本产出真实证据   # 只有真跑这个脚本才绑定，导入不绑
    dry = "--dry-run" in sys.argv
    # --env N：强制按某档判（执行照旧，用来造跨域的 degrade/env 样本）
    forced = None
    if "--env" in sys.argv:
        i = sys.argv.index("--env")
        if i + 1 < len(sys.argv) and sys.argv[i + 1].isdigit():
            forced = int(sys.argv[i + 1])
    env, why = detect_env(ROOT, None, True,
                          wsl_distro="Ubuntu-22.04",
                          wsl_executable="/usr/bin/observer")
    if forced is not None:
        from harness import EvidenceEnv as _EE
        env = _EE(forced)
        why = f"强制指定 L{forced}（实际探测是 L{env.level}）"

    print("=" * 88)
    print("跨领域样本 · file / http")
    if dry:
        print("【dry-run】不执行，不写账本")
    print("=" * 88)
    print(f"环境: L{env.level}   任务数: {len(TASKS)}")

    if not dry:
        shutil.rmtree(TMP, ignore_errors=True)
    # 脚手架目录在 dry-run 时也要建好——它属于测试准备，不是"执行任务"。
    # 不建的话 dry-run 会把 F4 判成"父目录不存在"，和正式跑结论不同。
    os.makedirs(TMP, exist_ok=True)

    print(f"\n  {'ID':<4}{'领域':<6}{'任务':<24}{'前置':>6}{'判定':>9}{'期望':>9}"
          f"{'实际':>7}{'一致':>5}  依据")
    print("  " + "-" * 88)

    rows = []
    for (tid, domain, name, probe, kind, e1, src, want) in TASKS:
        pr = P.check_task(domain, probe)
        c = Claim(tid, name, e1=e1, e2=0, e3=derive_e3(src), kind="procedure",
                  input_valid=pr.ok)
        g = run_gates(c, env)

        if dry:
            act, why_act = None, ""
        else:
            act, why_act = _do_exec(domain, probe)

        predicted_ok = g["final"] in ("pass", "degrade")
        consistent = (predicted_ok == act) if act is not None else None
        mark = "✓" if consistent else ("✗" if consistent is False else "?")

        print(f"  {tid:<4}{domain:<6}{name:<24}"
              f"{('✓' if pr.status=='ok' else '✗' if pr.status=='fail' else '?'):>6}"
              f"{g['final']:>9}{want:>9}"
              f"{('成' if act else '败' if act is False else '-') if act is not None else '-':>7}"
              f"{mark:>5}  {why_act[:34] or pr.reason[:34]}")

        rows.append({"tid": tid, "domain": domain, "name": name, "g": g,
                     "pre": pr, "act": act, "want": want, "rid": None,
                     "probe": probe})

    # ---- 记账 ----
    hit = scored = 0
    for r in rows:
        if r["act"] is None:
            continue
        scored += 1
        predicted_ok = r["g"]["final"] in ("pass", "degrade")
        hit += 1 if predicted_ok == r["act"] else 0
        if not dry:
            rec = L.record(r["g"]["final"], task=f"{r['domain']}收集·{r['tid']} {r['name']}",
                           note=f"领域={r['domain']} 前置={r['pre'].status}",
                           success=r["act"],
                           exec_ok=r["act"],
                           # --env N 强制低档判定、执行照旧 → success 是反事实的
                           counterfactual=(forced is not None),
                           evidence=r["pre"].reason[:60],
                           env_level=env.level,
                           cause=r["g"].get("cause"),
                           origin="collect",
                           replay={"domain": r["domain"],
                                   "task": ({**r["probe"], "op": "head"}
                                            if r["domain"] == "http" else r["probe"])})
            r["rid"] = rec["id"]

    print()
    print("=" * 88)
    print(f"事前预测命中率: {hit}/{scored}" + (f" = {hit/scored*100:.0f}%" if scored else ""))
    if not dry:
        print(f"记入 {len([r for r in rows if r['rid']])} 条")
    print("=" * 88)

    if not dry:
        from harness import MODEL_VERSION
        s = L.stats(env.level, MODEL_VERSION)
        print(f"\nL{env.level} v{MODEL_VERSION}：{s['total']} 条")
        for v in ("pass", "degrade", "reject"):
            c = s["calibration"].get(v)
            if c:
                print(f"  {v:8s} n={c['n']:<3} succ={c['success']:<3} "
                      f"Laplace={c['laplace']}  Wilson[{c['wilson_lo']}, {c['wilson_hi']}]")
        prior, det = L.current_prior(env_level=env.level)
        print("\n先验：")
        for k in sorted(prior):
            d = det.get(k, {})
            print(f"  {k:14s} {prior[k]:.3f}  source={d.get('source','base')}  n={d.get('n','-')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
