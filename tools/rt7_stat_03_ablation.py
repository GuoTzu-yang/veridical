#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rt7_stat_03_ablation.py —— 只读：在内存里做消融，不删任何文件。

三个条件，对 23 道题各算一次：
  C0  现状：溯源池 = verify.load_outputs(figdir)（目录下所有 .json/.csv，
      含 冻结数字.json）
  C1  只去掉冻结表：池 = C0 减去 冻结数字.json 那个对象
      —— 与 ablate_provenance.py 的「拷一份、删掉冻结表」等价（它也是
      只删这一个文件），但没有文件操作
  C2  真空池：池 = []  —— 「一条出处都不给」的真实反事实，用来看 0 是
      算术还是测量

每个条件同时报两个口径：
  full = verify 口径（全部 token）
  dec  = gate 口径（只算带小数的 token，与 freeze.check_paper 一致）

还报：每个 run 目录里 json/csv 的个数（「残余 11.5%」是从哪来的）、
C0→C1 的配对差分（b/c 两个方向）与 bootstrap 区间。
"""
import io
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.chdir(HERE)

import verify as V          # noqa: E402

CFG = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
FIVE = ["heat_sink", "queueing", "icm2006c", "evaluation", "population"]


def load_split(d):
    """把目录里的产物分成 (全池, 冻结表对象, 其余池, 文件清单)。

    注意：不能按 `is` 比较对象 —— verify.load_outputs 每次都重新 json.load，
    同一文件两次读出来是两个对象。必须按**文件名**排除。
    """
    names = []
    full, rest = [], []
    for root, _dd, files in os.walk(d):
        for f in sorted(files):
            if f.startswith("."):
                continue
            p = os.path.join(root, f)
            rel = os.path.relpath(p, d)
            if f.endswith(".json"):
                try:
                    obj = json.load(io.open(p, encoding="utf-8"))
                except Exception:                    # noqa: BLE001
                    continue
                if V._looks_self_proved(obj):
                    continue
                names.append(rel)
                full.append(obj)
                if f != "冻结数字.json":
                    rest.append(obj)
            elif f.endswith(".csv"):
                try:
                    txt = io.open(p, encoding="utf-8", errors="replace").read()
                except OSError:
                    continue
                names.append(rel)
                full.append(txt)
                rest.append(txt)
    return full, rest, names


def traced_counts(tex, pool):
    """返回 (判定的 token 数, 判定口径=dec?, 已溯源数, 未溯源 token 列表)。

    走 verify.trace 的同一条匹配判据（_near + 书写精度）。
    """
    toks = V.extract_numbers(tex)                 # full 口径
    dec = [(t, l) for t, l in toks if "." in t]   # gate 口径的子集
    nums = V.collect_output_numbers(pool)

    def judge(pairs):
        tr, un = 0, []
        for t, _l in pairs:
            try:
                v = float(t)
            except ValueError:
                continue
            d = V._written_decimals(t)
            if any(V._near(v, p, d) for p in nums):
                tr += 1
            else:
                un.append(t)
        return tr, un

    trf, unf = judge(toks)
    trd, und = judge(dec)
    return len(toks), trf, unf, len(dec), trd, und


rows = []
for name, it in CFG.items():
    d = os.path.join(HERE, it["out"])
    tex_p = os.path.join(d, "paper.tex")
    if not os.path.exists(tex_p):
        continue
    tex = io.open(tex_p, encoding="utf-8").read()
    full, rest, names = load_split(d)
    c0 = traced_counts(tex, full)
    c1 = traced_counts(tex, rest)
    c2 = traced_counts(tex, [])
    rows.append(dict(name=name, nfiles=len(names),
                     has_frozen="冻结数字.json" in names,
                     pool=names,
                     n_full=c0[0], t0_full=c0[1], t1_full=c1[1], t2_full=c2[1],
                     n_dec=c0[3], t0_dec=c0[4], t1_dec=c1[4], t2_dec=c2[4]))
    print("  %-16s files=%2d  FULL %3d/%3d -> %3d -> %2d | "
          "DEC %3d/%3d -> %3d -> %2d"
          % (name, len(names), c0[1], c0[0], c1[1], c2[1],
             c0[4], c0[3], c1[4], c2[4]))

print()
hdr = "%-16s %5s %10s %10s %8s %10s %10s %8s"
print(hdr % ("run", "files", "C0-full", "C1-full", "C2", "C0-dec", "C1-dec", "C2"))
print("-" * 92)
for r in sorted(rows, key=lambda x: x["name"]):
    print(hdr % (r["name"], r["nfiles"],
                 "%d/%d" % (r["t0_full"], r["n_full"]),
                 "%d/%d" % (r["t1_full"], r["n_full"]),
                 "%d" % r["t2_full"],
                 "%d/%d" % (r["t0_dec"], r["n_dec"]),
                 "%d/%d" % (r["t1_dec"], r["n_dec"]),
                 "%d" % r["t2_dec"]))

print()
print("=== 合计（23 题）===")
Nf = sum(r["n_full"] for r in rows)
Nd = sum(r["n_dec"] for r in rows)
T0f = sum(r["t0_full"] for r in rows)
T1f = sum(r["t1_full"] for r in rows)
T2f = sum(r["t2_full"] for r in rows)
T0d = sum(r["t0_dec"] for r in rows)
T1d = sum(r["t1_dec"] for r in rows)
T2d = sum(r["t2_dec"] for r in rows)
print("  full 口径  %d/%d = %.2f%%  ->  去冻结表 %d/%d = %.2f%%  ->  空池 %d = %.2f%%"
      % (T0f, Nf, 100.0 * T0f / Nf, T1f, Nf, 100.0 * T1f / Nf, T2f,
         100.0 * T2f / Nf))
print("  dec  口径  %d/%d = %.2f%%  ->  去冻结表 %d/%d = %.2f%%  ->  空池 %d = %.2f%%"
      % (T0d, Nd, 100.0 * T0d / Nd, T1d, Nd, 100.0 * T1d / Nd, T2d,
         100.0 * T2d / Nd))
print("  冻结表的边际贡献（full 口径）= %.2f pp；去表后残余 %.2f%% 全部来自"
      "同目录的其它 json/csv" % (100.0 * (T0f - T1f) / Nf, 100.0 * T1f / Nf))

print()
print("=== 每个 run 的溯源池（除 paper.tex 外，能进池的 json/csv）===")
for r in sorted(rows, key=lambda x: x["name"]):
    print("  %-16s %s" % (r["name"], ", ".join(r["pool"])))
OLD = {x["name"]: x for x in json.load(
    io.open(os.path.join(HERE, "out", "final", "ablation.json"),
            encoding="utf-8"))}
print("  %-14s %-22s %-22s %s"
      % ("run", "论文(有表/无表)", "现在重算(有表/无表)", "分母"))
for nm in FIVE:
    r = [x for x in rows if x["name"] == nm]
    if not r:
        continue
    r = r[0]
    o = OLD.get(nm, {})
    print("  %-14s %-22s %-22s %d -> %d"
          % (nm,
             "%.1f%%/%.1f%%" % (o.get("with_table", -1), o.get("without_table", -1)),
             "%.1f%%/%.1f%%" % (100.0 * r["t0_full"] / r["n_full"],
                                100.0 * r["t1_full"] / r["n_full"]),
             o.get("n_total", -1), r["n_full"]))
print("  tab 里那列「Orphan tokens」= 234/192/263/222/178，与 ablation.json 的")
print("  n_total 逐项相同 —— 它是**分母**，不是孤儿数（孤儿应是 14/15/48/17/9）。")

print()
print("=== 配对差分 + bootstrap（C0 vs C1，full 口径逐 token 配对）===")
random.seed(20261111)
# 逐 token 的配对样本：同一 token 在 C0/C1 下是否溯源
pairs = []
per_run = {}
for name, it in CFG.items():
    d = os.path.join(HERE, it["out"])
    tex_p = os.path.join(d, "paper.tex")
    if not os.path.exists(tex_p):
        continue
    tex = io.open(tex_p, encoding="utf-8").read()
    full, rest, names = load_split(d)
    toks = V.extract_numbers(tex)
    n0 = V.collect_output_numbers(full)
    n1 = V.collect_output_numbers(rest)
    loc = []
    for t, _l in toks:
        try:
            v = float(t)
        except ValueError:
            continue
        dd = V._written_decimals(t)
        a = any(V._near(v, p, dd) for p in n0)
        b = any(V._near(v, p, dd) for p in n1)
        loc.append((a, b))
    pairs += loc
    per_run[name] = loc


def diff(ps):
    b = sum(1 for a, c in ps if a and not c)
    c = sum(1 for a, cc in ps if cc and not a)
    return (b - c) / len(ps)


point = diff(pairs)
bs = []
for _ in range(2000):
    s = [pairs[random.randrange(len(pairs))] for _ in range(len(pairs))]
    bs.append(diff(s))
bs.sort()
print("  Δ(有表-无表) = %+.3f  %d/%d" % (point, sum(1 for a, c in pairs if a and not c),
                                        len(pairs)))
print("  token 级 bootstrap 95%% = [%+.3f, %+.3f]（n=%d，配对）"
      % (bs[49], bs[1949], len(pairs)))
print("  反向（无表能溯源、有表不能）= %d —— 去掉出处不可能变好，"
      % sum(1 for a, c in pairs if c and not a))

# 题级（cluster）bootstrap：重采样 23 道题
names = sorted(per_run)
bsc = []
for _ in range(2000):
    pick = [names[random.randrange(len(names))] for _ in names]
    allp = []
    for nm in pick:
        allp += per_run[nm]
    bsc.append(diff(allp))
bsc.sort()
print("  题级 cluster bootstrap 95%% = [%+.3f, %+.3f]（23 题，含题目间差异）"
      % (bsc[49], bsc[1949]))
print("  5 题（tab:ablation 的那 5 题）fit 出来的区间：")
five_pairs = []
for nm in FIVE:
    five_pairs += per_run.get(nm, [])
b5 = []
for _ in range(2000):
    s = [five_pairs[random.randrange(len(five_pairs))]
         for _ in range(len(five_pairs))]
    b5.append(diff(s))
b5.sort()
print("    token 级 = [%+.3f, %+.3f]；n_tokens=%d"
      % (b5[49], b5[1949], len(five_pairs)))
