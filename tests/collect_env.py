#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
补 degrade/env 样本：判定用 L2，执行用真实能力

`degrade` 有两种成因，第十九轮拆开了：

    env   本可 pass，被环境规则降级     ← v2 里一条都没有
    info  证据不足，闸门自己判的降级

`env` 只在 L2 环境下产生（L3 不受环境限制）。而 L2 的定义就是"有源码、
能上网，但没有可执行实例"——所以这条路在 L3 下永远走不到。

要补它，只能**故意把判定环境降到 L2，执行却用真实能力**：
这正是"当时证据不够、后来环境好了"的场景，也就是 degrade/env 的本义。

跑法：
  python collect_env.py --dry-run
  python collect_env.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # 架构本体所在目录
sys.path.insert(0, ROOT)

from harness import Claim, run_gates, EvidenceEnv, derive_e3, MODEL_VERSION  # noqa: E402
import ledger as L  # noqa: E402
from sqlcheck import precheck as sql_precheck, _tables  # noqa: E402

DISTRO = "Ubuntu-22.04"
TMP_WSL = "/mnt/c/Users/21246/AppData/Local/Temp"

# 全部 e1=2 / e3=2：在 L3 下都会 pass，在 L2 下会被降级成 degrade(env)
TASKS = [
    ("G1", "查 t_ann 行数",     "SELECT COUNT(*) FROM bench_l3.t_ann"),
    ("G2", "查 age>50 行数",    "SELECT COUNT(*) FROM bench_l3.t_ann WHERE age > 50"),
    ("G3", "查最小 age",        "SELECT MIN(age) FROM bench_l3.t_ann"),
    ("G4", "按 category 分组",  "SELECT category5, COUNT(*) FROM bench_l3.t_ann GROUP BY category5"),
    ("G5", "建临时表 t_g",      "CREATE TABLE IF NOT EXISTS bench_l3.t_g(a INT)"),
    ("G6", "往 t_g 插 3 行",    "INSERT INTO bench_l3.t_g VALUES (1),(2),(3)"),
    ("G7", "查 t_g",           "SELECT COUNT(*) FROM bench_l3.t_g"),
    ("G8", "删 t_g",           "DROP TABLE IF EXISTS bench_l3.t_g"),
    ("G9", "向量距离排序",       "SELECT id FROM bench_l3.t_ann ORDER BY l2_distance(v,'[0,0,0,0]') LIMIT 3"),
    ("G10", "按 age 排序取前 5",  "SELECT id FROM bench_l3.t_ann ORDER BY age DESC LIMIT 5"),
]


def wsl(script: str, timeout: int = 400) -> tuple[int, str]:
    tmp = os.path.join(tempfile.gettempdir(), "env_run.sh")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(script)
    env = dict(os.environ)
    env["WSL_UTF8"] = "1"
    r = subprocess.run(["wsl.exe", "-d", DISTRO, "--", "bash", TMP_WSL + "/env_run.sh"],
                       capture_output=True, timeout=timeout, env=env)
    out = (r.stdout or b"").decode("utf-8", "replace") + (r.stderr or b"").decode("utf-8", "replace")
    return r.returncode, out


def main() -> int:
    L.bind_production("采集脚本：L2 降级对照")  # 本脚本产出真实证据   # 只有真跑这个脚本才绑定，导入不绑
    dry = "--dry-run" in sys.argv
    env2 = EvidenceEnv(2)   # 判定用 L2
    env3 = EvidenceEnv(3)   # 对照：同一批在 L3 下会怎样

    print("=" * 82)
    print("补 degrade/env 样本 · 判定 L2，执行真实")
    if dry:
        print("【dry-run】不执行，不写账本")
    print("=" * 82)
    print(f"判定环境: L{env2.level}（该环境下降级成因必为 env）")

    # ---- 判定 ----
    print(f"\n  {'ID':<5}{'任务':<22}{'L3 下':>9}{'L2 下':>10}{'成因':>8}")
    print("  " + "-" * 58)
    rows = []
    for tid, name, sql in TASKS:
        c = Claim(tid, name, e1=2, e2=0, e3=derive_e3("measured"), kind="procedure")
        g3 = run_gates(c, env3)
        g2 = run_gates(c, env2)
        print(f"  {tid:<5}{name:<22}{g3['final']:>9}{g2['final']:>10}"
              f"{(g2.get('cause') or '-'):>8}")
        rows.append({"tid": tid, "name": name, "sql": sql, "g": g2, "g3": g3})

    # ---- 执行 ----
    actual: dict[str, bool] = {}
    if dry:
        print("\n（dry-run：不执行）")
    else:
        script = ["set -u",
                  "systemctl start seekdb >/dev/null 2>&1",
                  "for i in $(seq 1 40); do",
                  "  mysql -h127.0.0.1 -P2881 -uroot@sys --connect-timeout=2 -e 'select 1' >/dev/null 2>&1 && break",
                  "  sleep 1",
                  "done",
                  "mysql -h127.0.0.1 -P2881 -uroot@sys -e 'DROP TABLE IF EXISTS bench_l3.t_g' 2>/dev/null"]
        for tid, name, sql in TASKS:
            q = sql.replace("'", "'\\''")
            script.append(f"if mysql -h127.0.0.1 -P2881 -uroot@sys -e '{q}' >/dev/null 2>&1; then")
            script.append(f"  echo \"R {tid}=ok\"")
            script.append("else")
            script.append(f"  echo \"R {tid}=fail\"")
            script.append("fi")
        code, out = wsl("\n".join(script), timeout=400)
        for line in out.splitlines():
            if line.startswith("R "):
                k, _, v = line[2:].partition("=")
                actual[k.strip()] = (v.strip() == "ok")

    # ---- 记账 ----
    print(f"\n  {'ID':<5}{'任务':<22}{'判定':>10}{'成因':>8}{'实际':>7}{'一致':>5}")
    print("  " + "-" * 58)
    hit = scored = 0
    for r in rows:
        act = actual.get(r["tid"])
        predicted_ok = r["g"]["final"] in ("pass", "degrade")
        consistent = (predicted_ok == act) if act is not None else None
        hit += 1 if consistent else 0
        scored += 1 if act is not None else 0
        print(f"  {r['tid']:<5}{r['name']:<22}{r['g']['final']:>10}"
              f"{(r['g'].get('cause') or '-'):>8}"
              f"{('成' if act else '败' if act is False else '-') if act is not None else '-':>7}"
              f"{('✓' if consistent else '✗' if consistent is False else '?') if act is not None else ' ':>5}")
        if not dry and act is not None:
            L.record(r["g"]["final"], task=f"env收集·{r['tid']} {r['name']}",
                     note="判定用 L2，执行用真实能力（补 degrade/env）",
                     # ⚠ 这里的 success 是**反事实**的：判定按 L2 限制，执行却用 L3 权限。
                     # 所以「成功」的意思是「如果能验，这任务会不会成」，
                     # 不是「在当前环境里成不成」。
                     #
                     # 第五十五轮发现：这跟 case_l3_limits 里的 degrade/env
                     # （环境真给不了，0/5 全败）是两个不同的问题，
                     # 却共用了同一个 cause 标签。看这一档的数字前先想清楚问的是哪个。
                     success=act,
                     exec_ok=act,
                     # 反事实样本：这个 success 说的是「如果能验会不会成」
                     counterfactual=True,
                     evidence=f"L3 下会判 {r['g3']['final']}，L2 下降级为 {r['g']['final']}",
                     env_level=2,
                     cause=r["g"].get("cause"),
                     origin="collect",
                     replay=(None if any(x in (r["sql"] or "").lower()
                                          for x in ("t_c1", "t_g"))
                             else {"domain": "sql", "task": {"sql": r["sql"]}}))

    print()
    print("=" * 82)
    print(f"命中率: {hit}/{scored}" + (f" = {hit/scored*100:.0f}%" if scored else ""))
    print("=" * 82)

    if not dry:
        s = L.stats(2, MODEL_VERSION)
        print(f"\nL2 v{MODEL_VERSION}：{s['total']} 条   成因分布 {s.get('by_cause') or {}}")
        for k, c in sorted(s["calibration_by_cause"].items()):
            print(f"  {k:16s} n={c['n']:<3} succ={c['success']:<3} "
                  f"Laplace={c['laplace']}  Wilson[{c['wilson_lo']}, {c['wilson_hi']}]")
        prior, det = L.current_prior(env_level=2)
        print("\nL2 先验：")
        for k in sorted(prior):
            d = det.get(k, {})
            print(f"  {k:14s} {prior[k]:.3f}  source={d.get('source','base')}  n={d.get('n','-')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
