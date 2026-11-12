#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""arch_audit_E.py —— 严肃看架构：数字溯源这条链上有几份真相源？只读。

不猜，只量四件事：

A. ctx 与 rep 的顶层键差集 —— 「两本账」有多大
B. paper.py 实际从 ctx 读哪些键 —— 哪些账 paper 真的在用
C. 同一份计算被跑几遍 —— ctx 与 rep 里同参数的重复调用
D. 判据/精度换算各有几处实现 —— 同一概念的重影

输出是给人看的表，不是 PASS/FAIL。
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)


def read(p):
    return io.open(os.path.join(HERE, p), encoding="utf-8").read()


def section(t):
    print()
    print("=" * 78)
    print(t)
    print("=" * 78)


def main():
    src_kit = read("mmkit.py")
    src_paper = read("paper.py")

    # ── A. ctx 顶层键 ──────────────────────────────────────────────
    # ctx = dict( ... ) 在 run() 里构造，取从 "ctx = dict(" 到配对的 ")"
    section("A · ctx 与 rep 的顶层键")
    i = src_kit.find("        ctx = dict(")
    if i < 0:
        print("  找不到 ctx = dict( —— 位置变了，先修本工具")
        return 2
    seg = src_kit[i:i + 6000]
    # 顶层键：行首缩进 12 空格的 `name=` 或 `name=`
    ctx_keys = set()
    depth = 0
    for line in seg.splitlines()[1:]:
        stripped = line.strip()
        if stripped.startswith(")"):
            break
        m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s*=", stripped)
        if m:
            ctx_keys.add(m.group(1))
    print("  ctx 顶层键 %d 个：%s" % (len(ctx_keys), ", ".join(sorted(ctx_keys))))

    rep_keys = set(re.findall(r'\brep\["([A-Za-z_][A-Za-z0-9_]*)"\]\s*=',
                              src_kit))
    rep_keys |= set(re.findall(r'\brep\["([A-Za-z_][A-Za-z0-9_]*)"\]\s*=',
                               read("mmkit.py")))
    print("  rep 被赋值的顶层键 %d 个：%s"
          % (len(rep_keys), ", ".join(sorted(rep_keys))))
    only_ctx = ctx_keys - rep_keys
    both = ctx_keys & rep_keys
    print("  两者都有 %d 个：%s" % (len(both), ", ".join(sorted(both))))
    print("  **只有 ctx、rep 没有** %d 个：" % len(only_ctx))
    for k in sorted(only_ctx):
        print("      %s" % k)

    # ── B. paper.py 从 ctx 读哪些键 ────────────────────────────────
    section("B · paper.py 实际读了哪些 ctx 键")
    used = set(re.findall(r'ctx\.get\(\s*"([A-Za-z_][A-Za-z0-9_]*)"', src_paper))
    used |= set(re.findall(r'ctx\[\s*"([A-Za-z_][A-Za-z0-9_]*)"\s*\]', src_paper))
    print("  paper.py 读 ctx 的键 %d 个：%s" % (len(used), ", ".join(sorted(used))))
    gap = used - rep_keys
    print("  其中 **rep 里没有** 的 %d 个：" % len(gap))
    for k in sorted(gap):
        print("      %-22s %s" % (k, "← 缺口" if k in ctx_keys else "（ctx 里也没有）"))

    # ── C. 同参数的重复计算 ───────────────────────────────────────
    section("C · ctx 与 rep 里的重复计算（同一函数、同参数、跑两遍）")
    calls = re.findall(r"(_[a-z0-9_]+)\(([^()]*(?:\([^()]*\)[^()]*)*)\)",
                       src_kit)
    from collections import Counter
    cnt = Counter()
    for fn, arg in calls:
        if fn.startswith("_") and fn not in ("_close", "_near"):
            cnt[(fn, re.sub(r"\s+", "", arg))] += 1
    dup = [(k, v) for k, v in cnt.items() if v >= 2]
    for (fn, arg), v in sorted(dup, key=lambda x: -x[1]):
        print("  %-22s ( %-38s ) ×%d" % (fn, arg[:38], v))
    if not dup:
        print("  没有重复调用")

    # ── D. 判据与精度换算的重影 ───────────────────────────────────
    section("D · 同一概念的实现处数")
    impl = {
        "精度的读法（小数位）": [
            ("verify.py", "def _decimals"),
            ("verify.py", "def _written_decimals"),
            ("freeze.py", "def _decimals"),
        ],
        "「论文数 vs 账本数」的匹配": [
            ("verify.py", "def _near"),
            ("freeze.py", "def _match_written"),
            ("freeze.py", "def _found_in_paper"),
            ("freeze.py", "def _close"),
        ],
        "数的抽取": [
            ("verify.py", "def extract_numbers"),
        ],
        "未溯源的分类": [
            ("untraced.py", "def classify_token"),
            ("freeze.py", "data_values and round(v, 6) in data_values"),
        ],
        "冻结哪些数": [
            ("freeze.py", "KEY_HINTS"),
            ("freeze.py", "depth <= 2"),
        ],
    }
    for label, places in impl.items():
        print("  %s：%d 处" % (label, len(places)))
        for f, needle in places:
            src = read(f)
            n = src.count(needle)
            print("      %-12s %-46s %s"
                  % (f, needle, "找到" if n else "**找不到（已改名？）**"))

    # ── E. 冻结表里「真的用得上」的比例 ───────────────────────────
    section("E · 冻结表规模 vs 论文真正引用")
    cfg = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
    for nm in ("age_struct", "nflis", "pop_panel", "icm2006c",
               "multiobjective"):
        fz = os.path.join(HERE, cfg[nm]["out"], "冻结数字.json")
        if not os.path.exists(fz):
            continue
        j = json.load(io.open(fz, encoding="utf-8"))
        items = j.get("items") or []
        tex = io.open(os.path.join(HERE, cfg[nm]["out"], "paper.tex"),
                      encoding="utf-8").read()
        import verify as V
        toks = {tk for tk, _l in V.extract_numbers(tex, skip_meta=False)}
        vals = set()
        for tk in toks:
            try:
                vals.add(abs(float(tk)))
            except ValueError:
                pass
        hit = 0
        for it in items:
            v = abs(it["value"])
            if any(abs(v - c) <= 0.5 * 10 ** -max(0, len(str(v).split(".")[-1]))
                   for c in vals):
                hit += 1
        print("  %-14s 冻结 %5d 项 ｜ 论文数字 token %4d ｜ 账本里被用到 %4d (%.1f%%)"
              % (nm, len(items), len(toks), hit,
                 100.0 * hit / max(1, len(items))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
