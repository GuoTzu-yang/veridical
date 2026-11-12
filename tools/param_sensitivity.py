#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""param_sensitivity.py —— 判据参数有多敏感：扫一遍，看结论变不变。

背景（第 123 轮，用户问「把门设成固有绝对正确的参数，或者公式拟合？」）：

判据里 5 个参数，只有 1 个是**数学定理**：
  · `tol = 0.5 * 10^-dec`      舍入误差上界，不是选择（已做到）
  · `max_untraced = 10%`       风险偏好
  · 单点规则 `d >= 3`          设计选择
  · `|v| <= 1000`（A_struct）  经验界
  · `must >= 3`                设计选择

后四个**没有绝对正确值**。硬说某值绝对正确，就是把设计选择伪装成事实。
「公式拟合」更不行：拟合是让判据适应数据（把异常当噪声最小化），
而围栏是让数据被判据拦住 —— 方向相反。且这里没有标注数据，
拟合出来的只是「我一个人判断的近似」。

**唯一正当的用法是反过来**：拿数据**检验**参数，看结论对参数敏不敏感。
本工具就做这件事：扫参数，报告「结论在哪一段取值内不变」。

用法：
    python tools/param_sensitivity.py
    python tools/param_sensitivity.py --json
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

OUT = os.path.join(HERE, "out", "final")


def _load():
    import freeze
    import untraced as U
    tex = io.open(os.path.join(OUT, "paper.tex"), encoding="utf-8",
                  errors="replace").read()
    fz = json.load(io.open(os.path.join(OUT, "冻结数字.json"),
                          encoding="utf-8"))
    dv = U.data_values_of(U.find_data_file(OUT))
    return freeze, tex, fz, dv


def scan_untraced():
    """扫 max_untraced：结论（ok）在哪一段取值内不变。

    字段名注意：`check_paper` 返回的是 `n_numbers` / `untraced`，
    **不是 `n`** —— 第 123 轮踩过：读 `r.get("n")` 得到 0，
    于是整张表打印 n=0，被误读成「没有候选数」。
    """
    freeze, tex, fz, dv = _load()
    rows = []
    for t in (0.0, 0.005, 0.01, 0.02, 0.05, 0.10, 0.20, 0.50, 1.0):
        r = freeze.check_paper(tex, fz, max_untraced=t, single_point=True,
                               data_values=dv, strict_source=False)
        rows.append(dict(param=t, ok=bool(r["ok"]),
                         n_untraced=len(r["untraced"]),
                         n=r.get("n_numbers") or 0))
    stayed = len({r["ok"] for r in rows}) == 1
    return "max_untraced", rows, stayed


def scan_single_point():
    """扫单点规则的精度门槛 d>=k。"""
    freeze, tex, fz, dv = _load()
    rows = []
    for k in (1, 2, 3, 4, 5, 6):
        r = freeze.check_paper(tex, fz, max_untraced=1.0, single_point=True,
                               single_point_min_dec=k,
                               data_values=dv, strict_source=False)
        rows.append(dict(param=k, ok=bool(r["ok"]),
                         n_untraced=len(r["untraced"]),
                         n=r.get("n_numbers") or 0))
    stayed = len({r["ok"] for r in rows}) == 1
    return "单点规则 d>=k", rows, stayed


def scan_struct_limit():
    """扫 A_struct 的范围上界：看分类分布怎么变。"""
    import untraced as U
    tex = io.open(os.path.join(OUT, "paper.tex"), encoding="utf-8",
                  errors="replace").read()
    toks = [t for t, _ln in U.extract_tokens(tex)] if hasattr(U, "extract_tokens") else []
    if not toks:
        # 退回：用 verify 的分词器
        import verify
        toks = [t for t, _ln in verify.extract_numbers(tex, skip_meta=False)]
    rows = []
    for lim in (10, 50, 100, 500, 1000, 5000, 10000, 100000):
        from collections import Counter
        c = Counter(U.classify_token(t, struct_limit=lim) for t in toks)
        rows.append(dict(param=lim, A_struct=c.get("A_struct", 0),
                         D_computed=c.get("D_computed", 0),
                         E_data=c.get("E_data", 0), n=len(toks)))
    # 敏感 = A_struct 的占比在扫描区间里变化超过 5 个百分点
    pcts = [100.0 * r["A_struct"] / max(1, r["n"]) for r in rows]
    stayed = (max(pcts) - min(pcts)) <= 5.0
    return "A_struct 上界", rows, stayed


SCANS = [scan_untraced, scan_single_point, scan_struct_limit]


def main(argv):
    out = []
    for fn in SCANS:
        try:
            name, rows, stayed = fn()
            out.append(dict(name=name, rows=rows, stable=stayed))
        except Exception as e:                          # noqa: BLE001
            out.append(dict(name=fn.__name__, rows=[], stable=None,
                            error=str(e)))
    if "--json" in argv:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0

    print("判据参数敏感性：%d 个参数" % len(out))
    print()
    for o in out:
        print("── %s ──  %s" % (o["name"],
                              "结论对取值不敏感" if o["stable"]
                              else ("**一改就翻**" if o["stable"] is False
                                    else "无法判定")))
        if o.get("error"):
            print("   %s" % o["error"])
            continue
        for r in o["rows"]:
            kv = "  ".join("%s=%s" % (k, v) for k, v in r.items())
            print("   %s" % kv)
        print()
    nbad = sum(1 for o in out if o["stable"] is False)
    print("敏感（结论随参数变）：%d / %d" % (nbad, len(out)))
    print("说明：敏感不等于错。它说明「这个参数的选择会改变判决」，")
    print("      所以必须写进论文，并说明选了哪个值、代价是什么。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
