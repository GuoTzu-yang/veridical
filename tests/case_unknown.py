#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证「没查成 ≠ 做不了」：unknown 输入不否决，而且确实不该否决

第二十三/二十四轮把前置检查做成了三态，但账本里从没出现过 input_valid=None 的判定。
**新状态没被使用过，就等于没验证过。**

这一轮造一个真实场景：
  1. 把 sql 检查器的 distro 指到不存在的地方 → 检查结果 unknown
  2. 用这个结果作为 input_valid=None 去评估
  3. 恢复 distro，**真把任务跑一遍**
  4. 看「不否决」这个决定对不对

如果真跑成了，说明当时若判 False 就会误杀一个能成的任务——那才是真的错。

跑法：
  python case_unknown.py --dry-run
  python case_unknown.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 架构本体所在目录
sys.path.insert(0, ROOT)

from harness import Claim, run_gates, detect_env, derive_e3, e3_reason  # noqa: E402
import ledger as L  # noqa: E402
import precheck as P  # noqa: E402
import sqlcheck  # noqa: E402

DISTRO = "Ubuntu-22.04"
TMP_WSL = "/mnt/c/Users/21246/AppData/Local/Temp"

SQL = "SELECT COUNT(*) FROM bench_l3.t_ann WHERE age > 50"


def wsl(script: str, timeout: int = 300) -> tuple[int, str]:
    tmp = os.path.join(tempfile.gettempdir(), "unk_run.sh")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(script)
    env = dict(os.environ)
    env["WSL_UTF8"] = "1"
    r = subprocess.run(["wsl.exe", "-d", DISTRO, "--", "bash", TMP_WSL + "/unk_run.sh"],
                       capture_output=True, timeout=timeout, env=env)
    out = (r.stdout or b"").decode("utf-8", "replace") + (r.stderr or b"").decode("utf-8", "replace")
    return r.returncode, out


def main() -> int:
    L.bind_production("案例脚本：unknown 不否决")  # 本脚本产出真实证据   # 只有真跑这个脚本才绑定，导入不绑
    dry = "--dry-run" in sys.argv
    env, why = detect_env(ROOT, None, True,
                          wsl_distro=DISTRO, wsl_executable="/usr/bin/observer")

    print("=" * 76)
    print("unknown 输入不否决 · 完整链路验证")
    if dry:
        print("【dry-run】不写账本")
    print("=" * 76)
    print(f"环境: L{env.level}")
    print(f"任务: {SQL}")

    # ---- 1. 制造 unknown ----
    print("\n【1】让检查器不可用（把 distro 指向不存在的名字）")
    saved_tg = sqlcheck.DISTRO
    sqlcheck.DISTRO = "NoSuchDistro-XYZ"
    try:
        r = P.check_task("sql", {"sql": SQL})
    finally:
        sqlcheck.DISTRO = saved_tg
    print(f"    状态 = {r.status}")
    print(f"    理由 = {r.reason[:60]}")
    print(f"    → input_valid = {r.ok}")

    # ---- 2. 用 unknown 评估 ----
    src = "measured"
    c = Claim("U1", "查 age>50 的行数",
              e1=2, e2=0, e3=derive_e3(src),
              kind="procedure", input_valid=r.ok)
    g = run_gates(c, env)
    print(f"\n【2】评估（e1=2 e3={c.e3} 来源={src}，input_valid={r.ok}）")
    for x in g["ledger"]:
        print(f"    {x['gate']} 值={x['value']} 线={x['pass_at']} → {x['verdict']}")
    print(f"    最终: {g['final']}" + (f"（成因={g['cause']}）" if g.get("cause") else ""))
    print(f"    {'✓ 没有因为「没查成」就否决' if g['final'] != 'reject' else '✗ 被否决了'}")

    # ---- 3. 真跑 ----
    print("\n【3】恢复环境，真执行")
    code, out = wsl(
        "set -u\n"
        "systemctl start seekdb >/dev/null 2>&1\n"
        "for i in $(seq 1 40); do\n"
        "  mysql -h127.0.0.1 -P2881 -uroot@sys --connect-timeout=2 -e 'select 1' >/dev/null 2>&1 && break\n"
        "  sleep 1\n"
        "done\n"
        f"mysql -h127.0.0.1 -P2881 -uroot@sys -N -B -e \"{SQL}\" 2>&1 | head -3\n"
    )
    got = [l.strip() for l in out.splitlines() if l.strip().isdigit()]
    ok = code == 0 and bool(got)
    print(f"    执行结果: {got[0] + ' 行' if got else '（无输出）'}  退出码 {code}")

    # ---- 4. 记账 ----
    rec_id = None
    if not dry:
        rec = L.record(
            g["final"],
            task="unknown·U1 检查器不可用时的查询",
            note=f"input_valid=None（前置检查 {r.status}）→ 不否决 → 实际{'成功' if ok else '失败'}",
            success=ok,
            evidence=f"{r.reason[:50]} | 实际返回 {got[0] if got else 'N/A'} 行",
            env_level=env.level,
            cause=g.get("cause"),
            origin="case")
        rec_id = rec["id"]

    # ---- 5. 结论 ----
    print("\n【4】这个「不否决」的决定对不对")
    if g["final"] == "reject":
        verdict = "无法评估（已否决）"
    elif ok:
        verdict = "✓ 对——真跑成了。当时若判 input_valid=False，就误杀了一个能成的任务"
    else:
        verdict = "· 不算错——真没跑成，但不否决也没有增加风险（结果仍是失败）"
    print(f"    {verdict}")

    if not dry:
        print(f"\n    记入 {rec_id}  success={ok}")
        s = L.stats(env.level)
        print(f"\nL{env.level}：{s['total']} 条")
        for v in ("pass", "degrade", "reject"):
            cc = s["calibration"].get(v)
            if cc:
                print(f"  {v:8s} n={cc['n']:<3} succ={cc['success']:<3} Laplace={cc['laplace']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
