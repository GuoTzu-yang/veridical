#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
schema.py —— 导出插件能力清单（P03，第 3 轮）

为什么这是前提
--------------
LLM 要提「用 run 跑 --y 热阻 --x 宽度」，它必须知道：
    · run 这个子命令存在吗
    · run 接受 --y 和 --x 吗，类型是什么
不知道就只能瞎猜，猜错的提案映射不成命令 → 整条链路断在第一步。

之前 contract.reflect_cmds() 想从 argparse 反射，但 mmkit 用的是
**单一 parser + if a.cmd == 分派**，没有 subparsers，反射不到。
所以改成静态分析：从源码里读出「每个分支用了哪些参数」。

方法
----
1. 正则抓 amp.add_argument 的定义 → 参数名 / 类型 / 默认值
2. 正则抓每个 `a.cmd == "xxx"` 分支体内访问的 `a.yyy`
3. 交叉：分支用到的参数 ∩ argparse 定义过的参数
4. 全局参数（如 --data / --sheet）标出来，所有分支都能用

输出
----
schema.json：
    {
      "generated_at": "...",
      "source": "mmkit.py",
      "global_args": {...},
      "commands": {"run": {"args": {...}}, ...},
      "metrics": {...}
    }

用法
    python schema.py            # 生成 schema.json
    python schema.py --check    # 只校验不写
    python schema.py selftest
"""

from __future__ import annotations

import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "schema.json")

# 插件能算出来的指标（成对：指标名 → 从哪个字段取）
METRICS = {
    "cv_rmse_max": dict(field="cv_rmse", cmp="<=",
                        desc="交叉验证 RMSE 上限"),
    "cv_rmse_min": dict(field="cv_rmse", cmp=">=",
                        desc="交叉验证 RMSE 下限"),
    "r2_min": dict(field="r2", cmp=">=", desc="R² 下限"),
    "r2_max": dict(field="r2", cmp="<=", desc="R² 上限"),
    "front_size_min": dict(field="front", cmp=">=",
                           desc="帕累托前沿点数下限"),
    "bp_max": dict(field="bp", cmp="<=",
                   desc="Breusch-Pagan 统计量上限"),
    "coverage_min": dict(field="coverage", cmp=">=",
                         desc="时间覆盖率下限"),
    "n_rows_min": dict(field="n_rows", cmp=">=", desc="可用行数下限"),
}



# ══════════════════════════════════════════════════════════════════════
#  每个子命令干什么
#
#  为什么非要有这张表
#  ------------------
#  mmkit 的 22 个参数全挂在顶层 argparse 上，`cmd` 只是个 choices。
#  于是 `mmkit race --help` 和 `mmkit run --help` 输出**完全一样** ——
#  58 个全局参数，看不出命令之间的区别。实测确认过。
#
#  结果是：LLM 只知道有个命令叫 race，不知道它和 run 差在哪，
#  于是每次都退回 run 一条龙，插件的能力全被绕过。
#
#  这张表是「能力可发现」的唯一入口。
# ══════════════════════════════════════════════════════════════════════

DESC = {
    "advise": "定题：判断题型（关系与解释/预测/优化/评价）+ 逐条可复核依据。"
              "**建模第一步**，先用它确认方向再选工具",
    "race": "模型赛马：多个模型结构 x 多 seed 的交叉验证对比，出 RMSE/R2 表。"
            "要回答「为什么用这个模型」就跑它",
    "solve": "约束优化：单目标最大化/最小化，或 --constraint 带约束；"
             "含 Pareto 前沿与膝点",
    "forecast": "时间序列预测：--t 时间轴、--y 目标，外推 --horizon 步",
    "grey": "灰色预测 GM(1,1)：小样本序列外推，与 forecast 互为对照",
    "greyrel": "灰色关联 + 模糊综合评价：--directions 定指标方向、"
               "--weights/--ahp 定权重、--membership/--grades 做模糊评。"
               "评价类题目的主力",
    "ahp": "层次分析：判断矩阵 --ahp 求权重，带一致性检验",
    "cluster": "聚类：--x 选变量、--k 定簇数，出划分与簇质量",
    "graph": "--op 四选一：dijkstra 最短路 / mst 最小生成树 / "
             "flow 最大流 / tsp 旅行商",
    "ode": "常微分方程：--rhs 给右端表达式，--method rk45|rk4",
    "dim": "量纲分析：--var '名字=量纲'（等号！）求 Buckingham Pi 群",
    "profile": "数据剖面：每列的分布、缺失、异常摘要",
    "clean": "清洗：列名英文化（--names-out）、导出 CSV",
    "merge": "多表合并：按共同列合并多个 sheet 或文件",
    "plot": "--kind 十六种图：scatter/forecast/bar/pareto/corr/pred/sens/"
            "flow/box/hist/resid/qq/tornado/cand/surface/surfaces",
    "video": "GIF/MP4：把多张图串成逐帧动画",
    "hints": "给出可复制的命令提示（含 --claim/--compile 的常用组合）",
    # cand / surface 不是子命令，是 plot 的 --kind 取值。
    # 它们原来被写进 cmd 的 choices，于是 `mmkit.py cand` 会**静默跑出整篇论文**
    # （落到 main() 末尾的 run() 兜底）。两条 desc 留在这里只是文档，
    # 已不在命令表里（第 93 轮）。
    "cand": "（不是子命令）候选模型对比图 —— 用 `plot --kind cand`",
    "surface": "（不是子命令）响应面三维曲面 —— 用 `plot --kind surface`",
    # 这四个原来完全没有 desc：schema.json 告诉了 LLM「有这个命令」，
    # 却不说它干什么，等于给了个没有说明的按钮。
    "fuzzy": "模糊综合评价（与 greyrel 同一分支）：--membership 隶属度、"
             "--grades 等级、--weights/--ahp 权重",
    "experiment": "试错循环：propose → exec → judge → 下一轮，"
                  "--rounds 定轮数、--budget 定预算，产出「试过什么、否掉了什么」",
    "contract": "提案契约：把一次建模提案写成可检查的 JSON（--proposal），"
                "缺字段/越界会当场指出",
    "skeleton": "出稿骨架：--from-tex 从已生成的 tex 里列出可被 LLM 重写的段落"
                "（摘要、结论），--lang 选语言",
    "run": "一条龙：读数据到出 PDF 全自动。**自动模式**，"
           "会替你做掉所有建模决定 —— DSH 主导建模时不要用它",
    "selftest": "自检：所有内置用例",
}

def _parse_add_arguments(src: str) -> dict:
    """从 ap.add_argument(...) 抠出参数定义。

    只处理单行定义和简单跨行（括号内没有嵌套的 add_argument）。
    """
    args = {}
    # 抓 ap.add_argument( ... ) 的整块（非贪婪，到第一个不嵌套的右括号）
    for m in re.finditer(r"ap\.add_argument\(\s*(.*?)\)\s*(?:\n|$)",
                         src, re.S):
        body = m.group(1)
        # 参数名
        nm = re.search(r"[\"'](--?[\w-]+)[\"']", body)
        if not nm:
            continue
        flag = nm.group(1)
        dest = flag.lstrip("-").replace("-", "_")
        # 类型
        t = "str"
        tm = re.search(r"type\s*=\s*(\w+)", body)
        if tm:
            mp = {"int": "int", "float": "float", "str": "str"}
            t = mp.get(tm.group(1), "str")
        if re.search(r"action\s*=\s*[\"']store_true", body):
            t = "bool"
        # choices
        ch = re.search(r"choices\s*=\s*(\[[^\]]*\]|[\w_.]+)", body)
        choices = None
        if ch:
            raw = ch.group(1)
            if raw.startswith("["):
                choices = re.findall(r"[\"']([^\"']+)[\"']", raw)
            elif raw.endswith("()"):
                choices = f"<{raw}>"   # 动态生成，标记出来
        # 默认值
        dv = re.search(r"default\s*=\s*([^,)]+)", body)
        default = dv.group(1).strip() if dv else None
        # help
        hp = re.search(r"help\s*=\s*[\"']([^\"']*)", body)
        args[dest] = dict(flag=flag, type=t,
                          choices=choices,
                          default=default,
                          help=(hp.group(1)[:60] if hp else ""))
    return args


def _parse_branches(src: str) -> dict:
    """抓每个 `a.cmd == "xxx"` **以及** `a.cmd in ("xxx","yyy")` 分支体里用到的 a.yyy。

    原来只认 `a.cmd == "x"`，于是 `if a.cmd in ("greyrel", "fuzzy")` 这一支
    只登记了 greyrel，**fuzzy 从 schema 里整条消失** —— LLM 看 schema.json
    就不知道 fuzzy 存在，也就永远不会调它。
    """
    out = {}
    # 分支范围按**缩进**判，不按「下一个 a.cmd 标记」。
    #
    # 为什么（第 93 轮实测）：greyrel/fuzzy 的代码是
    #     if a.cmd in ("greyrel", "fuzzy"):
    #         def _mat(...)...
    #         if a.cmd == "greyrel":     ← 嵌套在里面的分支
    #             ...a.directions...
    # 若拿「下一个 a.cmd 标记」当边界，外层会在嵌套那行被截断：
    # greyrel 拿到了自己的参数，**fuzzy 只剩空 body → args=[]**，
    # 于是 schema.json 告诉 LLM「有 fuzzy 这个命令」却不给它任何参数。
    lines = src.splitlines(keepends=True)
    offsets, acc = [], 0
    for ln in lines:
        offsets.append(acc)
        acc += len(ln)

    def _line_of(pos: int) -> int:
        lo, hi = 0, len(offsets) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if offsets[mid] <= pos:
                lo = mid
            else:
                hi = mid - 1
        return lo

    def _body(pos: int) -> str:
        i0 = _line_of(pos)
        line = lines[i0]
        indent = len(line) - len(line.lstrip())
        j = i0 + 1
        while j < len(lines):
            cur = lines[j]
            if cur.strip():
                cur_indent = len(cur) - len(cur.lstrip())
                if cur_indent <= indent and not cur.lstrip().startswith("#"):
                    break
            j += 1
        return "".join(lines[i0:j])

    groups: dict = {}
    for m in re.finditer(r'a\.cmd\s*==\s*"(\w+)"', src):
        groups.setdefault(m.start(), []).extend([m.group(1)])
    for m in re.finditer(r'a\.cmd\s+in\s*\(([^)]*)\)', src):
        groups.setdefault(m.start(), []).extend(
            re.findall(r'"(\w+)"', m.group(1)))
    if not groups:
        return out
    for pos, names in sorted(groups.items()):
        body = _body(pos)
        used = sorted({x for x in re.findall(r"\ba\.(\w+)", body)
                       if x != "cmd"})
        for cmd in names:
            # 同一个命令可能出现在多处（外层 in + 内层 ==）：
            # 取并集，免得内层把外层发现的参数覆盖掉。
            if used:
                out[cmd] = sorted(set(out.get(cmd, [])) | set(used))
            else:
                out.setdefault(cmd, [])

    # run 是「默认动作」，不走 a.cmd 分支：main() 末尾直接
    # `return run(a.data, a.y, ...)`。LLM 最常用的就是它，必须补进来。
    # 注意：不能用 [^)]* —— 参数列表里有嵌套括号，会被提前截断。
    m = re.search(r"return\s+run\(", src)
    if m:
        i = m.end()
        depth, start = 1, i
        while i < len(src) and depth > 0:
            if src[i] == "(":
                depth += 1
            elif src[i] == ")":
                depth -= 1
            i += 1
        body = src[start:i - 1]
        used = sorted({x for x in re.findall(r"\ba\.(\w+)", body)})
        out["run"] = used
    return out


def build(path=None) -> dict:
    path = path or os.path.join(HERE, "mmkit.py")
    src = open(path, encoding="utf-8").read()
    decl = _parse_add_arguments(src)
    branches = _parse_branches(src)

    # 全局参数：出现在 ≥3 个分支里的
    freq = {}
    for cmd, used in branches.items():
        for u in used:
            freq[u] = freq.get(u, 0) + 1
    n_cmd = max(1, len(branches))
    global_dests = {d for d, n in freq.items()
                    if n >= max(3, n_cmd // 3)}

    cmds = {}
    for cmd, used in sorted(branches.items()):
        args = {}
        for d in used:
            spec = decl.get(d)
            if spec:
                args[spec["flag"]] = dict(
                    type=spec["type"], choices=spec["choices"],
                    default=spec["default"], help=spec["help"],
                    dest=d)
        cmds[cmd] = dict(desc=DESC.get(cmd, ""), args=args,
                         n_args=len(args),
                         uses_global=sorted(set(used) & global_dests))

    glob = {decl[d]["flag"]: dict(type=decl[d]["type"],
                                  default=decl[d]["default"],
                                  help=decl[d]["help"], dest=d)
            for d in sorted(global_dests) if d in decl}

    return dict(
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        source=os.path.basename(path),
        n_commands=len(cmds),
        n_declared_args=len(decl),
        global_args=glob,
        commands=cmds,
        metrics=METRICS,
        note=("args 是「该子命令实际访问到的 a.xxx 且 argparse 里定义过」的交集。"
              "没列出来的参数即使定义了，该子命令也不读。"),
    )


def problems(sc: dict) -> list[str]:
    """schema 自身的健康检查。"""
    p = []
    if sc["n_commands"] < 10:
        p.append(f"子命令只有 {sc['n_commands']} 个，疑似解析失败")
    if not sc["global_args"]:
        p.append("没有识别出任何全局参数")
    empty = [c for c, v in sc["commands"].items() if v["n_args"] == 0]
    if len(empty) > sc["n_commands"] // 2:
        p.append(f"{len(empty)} 个子命令解析不到参数：{empty[:5]}")
    return p


def selftest() -> int:
    bad = 0
    n = 0

    def ck(name, cond, detail=""):
        nonlocal bad, n
        n += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
              + (f"  — {detail}" if detail else ""))
        if not cond:
            bad += 1

    sc = build()
    ck("能解析出子命令", sc["n_commands"] >= 15, f"{sc['n_commands']} 个")
    ck("能解析出参数定义", sc["n_declared_args"] >= 30,
       f"{sc['n_declared_args']} 个")
    ck("有全局参数", bool(sc["global_args"]),
       str(list(sc["global_args"])[:4]))

    # 关键子命令必须有参数
    for c in ("run", "plot", "forecast", "solve", "clean"):
        v = sc["commands"].get(c)
        ck(f"{c} 有参数", bool(v and v["n_args"] > 0),
           f"{v['n_args'] if v else 0} 个")

    # run 必须能用 --y / --x
    run = sc["commands"].get("run", {}).get("args", {})
    ck("run 有 --y", "--y" in run, str(list(run)[:6]))
    ck("run 有 --x", "--x" in run)

    # plot 必须有 --kind 且带 choices
    pk = sc["commands"].get("plot", {}).get("args", {}).get("--kind", {})
    ck("plot 的 --kind 有 choices", bool(pk.get("choices")),
       f"{len(pk.get('choices') or [])} 种")

    # 指标表与指标一一对应
    ck("指标表非空", len(sc["metrics"]) >= 6, f"{len(sc['metrics'])} 个")
    ck("指标都有 field/cmp",
       all("field" in v and "cmp" in v for v in sc["metrics"].values()))

    ck("schema 无明显问题", not problems(sc), str(problems(sc))[:60])

    # 往返：写出去再读回来必须一致
    # 必须**无条件写**。原来写成 `if not os.path.exists(OUT)` 等于
    # 「文件存在就不写」，自测于是永远在读旧文件 —— 声称验往返，
    # 实际验历史数据（schema.json 曾停在 18 条，而 build() 已经 19）。
    write(sc)
    sc2 = json.load(open(OUT, encoding="utf-8"))
    ck("落盘后可读回", sc2["n_commands"] == sc["n_commands"],
       f"{sc2['n_commands']}")

    print(f"\n{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1


def write(sc: dict) -> None:
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(sc, f, ensure_ascii=False, indent=2)
    print(f"  已写 {OUT}（{os.path.getsize(OUT)} 字节，"
          f"{sc['n_commands']} 子命令）")


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="导出插件能力清单")
    ap.add_argument("cmd", nargs="?", default="build",
                    choices=["build", "check", "selftest"])
    a = ap.parse_args(argv)

    if a.cmd == "selftest":
        return selftest()
    sc = build()
    ps = problems(sc)
    if ps:
        print("  ⚠ schema 有问题：")
        for p in ps:
            print(f"    · {p}")
    if a.cmd == "check":
        print(f"  子命令 {sc['n_commands']} / 参数 {sc['n_declared_args']} / "
              f"全局 {len(sc['global_args'])}")
        return 0 if not ps else 1
    write(sc)
    return 0 if not ps else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
