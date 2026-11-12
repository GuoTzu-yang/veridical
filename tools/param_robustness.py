#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""param_robustness.py —— 不设敏感度阈值，直接检验「结论在参数区间上恒成立吗」。

用户问：「如果设立敏感度阈值呢，用数学的方法解决它，化为公式？」
再问：「以绝对的数学，保证极高的围栏。」

答案分三层，只有第一层是「绝对」的：

**第一层 · 定理（可证）**
    舍入容差：|round(x,dec) − x| ≤ 0.5·10^−dec 是定理，所以
    「两个数在 dec 位书写相同」⟺「|a − b| ≤ 0.5·10^−dec」。
    这一层已经做到（`freeze._match_written`），且容差不是选择。

**第二层 · 可穷举（可证）**
    分类器是**阶梯函数**：只在 token 的取值处跳变。
    `A_struct(k) = #{t : |t| ≤ k, t 无小数, t 不是年份}` 之类。
    整 token 只有有限个（本轮实测 159 个），所以**跳点有限**，
    参数空间可以被**穷举**而不是抽样 —— 穷举是证明，抽样不是。
    本工具第 123 轮修：原来扫 14 个预设值（抽样），现在扫**全部跳点**
    并给出**精确的稳定域边界**。

**第三层 · 不可证（必须承认）**
    ·「结论本身对不对」——内容问题，不是数学问题
    ·「未知缺陷能不能检出」——归纳问题
    ·「参数选哪个值」——风险偏好，把 10% 改叫 ε 只是换名字

用法：
    python tools/param_robustness.py
    python tools/param_robustness.py --json
退出码：0 = 所有结论在整个参数域鲁棒；1 = 有结论在某段崩。
"""
import io
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

OUT = os.path.join(HERE, "out", "final")

# 参数空间：**穷举全部跳点**，不是抽样。
# 分类器是阶梯函数，只在 token 的取值处跳变；整 token 有限（本轮 159 个），
# 所以扫描「0 + 每个不同取值 + 每个取值−1」就覆盖了所有可能的分类结果。
# 第 123 轮修：原来写死 14 个预设值（0,1,2,5,10,...,1e9），那是抽样，
# 抽样只能证伪（找到崩点），不能证明鲁棒。
def _jump_points():
    """返回 {0} ∪ {每个整 token 的值} ∪ {值−1}，升序去重。"""
    vals = set()
    for t in _tokens():
        if "." in t:
            continue
        try:
            v = abs(float(t))
        except ValueError:
            continue
        if v == int(v):
            vals.add(int(v))
            if v > 0:
                vals.add(int(v) - 1)
    vals.add(0)
    return tuple(sorted(v for v in vals if 0 <= v <= 10 ** 9))


STRUCT_LIMITS = None          # 运行时填充（依赖论文本身）
MAX_UNTRACED = (0.0, 0.005, 0.01, 0.05, 0.10, 0.50, 1.0)


def _theory():
    """返回论文正文，但**排除 Assumptions 节**。

    为什么必须排除（第 123 轮，实测三次数字都不一样）：
    统计对象是论文自身，而 Assumptions 节正好在**自述**这些统计
    （「at a boundary of ten the count is 179 computed against 44 structural」）。
    于是每改一次那句话，论文就多/少一个 token，统计跟着变 —— 自我指涉，
    永远收敛不到不动点。实测：D_at_ten 在 179 / 181 之间跳，跳点数 106 / 108。

    排除「关于分类的元陈述」这一节后，统计只反映**被分类的正文**，
    与本节怎么写无关，迭代到不动点。
    """
    import re as _re
    tex = io.open(os.path.join(OUT, "paper.tex"), encoding="utf-8",
                  errors="replace").read()
    parts = _re.split(r"\n\\section\*?\{([^}]*)\}", "\n" + tex)
    keep = [parts[0]]
    for i in range(1, len(parts), 2):
        title = parts[i].strip().lower()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        if "assumption" in title:
            continue                      # 元陈述，不计入被分类的正文
        keep.append(body)
    return "\n".join(keep)


def _tokens():
    """用**真分词器**取 token，不自己重写公式。

    第 123 轮教训：手写 `#{v > k}` 当 D(k) 会多算 60 个，
    因为漏掉了「在 data_values 里要走 E_data」这一支。公式必须完整
    反映实现，所以这里调 `verify.extract_numbers` + `untraced.classify_token`。
    """
    import verify
    return [t for t, _ln in verify.extract_numbers(_theory(), skip_meta=False)]


def _dist(limit):
    """在给定 struct_limit 下的分类分布。"""
    import untraced as U
    dv = U.data_values_of(U.find_data_file(OUT))
    toks = _tokens()
    c = Counter(U.classify_token(t, data_values=dv, struct_limit=limit)
                for t in toks)
    return dict(A=c.get("A_struct", 0), D=c.get("D_computed", 0),
                E=c.get("E_data", 0), n=len(toks))


def _numbers(limit_override=None, untraced_override=None):
    """在给定参数下跑 check_paper。"""
    import freeze
    import untraced as U
    tex = io.open(os.path.join(OUT, "paper.tex"), encoding="utf-8",
                  errors="replace").read()
    fz = json.load(io.open(os.path.join(OUT, "冻结数字.json"),
                          encoding="utf-8"))
    dv = U.data_values_of(U.find_data_file(OUT))
    kw = dict(single_point=True, data_values=dv, strict_source=True)
    if untraced_override is not None:
        kw["max_untraced"] = untraced_override
    r = freeze.check_paper(tex, fz, **kw)
    return dict(ok=bool(r["ok"]), n=r.get("n_numbers") or 0,
                bad=len(r["untraced"]),
                nint=int(r.get("n_int_not_judged") or 0))


# ── 结论集：全部来自论文正文，且都可机械判定 ──
def claims():
    out = []

    # C1 结构类多于计算类（论文 tab:anatomy 的定性描述）
    def c1(lim, mu):
        d = _dist(lim)
        return d["A"] > d["D"], "A=%d D=%d" % (d["A"], d["D"])
    out.append(("C1 结构类多于计算类", c1, "struct_limit"))

    # C2 计算类非空（论文说 D_computed 是一类，不能是 0）
    def c2(lim, mu):
        d = _dist(lim)
        return d["D"] >= 5, "D=%d" % d["D"]
    out.append(("C2 计算类至少 5 个", c2, "struct_limit"))

    # C3 gate 的 numbers 项通过（论文 claims 表第 1、2 行依赖它）
    def c3(lim, mu):
        r = _numbers(untraced_override=mu)
        return r["ok"], "ok=%s bad=%d n=%d" % (r["ok"], r["bad"], r["n"])
    out.append(("C3 numbers 门通过", c3, "max_untraced"))

    # C4 整数 token 至少 100 个（论文说 160 个未纳入判定）
    def c4(lim, mu):
        r = _numbers()
        return r["nint"] >= 100, "n_int_not_judged=%d" % r["nint"]
    out.append(("C4 整数 token >= 100", c4, "—（与两参数无关）"))

    # C5 未溯源比例为 0（论文说 37/37）
    def c5(lim, mu):
        r = _numbers()
        return r["bad"] == 0, "untraced=%d" % r["bad"]
    out.append(("C5 未溯源为 0", c5, "—（与两参数无关）"))

    return out


def main(argv):
    global STRUCT_LIMITS
    STRUCT_LIMITS = _jump_points()
    rows = []
    for name, fn, space in claims():
        # 只扫与该结论相关的参数；无关参数固定默认值
        if "struct_limit" in space:
            grid = [(lim, 0.10) for lim in STRUCT_LIMITS]
        elif "max_untraced" in space:
            grid = [(1000, mu) for mu in MAX_UNTRACED]
        else:
            grid = [(1000, 0.10)]
        fails = []
        last_ok = None
        for lim, mu in grid:
            try:
                ok, ev = fn(lim, mu)
            except Exception as e:                      # noqa: BLE001
                ok, ev = False, "执行出错：%s" % e
            if not ok:
                fails.append(dict(limit=lim, max_untraced=mu, evidence=ev))
            else:
                last_ok = lim
        # 精确稳定域：对 struct_limit 类结论，报「最小的成立边界」
        stable_from = None
        if "struct_limit" in space and fails:
            after = [lim for lim in STRUCT_LIMITS
                     if lim > max(f["limit"] for f in fails)]
            stable_from = after[0] if after else None
        rows.append(dict(claim=name, space=space, n_points=len(grid),
                         fails=fails, robust=(not fails),
                         stable_from=stable_from))

    # ── 写实测值，供 tools/freeze_paper_numbers.py 登记进冻结表 ──
    # 论文 §Assumptions 引用的 175 / 44 / 150 / 69 / 100 必须能追到这里，
    # 否则它们就是手写常量（第 123 轮：我第一版写错了 131，就是手算的锅）。
    derived = {}
    try:
        d10 = _dist(10)
        d1k = _dist(1000)
        derived["robust_A_at_ten"] = d10["A"]
        derived["robust_D_at_ten"] = d10["D"]
        derived["robust_A_at_thousand"] = d1k["A"]
        derived["robust_D_at_thousand"] = d1k["D"]
        # C1（A > D）的稳定域下界：扫到第一个成立的边界
        lower = None
        for lim in STRUCT_LIMITS:
            d = _dist(lim)
            if d["A"] > d["D"]:
                lower = lim
                break
        derived["robust_stable_boundary"] = lower if lower is not None else -1
        # 跳点数本身也要能溯源：论文写「all 106 of them」
        derived["robust_n_jumps"] = len(STRUCT_LIMITS)
    except Exception as e:                              # noqa: BLE001
        derived["robust_error"] = 0.0
        print("写 derived 出错：%s" % e, file=sys.stderr)

    with io.open(os.path.join(OUT, "param_robustness.json"), "w",
                 encoding="utf-8", newline="\n") as fh:
        json.dump(dict(rows=rows, derived=derived), fh,
                  ensure_ascii=False, indent=1)

    if "--json" in argv:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0 if all(r["robust"] for r in rows) else 1

    print("结论鲁棒性：%d 条结论 × **穷举全部跳点**" % len(rows))
    print("（参数空间大小：struct_limit %d 点，max_untraced %d 点）"
          % (len(STRUCT_LIMITS), len(MAX_UNTRACED)))
    print("（判据：对所有点都成立 = 鲁棒；存在一个点不成立 = 依赖参数）")
    print()
    for r in rows:
        tag = "鲁棒" if r["robust"] else "**依赖参数**"
        print("  [%-8s] %-24s 扫 %d 点（%s）"
              % (tag, r["claim"][:24], r["n_points"], r["space"]))
        if r.get("stable_from"):
            print("            精确稳定域：limit >= %s" % r["stable_from"])
        for f in r["fails"][:3]:
            print("            崩于 limit=%s → %s"
                  % (f["limit"], f["evidence"][:56]))
        if len(r["fails"]) > 3:
            print("            ……另有 %d 个崩点" % (len(r["fails"]) - 3))
    nbad = sum(1 for r in rows if not r["robust"])
    print()
    print("依赖参数的结论：%d / %d" % (nbad, len(rows)))
    print("这些必须在论文里说明「选了哪个参数值、稳定域在哪」，")
    print("否则读者会把「依赖参数的选择」读成「客观事实」。")
    return 0 if nbad == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
