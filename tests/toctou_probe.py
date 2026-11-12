#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TOCTOU 实验：检查通过之后、执行之前，把世界改掉

为什么做这个（第六十四轮）：
    第六十三轮查出来：12 条 pass 样本里 11 条的依据是「前置检查通过」。
    也就是说 —— **pass 的可靠性是前置检查给的，不是执行给的。**

    那么 pass 什么时候会错？只有一种情况：
    **检查的时候世界是 A，执行的时候世界变成了 B。**

    这叫 TOCTOU（Time-Of-Check to Time-Of-Use）。堆更多正常样本测不出它，
    必须**故意在检查和执行之间改动世界**。

怎么算结论：
    「判 pass + 执行失败」= 一次 TOCTOU 暴露。
    但它**不一定是判据的错** —— 判据说的是"我查的时候可以做"，
    世界在之后变了，那是世界的问题。
    所以这份报告只量化**暴露窗口有多大**，不往 pass 精确率里算。

跑法：python tests/toctou_probe.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import precheck as P                                    # noqa: E402
from harness import Claim, run_gates, EvidenceEnv       # noqa: E402
from probe import do_exec                               # noqa: E402


def judge(task: dict) -> dict:
    """走真实链路：前置检查 → 判定。"""
    pr = P.check_task("file", task)
    c = Claim("T", "任务", e1=2, e2=0, e3=2, kind="procedure",
              verify={"domain": "file", "task": task},
              input_valid=pr.ok)
    g = run_gates(c, EvidenceEnv(3))
    return {"pre": pr, "gate": g}


def run_case(name: str, setup, tamper, task_fn, cleanup=None):
    """一套：造世界 → 检查+判定 → 改世界 → 执行。"""
    d = tempfile.mkdtemp(prefix="toctou_")
    try:
        setup(d)
        task = task_fn(d)

        g = judge(task)                      # ← 检查与判定

        tampered, tamper_ev = tamper(d)      # ← 在两者之间改世界

        ok, why = do_exec("file", task)      # ← 执行

        return {
            "name": name,
            "pre": g["pre"].status,
            "verdict": g["gate"]["final"],
            "cause": g["gate"].get("cause"),
            "tampered": tampered,
            "tamper_ev": tamper_ev,
            "exec_ok": ok,
            "exec_why": why,
            # 判 pass 但执行失败 —— 这就是被世界改动打中的那一次
            "hit": (g["gate"]["final"] == "pass") and (ok is False),
        }
    finally:
        if cleanup:
            try:
                cleanup(d)
            except Exception:  # noqa: BLE001
                pass
        shutil.rmtree(d, ignore_errors=True)


def main() -> int:
    print("=" * 96)
    print("TOCTOU 实验 · 检查通过之后、执行之前把世界改掉")
    print("=" * 96)

    rows = []

    # ---- 1. 检查后被删 ----
    def s1(d):
        with open(os.path.join(d, "a.txt"), "w", encoding="utf-8") as f:
            f.write("x" * 10)

    def t1(d):
        p = os.path.join(d, "a.txt")
        os.remove(p)
        return not os.path.exists(p), f"已删除：存在={os.path.exists(p)}"

    rows.append(run_case("检查后被删", s1, t1,
                         lambda d: {"path": os.path.join(d, "a.txt"), "op": "read"}))

    # ---- 2. 检查后被换成目录 ----
    def s2(d):
        with open(os.path.join(d, "b.txt"), "w", encoding="utf-8") as f:
            f.write("y" * 10)

    def t2(d):
        p = os.path.join(d, "b.txt")
        os.remove(p)
        os.makedirs(p)
        return os.path.isdir(p), f"已换成目录：isdir={os.path.isdir(p)}"

    rows.append(run_case("检查后被换成目录", s2, t2,
                         lambda d: {"path": os.path.join(d, "b.txt"), "op": "read"}))

    # ---- 3. 检查后被收回读权限 ----
    def s3(d):
        with open(os.path.join(d, "c.txt"), "w", encoding="utf-8") as f:
            f.write("z" * 10)

    def t3(d):
        p = os.path.join(d, "c.txt")
        try:
            os.chmod(p, 0o000)
        except Exception:  # noqa: BLE001
            return False, "改权限失败（本机策略不允许）"
        try:
            with open(p, "rb"):
                pass
            return False, "改到 0o000 但仍可读（管理员身份），限制未生效"
        except PermissionError:
            return True, "已收回权限：读取抛 PermissionError"
        except Exception as e:  # noqa: BLE001
            return True, f"已收回权限：{type(e).__name__}"

    def c3(d):
        try:
            os.chmod(os.path.join(d, "c.txt"), 0o644)
        except Exception:  # noqa: BLE001
            pass

    rows.append(run_case("检查后被收回读权限", s3, t3,
                         lambda d: {"path": os.path.join(d, "c.txt"), "op": "read"},
                         cleanup=c3))

    # ---- 4. 父目录检查后被删 ----
    def s4(d):
        sub = os.path.join(d, "sub")
        os.makedirs(sub)

    def t4(d):
        sub = os.path.join(d, "sub")
        shutil.rmtree(sub)
        return not os.path.exists(sub), f"父目录已删：存在={os.path.exists(sub)}"

    rows.append(run_case("父目录检查后被删", s4, t4,
                         lambda d: {"path": os.path.join(d, "sub", "new.txt"),
                                    "op": "create"}))

    # ---- 5. 对照组：不改世界 ----
    def s5(d):
        with open(os.path.join(d, "e.txt"), "w", encoding="utf-8") as f:
            f.write("w" * 10)

    def t5(d):
        return False, "对照组，不动"

    rows.append(run_case("对照：不改世界", s5, t5,
                         lambda d: {"path": os.path.join(d, "e.txt"), "op": "read"}))

    # ---- 输出 ----
    print()
    print(f"{'场景':<22}{'前置':>6}{'判定':>9}{'改动生效':>9}{'执行':>6}{'打中':>6}")
    print("-" * 96)
    for r in rows:
        print(f"{r['name']:<22}{r['pre']:>6}{r['verdict']:>9}"
              f"{('是' if r['tampered'] else '否'):>9}"
              f"{('成' if r['exec_ok'] else '败'):>6}"
              f"{('★' if r['hit'] else ''):>6}")
    print("-" * 96)
    for r in rows:
        print(f"  {r['name']}")
        print(f"     前置={r['pre']}  判定={r['verdict']}"
              + (f"/{r['cause']}" if r['cause'] else ""))
        print(f"     改动：{r['tamper_ev'][:66]}")
        print(f"     执行：{'成功' if r['exec_ok'] else '失败'} — {r['exec_why'][:56]}")

    hits = [r for r in rows if r["hit"]]
    tested = [r for r in rows if r["tampered"] or "对照" in r["name"]]
    print()
    print("=" * 96)
    print(f"  做了 {len(tested)} 个场景，其中 {len([r for r in tested if r['tampered']])} 个真的改动了世界")
    print(f"  判 pass 后被世界改动打中：{len(hits)}/{len(tested)}")
    print()
    print("  怎么读：")
    print("    「打中」不代表判据错。判据说的是『我查的时候可以做』；")
    print("    世界在检查之后变了，那是世界的问题，不是尺子的问题。")
    print("    这份报告量化的是**暴露窗口有多大**，不往 pass 精确率里算。")
    if hits:
        print()
        print("    但它确实说明：pass 是**有保质期的**。")
        print("    检查与使用之间隔得越久、世界越活跃，pass 越不可靠。")
    print("=" * 96)

    # 自检：这个实验必须真能打出洞来，否则说明实验本身失效了
    # （比如所有 tamper 都没生效、或判定被别的规则拦住了）
    effective = [r for r in rows if r["tampered"]]
    if not effective:
        print("[FAIL] 没有一个场景真的改动了世界 —— 实验失效，结论不可用")
        return 1
    if not hits:
        print("[FAIL] 改动都生效了却一次没打中 —— 要么判据变了，要么实验写错了")
        return 1
    print("[PASS] 改动已生效且确实打中了 pass —— 暴露窗口被量化出来了")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
