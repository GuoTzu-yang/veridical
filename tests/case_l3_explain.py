#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用 EXPLAIN 的确定性指标验证优化，替代不可靠的墙钟计时

上一轮的教训：11ms→9ms 和 10ms→10ms，两次跑出相反结论。墙钟时间在
10ms 量级上被噪声吃掉了。

这一轮换成优化器自己的估算：
  OPERATOR   FULL SCAN → RANGE SCAN     （二元，确定）
  EST.TIME   215us → 66us               （估算，非实测）

任务判 degrade 而不是 pass，理由是真的：
  e1=1  「优化这条查询」没指定方向（加索引／改写／分区都能优化）
  e3=1  EST.TIME 是优化器估算，不等于实际耗时

跑法：
  python case_l3_explain.py --dry-run
  python case_l3_explain.py
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

from harness import Claim, run_gates, detect_env, derive_e3, e3_reason  # noqa: E402
import ledger as L  # noqa: E402

DISTRO = "Ubuntu-22.04"
TMP_WSL = "/mnt/c/Users/21246/AppData/Local/Temp"


def wsl(script: str, timeout: int = 300) -> tuple[int, str]:
    tmp = os.path.join(tempfile.gettempdir(), "explain_run.sh")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(script)
    env = dict(os.environ)
    env["WSL_UTF8"] = "1"
    r = subprocess.run(["wsl.exe", "-d", DISTRO, "--", "bash", TMP_WSL + "/explain_run.sh"],
                       capture_output=True, timeout=timeout, env=env)
    out = (r.stdout or b"").decode("utf-8", "replace") + (r.stderr or b"").decode("utf-8", "replace")
    return r.returncode, out


def parse_plan(text: str) -> dict:
    """从 EXPLAIN 输出里抠出根算子的 OPERATOR 和 EST.TIME。"""
    op, est_time, est_rows = None, None, None
    for line in text.splitlines():
        if "|" in line and ("SCAN" in line or "GROUP" in line):
            parts = [p.strip() for p in line.strip("|").split("|")]
            # 形如 ['1', '└─TABLE RANGE SCAN', 't_ann(idx_age)', '2450', '66']
            if len(parts) >= 5 and parts[0].isdigit():
                op = re.sub(r"[└─]+", "", parts[1]).strip()
                try:
                    est_rows = int(parts[3])
                    est_time = int(parts[4])
                except (ValueError, IndexError):
                    pass
                if "SCAN" in op:
                    break
    return {"operator": op, "est_rows": est_rows, "est_time": est_time}


def main() -> int:
    L.bind_production("案例脚本：确定性指标验证")  # 本脚本产出真实证据   # 只有真跑这个脚本才绑定，导入不绑
    dry = "--dry-run" in sys.argv
    env, why = detect_env(ROOT, None, True,
                          wsl_distro=DISTRO, wsl_executable="/usr/bin/observer")

    print("=" * 74)
    print("确定性指标验证优化 · EXPLAIN 的 OPERATOR / EST.TIME")
    if dry:
        print("【dry-run】不写账本")
    print("=" * 74)
    print(f"环境: L{env.level}")

    # ---- 先判 ----
    # e3 按证据来源推导：事前不知道会走哪个计划，取最不可信的那档
    src = "fullscan_est"
    c = Claim("E1", "优化 age > 50 的查询",
              e1=1,                    # 「优化」方向不唯一
              e2=0,
              e3=derive_e3(src),       # 全表扫描估算，偏差 80-96%
              kind="procedure")
    r = run_gates(c, env)
    print(f"\n【1】先判  e1=1 e3={c.e3}（来源={src}：{e3_reason(src)}）"
          f" → C={r['C']} → {r['final']}")
    for g in r["ledger"]:
        print(f"    {g['gate']} value={g['value']} 线={g['pass_at']} → {g['verdict']}")

    # ---- 执行 ----
    print("\n【2】EXPLAIN 前后对比（不是计时）")
    script = """
set -u
systemctl start seekdb >/dev/null 2>&1
for i in $(seq 1 40); do
  mysql -h127.0.0.1 -P2881 -uroot@sys --connect-timeout=2 -e 'select 1' >/dev/null 2>&1 && break
  sleep 1
done
M="mysql -h127.0.0.1 -P2881 -uroot@sys bench_l3"
mysql -h127.0.0.1 -P2881 -uroot@sys -e "ALTER TABLE bench_l3.t_ann DROP INDEX idx_age" 2>/dev/null
echo "===NOIDX==="
$M -e "EXPLAIN SELECT COUNT(*) FROM t_ann WHERE age > 50"
mysql -h127.0.0.1 -P2881 -uroot@sys -e "CREATE INDEX idx_age ON bench_l3.t_ann(age)" 2>/dev/null
echo "===WITHIDX==="
$M -e "EXPLAIN SELECT COUNT(*) FROM t_ann WHERE age > 50"
"""
    code, out = wsl(script, timeout=300)

    part_no = out.split("===NOIDX===")[-1].split("===WITHIDX===")[0] if "===NOIDX===" in out else ""
    part_yes = out.split("===WITHIDX===")[-1] if "===WITHIDX===" in out else ""
    plan_no = parse_plan(part_no)
    plan_yes = parse_plan(part_yes)

    print(f"    无索引: {plan_no['operator']:<20} EST.TIME={plan_no['est_time']}us")
    print(f"    有索引: {plan_yes['operator']:<20} EST.TIME={plan_yes['est_time']}us")

    # ---- 判定 ----
    ok = False
    detail = "未取到计划"
    if plan_no["est_time"] and plan_yes["est_time"]:
        faster = plan_yes["est_time"] < plan_no["est_time"]
        switched = ("FULL" in (plan_no["operator"] or "")) and ("RANGE" in (plan_yes["operator"] or ""))
        # 只认算子切换这个确定事实；EST.TIME 的倍数不可信——
        # case_l3_estacc.py 实测：全表扫描时 EST.ROWS 偏差 80-96%
        ok = switched
        ratio = plan_no["est_time"] / plan_yes["est_time"] if plan_yes["est_time"] else 0
        detail = (f"{plan_no['operator']}→{plan_yes['operator']}"
                  f"（EST.TIME {plan_no['est_time']}→{plan_yes['est_time']}us，"
                  f"倍数 {ratio:.1f}× 仅供参考）")
        print(f"\n    算子切换: {'是' if switched else '否'}  ← 这是确定事实")
        print(f"    EST.TIME 变化: {ratio:.1f}×  ← 估算值，全表扫描段偏差可达 80-96%，不作判据")

    # ---- 记账 ----
    print(f"\n【3】记账：判 {r['final']}，优化{'生效' if ok else '未生效'}")
    if not dry:
        rec = L.record(r["final"], task="优化·E1 EXPLAIN 指标验证",
                       note="需求方向不唯一 + 指标为估算",
                       success=ok, evidence=detail, env_level=env.level,
                       cause=r.get("cause"), origin="case")
        print(f"    记入 {rec['id']}  success={ok}")
    else:
        print("    (dry-run 跳过)")

    if not dry:
        s = L.stats(env.level)
        print(f"\nL{env.level}：{s['total']} 条")
        for v in ("pass", "degrade", "reject"):
            cc = s["calibration"].get(v)
            if cc:
                print(f"  {v:8s} n={cc['n']:<3} succ={cc['success']:<3} "
                      f"Laplace={cc['laplace']}  Wilson[{cc['wilson_lo']}, {cc['wilson_hi']}]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
