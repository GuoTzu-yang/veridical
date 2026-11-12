"""TOPSIS 综合评价（含熵权法与权重敏感性）。

为什么要它
----------
APMCM 的 C 类是数据/评价题，TOPSIS 几乎是最常被用到的排名方法；`mmkit` 现在
只有 AHP / 熵权 / 灰色关联 / 模糊综合，缺 TOPSIS，是评价类里最显眼的缺口。

实现要点
--------
标准流程：向量归一化 -> 加权 -> 正/负理想解 -> 欧氏距离 -> 贴近度。
指标方向（benefit / cost）决定理想解取 max 还是 min，这一步写错会让排名整体反转，
所以单独用参数显式给出，不猜。

权重两种来源：
  · 给定权重
  · 熵权法自动算（也用于检查给定权重是否离谱）

敏感性：把每个权重按 ±ratio 扰动，看第一名是否改变，回答「排名稳不稳」。

用法
    python tools/topsis.py --data X.xlsx --cols 质量,成本,交付期 \
           --dirs benefit,cost,benefit --weights 0.5,0.3,0.2
    python tools/topsis.py selftest
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(path):
    import pandas as pd
    if path.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(path)
    return pd.read_csv(path)


def entropy_weights(X):
    """熵权法。X 先按列 min-max 到 [0,1] 并保证非负。"""
    m, n = X.shape
    P = X - X.min(axis=0)
    rng = P.max(axis=0)
    # np.where 会先算两边，rng=0 时 P/rng 触发除零警告；用 divide 的 where 参数
    P = np.divide(P, rng, out=np.ones_like(P), where=rng > 0)
    P = P + 1e-12
    P = P / P.sum(axis=0, keepdims=True)
    e = -(P * np.log(P)).sum(axis=0) / np.log(m)
    d = 1.0 - e
    if d.sum() <= 0:
        return np.full(n, 1.0 / n)
    return d / d.sum()


def topsis(X, w, dirs, ratio=0.2):
    """返回 dict：normalised、weighted、ideal、closeness、rank、sensitivity。"""
    m, n = X.shape
    norm = np.sqrt((X ** 2).sum(axis=0))
    norm = np.where(norm > 0, norm, 1.0)
    R = X / norm
    V = R * w

    vp = np.empty(n)
    vn = np.empty(n)
    for j in range(n):
        if dirs[j] == "benefit":
            vp[j], vn[j] = V[:, j].max(), V[:, j].min()
        else:                                    # cost：越小越好
            vp[j], vn[j] = V[:, j].min(), V[:, j].max()

    dp = np.sqrt(((V - vp) ** 2).sum(axis=1))
    dn = np.sqrt(((V - vn) ** 2).sum(axis=1))
    denom = dp + dn
    C = np.where(denom > 0, dn / denom, 0.5)

    order = np.argsort(-C)
    rank = np.empty(m, dtype=int)
    rank[order] = np.arange(1, m + 1)

    # 敏感性：逐个权重 ±ratio 扰动，看第一名是否换人
    base_first = int(order[0])
    flips = []
    for j in range(n):
        for sgn in (+1, -1):
            w2 = w.copy()
            w2[j] = max(1e-9, w2[j] * (1 + sgn * ratio))
            w2 = w2 / w2.sum()
            V2 = R * w2
            vp2 = np.array([V2[:, k].max() if dirs[k] == "benefit" else V2[:, k].min()
                            for k in range(n)])
            vn2 = np.array([V2[:, k].min() if dirs[k] == "benefit" else V2[:, k].max()
                            for k in range(n)])
            dp2 = np.sqrt(((V2 - vp2) ** 2).sum(axis=1))
            dn2 = np.sqrt(((V2 - vn2) ** 2).sum(axis=1))
            C2 = dn2 / (dp2 + dn2)
            if int(np.argmax(C2)) != base_first:
                flips.append(dict(column=j, sign="+" if sgn > 0 else "-",
                                  new_first=int(np.argmax(C2))))
    return dict(R=R, V=V, ideal_pos=vp, ideal_neg=vn, d_pos=dp, d_neg=dn,
                closeness=C, rank=rank, base_first=base_first,
                sensitivity_flips=flips,
                first_stable=(len(flips) == 0))


def report(X, cols, dirs, w, names, ratio=0.2, weights_given=True):
    r = topsis(X, w, dirs, ratio)
    w_ent = entropy_weights(X)
    print("TOPSIS 综合评价")
    print("  方案 %d × 指标 %d" % X.shape)
    print()
    if weights_given:
        print("  权重：给定 %s" % np.round(w, 4).tolist())
        print("        熵权 %s（对照）" % np.round(w_ent, 4).tolist())
    else:
        print("  权重：熵权法 %s" % np.round(w, 4).tolist())
    print()
    print("  %-14s %-10s %-10s %-8s" % ("方案", "d+", "d-", "贴近度 C"))
    order = np.argsort(-r["closeness"])
    for i in order:
        nm = names[i] if names is not None else "row%d" % i
        print("  %-14s %-10.4f %-10.4f %-8.4f  排名 %d"
              % (nm, r["d_pos"][i], r["d_neg"][i], r["closeness"][i], r["rank"][i]))
    print()
    print("  第一名稳健性（各权重 ±%.0f%% 扰动）：%s"
          % (ratio * 100, "稳定" if r["first_stable"] else "会变"))
    if r["sensitivity_flips"]:
        for f in r["sensitivity_flips"]:
            print("    · 指标 %s 权重%s 扰动 -> 第一名换成第 %d 行"
                  % (cols[f["column"]], f["sign"], f["new_first"] + 1))
    return r


def selftest():
    ok = True

    def ck(name, cond, detail=""):
        nonlocal ok
        ok = ok and cond
        print("  [%s] %s %s" % ("PASS" if cond else "FAIL", name, detail))

    # 手工算例：3 方案 × 2 指标（都是 benefit），等权
    X = np.array([[1.0, 2.0], [2.0, 1.0], [3.0, 3.0]])
    r = topsis(X, np.array([0.5, 0.5]), ["benefit", "benefit"])
    # 第三个方案两项都最高，应排第一
    ck("支配方案排第一", int(np.argmax(r["closeness"])) == 2,
       "C=%s" % np.round(r["closeness"], 4).tolist())
    ck("贴近度在 [0,1]", bool(((r["closeness"] >= 0) & (r["closeness"] <= 1)).all()))

    # cost 方向：把第二列改成 cost，最小的方案该在那一列占优
    r2 = topsis(X, np.array([0.5, 0.5]), ["benefit", "cost"])
    ck("cost 方向改变理想解", not np.allclose(r["ideal_pos"], r2["ideal_pos"]))

    # 熵权：若某列全相同，其熵权应接近 0
    X3 = np.array([[1.0, 5.0], [2.0, 5.0], [3.0, 5.0]])
    w3 = entropy_weights(X3)
    ck("常数列熵权≈0", w3[1] < 1e-6, "w=%s" % np.round(w3, 6).tolist())

    # 敏感性：权重全部给第一列时第一名应与只有第一列时一致
    r4 = topsis(X, np.array([0.999, 0.001]), ["benefit", "benefit"])
    ck("权重集中时由主导列决定",
       int(np.argmax(r4["closeness"])) == int(np.argmax(X[:, 0])),
       "first=%d" % int(np.argmax(r4["closeness"])))

    print("\n%s" % ("ALL PASS" if ok else "FAILED"))
    return 0 if ok else 1


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] == "selftest":
        return selftest()
    ap = argparse.ArgumentParser(description="TOPSIS 综合评价")
    ap.add_argument("--data", required=True)
    ap.add_argument("--cols", required=True, help="指标列名，逗号分隔")
    ap.add_argument("--dirs", default="", help="benefit/cost，逗号分隔；省略视为全 benefit")
    ap.add_argument("--weights", default="", help="权重，逗号分隔；省略用熵权")
    ap.add_argument("--name-col", default="", help="方案名列；省略用行号")
    ap.add_argument("--ratio", type=float, default=0.2)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    df = load(a.data)
    cols = [c.strip() for c in a.cols.split(",") if c.strip()]
    missing = [c for c in cols if c not in df.columns]
    if missing:
        print("列不存在：%s" % missing)
        print("可用列：%s" % list(df.columns))
        return 2
    X = df[cols].to_numpy(float)
    dirs = [d.strip() for d in a.dirs.split(",") if d.strip()] or ["benefit"] * len(cols)
    if len(dirs) != len(cols):
        print("--dirs 个数与 --cols 不一致")
        return 2
    if any(d not in ("benefit", "cost") for d in dirs):
        print("--dirs 只能是 benefit / cost")
        return 2
    if a.weights:
        w = np.array([float(x) for x in a.weights.split(",")])
        if len(w) != len(cols):
            print("--weights 个数与 --cols 不一致")
            return 2
        w = w / w.sum()
    else:
        w = entropy_weights(X)
    names = df[a.name_col].tolist() if a.name_col else None

    if a.json:
        r = topsis(X, w, dirs, a.ratio)
        print(json.dumps(dict(
            weights=w.tolist(),
            entropy_weights=entropy_weights(X).tolist(),
            closeness=r["closeness"].tolist(),
            rank=r["rank"].tolist(),
            first_stable=r["first_stable"],
        ), ensure_ascii=False, indent=2))
        return 0
    report(X, cols, dirs, w, names, a.ratio,
           weights_given=bool(a.weights))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
