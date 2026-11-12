#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""numeric_genre.py —— 论文里的数字分几类，各占多少（第 124 轮）。

**这个脚本要回答一个定位问题**：

现有的 LLM 事实性评测（FActScore / HaluEval / RAGAS）问的是
「这句话是否被**知识源**支持」。那么问题来了：

> 一篇技术报告里的数字，有多少能被「知识源」支持，有多少不能？

如果**绝大多数**是「由数据算出来的」，那么「查知识源」这个判据就覆盖不了
大多数数字 —— 这是**结构性的**，不是某个工具的 bug。

## 分类口径（与 `untraced.classify_token` 一致）

| 类 | 例子 | 知识源能查吗 |
|---|---|---|
| **computed** 计算值 | `R^2=0.94`、`724173.37`、`96.95 percent` | **不能**：它是 `f(数据)` 的输出，知识源里不存在 |
| **structural** 结构值 | 「3 个节点」「24 小时」「12 板」 | 不能，但也不需要（它不是量） |
| **config** 配置值 | `0.85`（折现率）、`40` 元/kW·月（题面给的） | **能**：题面/规范里有 |
| **time** 时间标签 | `2026`、`2024-11` | 能 |

## 用法

    python tools/numeric_genre.py                 # 扫 out/runs/*/paper.tex
    python tools/numeric_genre.py out/final       # 只扫一篇
    python tools/numeric_genre.py --json
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import untraced as U


def _tokens(tex):
    """按 untraced 的口径抽 token，但要保留原串。"""
    # 去掉 \\code{} 参数（与 numbers 门一致：它看不见这些）
    t = re.sub(r"\\code\{[^}]*\}", " ", tex)
    t = re.sub(r"\\(begin|end)\{[^}]*\}", " ", t)
    out = []
    for m in re.finditer(r"(?<![\w.])-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?(?![\w])", t):
        out.append(m.group(0))
    return out


def genre(tok, has_dot=False):
    """给一个 token 判类。规则与 untraced.classify_token 同源，但这里要的是「类名」。"""
    try:
        v = float(tok)
    except ValueError:
        return "other"
    s = tok.lstrip("-")
    # 时间标签：4 位整数且在 1900-2100
    if "." not in s and len(s) == 4 and 1900 <= v <= 2100:
        return "time"
    if has_dot or "." in s:
        # 有小数 → 计算值或配置值；配置值常见于 0.xx 的比率
        return "computed"
    # 整数：结构值（<=1000）或大额计算值
    if abs(v) <= 1000:
        return "structural"
    return "computed"



def _frozen_vals(figdir):
    """读冻结表的值集合。items 是 list，每项 {path, value}。"""
    p = os.path.join(figdir, "冻结数字.json")
    if not os.path.exists(p):
        return None
    try:
        d = json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return None
    vals = set()
    for it in (d.get("items") or []):
        v = it.get("value") if isinstance(it, dict) else None
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            vals.add(round(float(v), 6))
    return vals


def genre_precise(tok, frozen):
    """精确分类：在冻结表里 -> computed；有小数但不在 -> config（假设值）。"""
    try:
        v = float(tok)
    except ValueError:
        return "other"
    s = tok.lstrip("-")
    if "." not in s and len(s) == 4 and 1900 <= v <= 2100:
        return "time"
    if frozen and round(v, 6) in frozen:
        return "computed"
    if "." in s:
        return "config"
    if abs(v) <= 1000:
        return "structural"
    return "config"


def scan(figdir):
    p = os.path.join(figdir, "paper.tex")
    if not os.path.exists(p):
        p = os.path.join(figdir, "main.tex")
    if not os.path.exists(p):
        return None
    tex = io.open(p, encoding="utf-8", errors="replace").read()
    toks = _tokens(tex)
    frozen = _frozen_vals(figdir)
    counts = {}
    counts_precise = {}
    for t in toks:
        g = genre(t)
        counts[g] = counts.get(g, 0) + 1
        gp = genre_precise(t, frozen)
        counts_precise[gp] = counts_precise.get(gp, 0) + 1
    return dict(dir=os.path.relpath(figdir, HERE), n=len(toks),
                counts=counts, counts_precise=counts_precise,
                has_frozen=frozen is not None)


def main(argv):
    if "--json" in argv:
        json_out = True
    else:
        json_out = False

    dirs = [a for a in argv[1:] if not a.startswith("-")]
    if dirs:
        targets = [d if os.path.isabs(d) else os.path.join(HERE, d) for d in dirs]
    else:
        # 目录来源以 runs.json 为准，不扫 out/runs/* ——
        # 实测 out/runs 只有 22 个目录，而 runs.json 有 23 条（有 1 题的 out 在别处）。
        targets = []
        rj = os.path.join(HERE, "runs.json")
        if os.path.exists(rj):
            import json as _j
            for name, cfg in _j.load(io.open(rj, encoding="utf-8")).items():
                out = cfg.get("out") or os.path.join("out", "runs", name)
                full = out if os.path.isabs(out) else os.path.join(HERE, out)
                if os.path.exists(os.path.join(full, "paper.tex")) or \
                        os.path.exists(os.path.join(full, "main.tex")):
                    targets.append(full)
        if not targets:
            runs = os.path.join(HERE, "out", "runs")
            if os.path.isdir(runs):
                for d in sorted(os.listdir(runs)):
                    full = os.path.join(runs, d)
                    if os.path.isdir(full):
                        targets.append(full)

    rows = [r for r in (scan(d) for d in targets) if r]
    if not rows:
        print("没有可扫的目录")
        return 2

    agg = {}
    for r in rows:
        for k, v in r["counts"].items():
            agg[k] = agg.get(k, 0) + v
    total = sum(agg.values())

    if json_out:
        print(json.dumps(dict(papers=len(rows), total=total, counts=agg,
                              per_paper=rows), ensure_ascii=False, indent=1))
        return 0

    print("扫了 %d 篇，共 %d 个数字 token" % (len(rows), total))
    print()
    print("%-12s %6s %8s" % ("类", "个数", "占比"))
    for k in ("computed", "structural", "config", "time", "other"):
        if k in agg:
            print("%-12s %6d %7.1f%%" % (k, agg[k], 100.0 * agg[k] / total))
    print()
    comp = agg.get("computed", 0)
    print("**计算值 %d 个，占 %.1f%%**" % (comp, 100.0 * comp / total))
    print()
    print("这个比例就是「知识源覆盖不了的份额」。")
    print("现有事实性评测（FActScore 类）查的是「这句话是否被知识源支持」，")
    print("而计算值在知识源里**不存在** —— 不是「不支持」，是「本来就不该在那儿」。")
    print()
    per = sorted(rows, key=lambda r: -r["counts"].get("computed", 0))[:3]
    print("计算值最多的三篇：")
    for r in per:
        print("  %-22s 共 %3d 个，其中计算值 %d" % (r["dir"], r["n"], r["counts"].get("computed", 0)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
