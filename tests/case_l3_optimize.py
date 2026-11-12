#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真 degrade 样本：任务做成了，但「算不算达成」说不清

上一轮补的 D1-D5 全是「验证条件不具备」——和 reject 没区别，都做不成。
修正语义后两桶都是 0/5，说明 degrade 这一档根本没被真正测到。

真正落进 degrade 的是这类：**需求本身模糊**。
  e1=1：知道该往哪优化，但没定位到具体改法
  e3=1：能测出数，但「快多少算优化」没有标准

  → e1+e3 = 2 → degrade

所以这一轮真做一个优化任务：加索引前后各测 15 次，
变快了记 success=True，没变快记 False —— 让数据自己说话。

跑法：
  python case_l3_optimize.py --dry-run
  python case_l3_optimize.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 架构本体所在目录
sys.path.insert(0, ROOT)

from harness import Claim, run_gates, detect_env  # noqa: E402
import ledger as L  # noqa: E402

DISTRO = "Ubuntu-22.04"
TMP_WSL = "/mnt/c/Users/21246/AppData/Local/Temp"
REPEAT = 15


def wsl(script: str, timeout: int = 400) -> tuple[int, str]:
    tmp = os.path.join(tempfile.gettempdir(), "opt_run.sh")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(script)
    env = dict(os.environ)
    env["WSL_UTF8"] = "1"
    r = subprocess.run(["wsl.exe", "-d", DISTRO, "--", "bash", TMP_WSL + "/opt_run.sh"],
                       capture_output=True, timeout=timeout, env=env)
    out = (r.stdout or b"").decode("utf-8", "replace") + (r.stderr or b"").decode("utf-8", "replace")
    return r.returncode, out


def main() -> int:
    L.bind_production("案例脚本：真做一次优化")  # 本脚本产出真实证据   # 只有真跑这个脚本才绑定，导入不绑
    dry = "--dry-run" in sys.argv
    env, why = detect_env(ROOT, None, True,
                          wsl_distro=DISTRO, wsl_executable="/usr/bin/observer")

    print("=" * 76)
    print("真 degrade：优化做成了，但「算不算达成」说不清")
    if dry:
        print("【dry-run】不写账本")
    print("=" * 76)
    print(f"环境: L{env.level}")

    # ---- 评估（先判）----
    # e1=1：知道该在 age 上想办法，但「最优改法」没有权威定义
    # e3=1：能测耗时，但单次波动大，"快多少算优化"没标准
    c = Claim("O1", "给 age 加索引让查询变快",
              e1=1, e2=0, e3=1, kind="procedure")
    r = run_gates(c, env)
    print(f"\n【1】先判  e1=1 e3=1 → C={r['C']} → {r['final']}")
    for g in r["ledger"]:
        print(f"    {g['gate']} value={g['value']} 线={g['pass_at']} → {g['verdict']}")

    # ---- 执行（真测）----
    print(f"\n【2】真跑：加索引前后各测 {REPEAT} 次，取中位数")
    script = f"""
set -u
systemctl start seekdb >/dev/null 2>&1
for i in $(seq 1 40); do
  mysql -h127.0.0.1 -P2881 -uroot@sys --connect-timeout=2 -e 'select 1' >/dev/null 2>&1 && break
  sleep 1
done
M="mysql -h127.0.0.1 -P2881 -uroot@sys -N -B bench_l3"
mysql -h127.0.0.1 -P2881 -uroot@sys -e "DROP INDEX IF EXISTS idx_age ON bench_l3.t_ann" 2>/dev/null

bench() {{
  local n=$1
  local times=""
  for i in $(seq 1 $n); do
    local s=$(date +%s%N)
    $M -e "SELECT COUNT(*) FROM t_ann WHERE age > 50" >/dev/null 2>&1
    local e=$(date +%s%N)
    times="$times $(( (e-s)/1000000 ))"
  done
  echo $times
}}

BEFORE=$(bench {REPEAT})
mysql -h127.0.0.1 -P2881 -uroot@sys -e "CREATE INDEX idx_age ON bench_l3.t_ann(age)" 2>/dev/null
AFTER=$(bench {REPEAT})
echo "BEFORE=$BEFORE"
echo "AFTER=$AFTER"
"""
    code, out = wsl(script, timeout=400)

    before, after = [], []
    for line in out.splitlines():
        if line.startswith("BEFORE="):
            before = [int(x) for x in line[7:].split() if x.isdigit()]
        elif line.startswith("AFTER="):
            after = [int(x) for x in line[6:].split() if x.isdigit()]

    def med(xs):
        if not xs:
            return None
        s = sorted(xs)
        return s[len(s) // 2]

    mb, ma = med(before), med(after)
    print(f"    索引前中位数: {mb} ms  (n={len(before)})")
    print(f"    索引后中位数: {ma} ms  (n={len(after)})")

    if mb is None or ma is None:
        print("\n  没测到数据，任务未完成")
        faster = False
        detail = "测量失败"
    else:
        faster = ma < mb
        delta = (mb - ma) / mb * 100 if mb else 0
        detail = f"{mb}ms → {ma}ms（{delta:+.0f}%）"
        print(f"    变快: {'是' if faster else '否'}  {detail}")

    # ---- 记账 ----
    print(f"\n【3】记账：判 {r['final']}，任务{'做成了' if faster else '没做成'}")
    if not dry:
        rec = L.record(r["final"], task="优化·O1 加索引让查询变快",
                       note="需求模糊（快多少算优化无标准），但任务真实执行",
                       success=faster,
                       evidence=detail,
                       env_level=env.level,
                       cause=r.get("cause"), origin="case")
        print(f"    记入 {rec['id']}  success={faster}")
    else:
        print("    (dry-run 跳过)")

    if not dry:
        s = L.stats(env.level)
        print(f"\nL{env.level} 现状：{s['total']} 条")
        for v in ("pass", "degrade", "reject"):
            cc = s["calibration"].get(v)
            if cc:
                print(f"  {v:8s} n={cc['n']:<3} succ={cc['success']:<3} "
                      f"Laplace={cc['laplace']}  Wilson[{cc['wilson_lo']}, {cc['wilson_hi']}]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
