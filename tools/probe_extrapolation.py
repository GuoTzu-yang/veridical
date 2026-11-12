"""外推荒谬性审计：线性模型稍一外推就预言不可能的取值吗？

用法：`python tools/probe_extrapolation.py [--json]`
退出码：0 = 没发现；1 = 有题目触发（不代表论文错，代表论文该声明边界）。

判据与 `falsify.limit_behavior` 的 y_sign / x_sign 分支一致：
  ① 观测到的 y 全部同号；
  ② 把 x 推到观测范围外 3 步，但**仍落在自变量可行的半轴内**；
  ③ 线性预测反号（穿过零点）。
第 ② 条是第 95 轮补的：不加它，23 道题里 11 道会报，大半是
「服务台数 = -10」这种自变量先失效的情形，报出来没有意义。

这个检查**没有接进 gate**：接进去会让 7 道题变红，而那 7 道题缺的是
论文里一句「本模型只在观测区间内有效」。先把结论量清楚，再决定怎么改。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402

import falsify  # noqa: E402
import gate  # noqa: E402
import mm  # noqa: E402


def main():
    cfg = json.load(open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
    hit, miss, skipped = [], [], []
    for name, it in cfg.items():
        d = os.path.join(HERE, it["out"])
        fz = os.path.join(d, "冻结数字.json")
        if not os.path.exists(fz):
            skipped.append((name, "无冻结表"))
            continue
        data, _why = gate._resolve_data(d)
        if not data:
            skipped.append((name, "无数据表"))
            continue
        fd = json.load(open(fz, encoding="utf-8"))
        ds = mm.DS(data)
        y = gate._pick_col(ds, fd.get("y"))
        xs = [c for c in (gate._pick_col(ds, v) for v in (fd.get("x") or []))
              if c and c != y]
        if not y or not xs:
            skipped.append((name, "冻结表无可用 y/x"))
            continue
        yv = np.asarray(ds.col(y), dtype=float)
        yv = yv[~np.isnan(yv)]
        if len(yv) < 5:
            skipped.append((name, "样本不足"))
            continue
        sign = 1 if (yv > 0).all() else (-1 if (yv < 0).all() else 0)
        if sign == 0:
            skipped.append((name, "y 有正有负，零穿越判据不适用"))
            continue
        flagged = []
        yall = np.asarray(ds.col(y), dtype=float)
        for x in xs:
            xv = np.asarray(ds.col(x), dtype=float)
            if len(xv) < 5 or xv.std() == 0:
                continue
            fit = falsify.fit_centered(xv, yall)
            xsign = 1 if (xv > 0).all() else (-1 if (xv < 0).all() else 0)
            r = falsify.limit_behavior(
                coef=fit["coef"], intercept=fit["intercept"],
                xmean=fit["xmean"], xstd=fit["xstd"],
                xs_min=fit["xs_min"], xs_max=fit["xs_max"],
                y_sign=sign, x_sign=(xsign or None))
            if not r["ok"]:
                flagged.append((x, r["issues"][0][:60]))
        (hit if flagged else miss).append((name, flagged))

    print("会触发「外推穿零」的题：%d" % len(hit))
    for n, f in hit:
        print("  %-18s %s" % (n, f[0][1] if f else ""))
    print()
    print("不触发：%d  跳过：%d" % (len(miss), len(skipped)))
    for n, why in skipped:
        print("  skip %-18s %s" % (n, why))
    print()
    if hit:
        print("提示：这些题不自相矛盾，缺的是论文里一句「本模型只在观测区间内有效」。")
        print("      gate 尚未接入这条判据 —— 接进去会让上面 %d 道变红。" % len(hit))
    if "--json" in sys.argv:
        print(json.dumps(
            dict(hit=[{"problem": n,
                       "x": f[0][0] if f else None,
                       "detail": f[0][1] if f else None} for n, f in hit],
                 n_miss=len(miss), n_skip=len(skipped)),
            ensure_ascii=False, indent=2))
    return 1 if hit else 0


if __name__ == "__main__":
    sys.exit(main())
