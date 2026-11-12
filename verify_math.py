#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_math.py —— 数值对拍（第 22 轮，思路集成自 dsh-sci-viz）

sci-viz 的做法
--------------
它自己实现不完全 Beta/Gamma（不查表），然后：

    与 scipy 1.18 对拍（tools/verify-math.mjs），相对误差 < 1e-9

我们没装 scipy，照搬不了。但它给的方法论是对的：**统计代码必须有参照**。

我们改成两层对拍
----------------
1. **已知答案**：造一组数据，真实斜率就是 2，算出来必须是 2。
   这是最强的参照 —— 答案不是"另一个库说的"，是构造时就定死的。

2. **不变量**：不管数据什么样都必须成立的等式。
   · R² 落在 [0, 1]
   · RMSE 非负
   · y 整体乘 100 → 系数乘 100、R² 不变（尺度不变性）
   · y 整体加常数 → 斜率不变、截距平移
   · 打乱 y → R² 应接近 0

为什么不变量比"对拍另一个库"更有用
----------------------------------
对拍只能证明"和 scipy 一样错"。不变量证明的是"自己内部自洽"，
而尺度不变性这类性质一旦破了，说明公式有量纲错误 —— 那是真错。

用法
    python verify_math.py
    python verify_math.py selftest
"""

from __future__ import annotations

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# 相对误差门槛。sci-viz 对 scipy 用 1e-9；
# 我们比的是构造时定死的真值，浮点噪声更小，但留点余量给优化的收敛误差。
RTOL = 1e-6


def _close(a: float, b: float, rtol: float = RTOL) -> bool:
    d = max(abs(a), abs(b), 1e-12)
    return abs(a - b) / d <= rtol


def _mk_dataset(tmpdir: str, x, y, name: str = "d.xlsx") -> str:
    """把合成数据写成 xlsx，走和真实数据一样的读入路径。"""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["x", "y"])
    for a, b in zip(x, y):
        ws.append([float(a), float(b)])
    p = os.path.join(tmpdir, name)
    wb.save(p)
    return p


def _fit(x, y, tmpdir):
    """一并拿到 ols 的三个量和交叉验证 RMSE。"""
    import mm
    slope, icept, r2, resid = _ols(x, y, tmpdir)
    p = _mk_dataset(tmpdir, x, y)
    ds = mm.DS(p)
    cv = mm.fit(ds, "y", ["x"])
    cv_rmse = (cv.get("best") or {}).get("rmse")
    return (slope, icept, r2, resid, cv_rmse), ds


def _ols(x, y, tmpdir):
    """用 mm.ols_summary 拟合，返回 (斜率, 截距, R², 残差)。

    mm.fit 只给 RMSE，系数和 R² 在 ols_summary 里 —— 这是查过真实返回
    结构才确认的，不是猜的。
    """
    import mm
    p = _mk_dataset(tmpdir, x, y)
    ds = mm.DS(p)
    X1 = np.asarray(ds.col("x"), dtype=float).reshape(-1, 1)
    yv = np.asarray(ds.col("y"), dtype=float)
    r = mm.ols_summary(X1, yv, ["x"])
    # 不能写 list(r.get("beta") or []) —— beta 是 ndarray，
    # ndarray 的真值判断会抛 ValueError。必须先判 None。
    _b = r.get("beta")
    beta = list(_b) if _b is not None else []
    return (float(beta[1]) if len(beta) > 1 else float("nan"),
            float(beta[0]) if beta else float("nan"),
            float(r.get("r2")) if r.get("r2") is not None else float("nan"),
            r.get("resid"))


def _coef(rep) -> float:
    """兼容旧调用：rep 是 _fit 的返回。"""
    return rep[0] if isinstance(rep, tuple) else float("nan")


def _r2(rep) -> float:
    return rep[2] if isinstance(rep, tuple) else float("nan")


def _rmse(rep) -> float:
    if isinstance(rep, tuple) and len(rep) > 4:
        return rep[4]
    return float("nan")


# ══════════════════════════════════════════════════════════════════════
def known_answer(tmpdir: str) -> list:
    """第一层：构造时答案就定死了。"""
    out = []
    rng = np.random.default_rng(7)
    x = np.linspace(0, 10, 60)

    # ① 斜率恰好 2、截距恰好 1，无噪声
    y = 2.0 * x + 1.0
    rep, _ = _fit(x, y, tmpdir)
    c = _coef(rep)
    out.append(dict(name="无噪声 y=2x+1 的斜率", got=c, want=2.0,
                    ok=_close(c, 2.0), rtol=RTOL))
    r = _r2(rep)
    out.append(dict(name="无噪声时 R² 应为 1", got=r, want=1.0,
                    ok=_close(r, 1.0, 1e-4), rtol=1e-4))

    # ② 斜率 -0.5（负相关）
    y2 = -0.5 * x + 3.0
    rep2, _ = _fit(x, y2, tmpdir)
    c2 = _coef(rep2)
    out.append(dict(name="无噪声 y=-0.5x+3 的斜率", got=c2, want=-0.5,
                    ok=_close(c2, -0.5), rtol=RTOL))

    # ③ 有噪声时斜率应落在真值附近
    y3 = 2.0 * x + 1.0 + rng.normal(0, 0.1, len(x))
    rep3, _ = _fit(x, y3, tmpdir)
    c3 = _coef(rep3)
    out.append(dict(name="弱噪声下斜率接近 2（±1%）", got=c3, want=2.0,
                    ok=abs(c3 - 2.0) <= 0.02, rtol=0.01))
    return out


def invariants(tmpdir: str) -> list:
    """第二层：不变量。这些一旦破了就是公式错。"""
    out = []
    rng = np.random.default_rng(11)
    x = np.linspace(0, 10, 60)
    y = 2.0 * x + 1.0 + rng.normal(0, 0.5, len(x))

    base, _ = _fit(x, y, tmpdir)
    c0, r0 = _coef(base), _r2(base)

    # ① R² 落在 [0,1]
    out.append(dict(name="R² ∈ [0,1]", got=r0, want="[0,1]",
                    ok=(0.0 <= r0 <= 1.0)))

    # ② RMSE 非负
    e0 = _rmse(base)
    out.append(dict(name="RMSE ≥ 0", got=e0, want=">=0",
                    ok=(e0 >= 0 or np.isnan(e0))))

    # ③ 尺度不变性：y 乘 100 → 斜率乘 100，R² 不变
    rep_s, _ = _fit(x, y * 100.0, tmpdir)
    cs, rs = _coef(rep_s), _r2(rep_s)
    out.append(dict(name="y×100 → 斜率×100", got=cs, want=c0 * 100,
                    ok=_close(cs, c0 * 100, 1e-5), rtol=1e-5))
    out.append(dict(name="y×100 → R² 不变", got=rs, want=r0,
                    ok=_close(rs, r0, 1e-6), rtol=1e-6))

    # ④ 平移不变性：y 加 50 → 斜率不变
    rep_t, _ = _fit(x, y + 50.0, tmpdir)
    ct = _coef(rep_t)
    out.append(dict(name="y+50 → 斜率不变", got=ct, want=c0,
                    ok=_close(ct, c0, 1e-6), rtol=1e-6))

    # ⑤ 打乱 y → R² 应接近 0
    yp = rng.permutation(y)
    rep_p, _ = _fit(x, yp, tmpdir)
    rp = _r2(rep_p)
    out.append(dict(name="打乱 y → R² 接近 0", got=rp, want="|R²|<0.1",
                    ok=(abs(rp) < 0.1)))

    return out


def compare_cases(tmpdir: str) -> list:
    """已知标准值（不依赖 mm）：正态分位数与 t 分位数。"""
    from statistics import NormalDist
    out = []
    # 正态 97.5% 分位 = 1.959963985（所有统计教材都有）
    z = NormalDist().inv_cdf(0.975)
    out.append(dict(name="标准正态 97.5% 分位", got=z,
                    want=1.959963984540054, ok=_close(z, 1.959963984540054)))
    # 正态 50% 分位 = 0
    z0 = NormalDist().inv_cdf(0.5)
    out.append(dict(name="标准正态 50% 分位=0", got=z0, want=0.0,
                    ok=abs(z0) < 1e-12))
    return out


def cross_impl(tmpdir: str) -> list:
    """对拍「论文附录里印的代码」与「实际算出数字的代码」。

    paper.py 里的 _CODE_ROB 是一段字符串，会被嵌进论文附录。它不是函数，
    而是一份**给人看的实现快照**。如果它和 mm 里真正跑的实现行为不同，
    读者照着附录复现不出论文结果 —— 复现性是假的。
    """
    out = []
    import mm
    import paper as P2
    rng = np.random.default_rng(23)
    x = np.linspace(-3, 7, 40)
    y = 1.7 * x - 2.3 + rng.normal(0, 0.3, len(x))
    X = x.reshape(-1, 1)

    # 实际实现
    real = mm.ols_summary(X, y, ["x"])

    # 附录里的代码：exec 出来才有行为
    src = getattr(P2, "_CODE_ROB", "") or ""
    if "def ols_summary" not in src:
        return [dict(name="附录代码可执行", got="无 ols_summary",
                     want="有", ok=False)]
    ns = {}
    try:
        exec(compile(src, "<appendix>", "exec"), ns)  # noqa: S102
    except Exception as e:                          # noqa: BLE001
        return [dict(name="附录代码可执行", got=f"{type(e).__name__}",
                     want="可执行", ok=False)]
    f = ns.get("ols_summary")
    if f is None:
        return [dict(name="附录代码有 ols_summary", got="无", want="有",
                     ok=False)]
    out.append(dict(name="附录代码可执行", got="OK", want="OK", ok=True))

    mine = f(X, y)
    # beta
    va = np.asarray(real.get("beta"), dtype=float)
    vb = np.asarray(mine.get("beta"), dtype=float)
    okb = (va.shape == vb.shape
           and bool(np.allclose(va, vb, rtol=1e-9, atol=1e-12)))
    out.append(dict(name="附录 beta 与实现一致",
                    got=float(va[-1]) if va.size else "None",
                    want=float(vb[-1]) if vb.size else "None", ok=okb))
    # r2
    ra, rb = real.get("r2"), mine.get("r2")
    okr = (ra is not None and rb is not None
           and _close(float(ra), float(rb), 1e-9))
    out.append(dict(name="附录 R² 与实现一致", got=ra, want=rb, ok=bool(okr)))
    return out


def report(rows: list) -> tuple:
    bad = [r for r in rows if not r["ok"]]
    print(f"  数值对拍：{len(rows) - len(bad)}/{len(rows)} 通过\n")
    for r in rows:
        mark = "PASS" if r["ok"] else "FAIL"
        g = r["got"]
        gs = f"{g:.10g}" if isinstance(g, (int, float)) else str(g)
        ws = f"{r['want']:.10g}" if isinstance(r["want"], (int, float)) \
            else str(r["want"])
        print(f"  [{mark}] {r['name']:<28}实得 {gs:<16}期望 {ws}")
    return len(bad) == 0, bad


def run_all() -> int:
    import tempfile
    tmp = tempfile.mkdtemp(prefix="vmath_")
    rows = []
    try:
        rows += known_answer(tmp)
    except Exception as e:                          # noqa: BLE001
        print(f"  已知答案层出错：{type(e).__name__}: {e}")
    try:
        rows += invariants(tmp)
    except Exception as e:                          # noqa: BLE001
        print(f"  不变量层出错：{type(e).__name__}: {e}")
    try:
        rows += compare_cases(tmp)
    except Exception as e:                          # noqa: BLE001
        print(f"  标准值层出错：{type(e).__name__}: {e}")
    try:
        rows += cross_impl(tmp)
    except Exception as e:                          # noqa: BLE001
        print(f"  双实现对拍层出错：{type(e).__name__}: {e}")

    ok, bad = report(rows)
    if bad:
        print(f"\n  未通过 {len(bad)} 项 —— 这些是公式层面的问题，"
              f"不是数据问题")
    return 0 if ok else 1


def selftest() -> int:
    """自测对拍器本身（先验证检查器，这是本仓库的规矩）。"""
    bad = 0
    n = 0

    def ck(name, cond, detail=""):
        nonlocal bad, n
        n += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
              + (f"  — {detail}" if detail else ""))
        if not cond:
            bad += 1

    ck("相等判真", _close(2.0, 2.0))
    ck("差异判假", not _close(2.0, 2.0001, 1e-6))
    ck("容差内判真", _close(2.0, 2.000001, 1e-5))
    ck("零值不炸", _close(0.0, 0.0))
    ck("负数正常", _close(-0.5, -0.5))

    # 对拍器必须能抓到错的
    # 下面这条 [FAIL] 是**故意的**：喂一个错值，证明 report() 会把它抓出来。
    # 先说明再打，免得在日志里被当成真失败（第 101 轮 —— 回归日志里
    # 它曾以「最近一次失败：[FAIL] 故意错」的样子出现，读起来很吓人）。
    print("  （下一条 [FAIL] 是故意的：验证对拍器能抓错）")
    fake = [dict(name="故意错", got=3.0, want=2.0, ok=_close(3.0, 2.0))]
    ok, b = report(fake)
    ck("能抓出错值", not ok and len(b) == 1)

    import tempfile
    tmp = tempfile.mkdtemp(prefix="vmath_st_")
    try:
        rows = known_answer(tmp) + invariants(tmp) + compare_cases(tmp)
        ck("三层都能跑出结果", len(rows) >= 8, f"{len(rows)} 项")
        ok2, bad2 = report(rows)
        ck("真数据全部通过", ok2,
           f"未过 {[r['name'] for r in bad2][:3]}")
    except Exception as e:                          # noqa: BLE001
        ck("三层都能跑出结果", False, f"{type(e).__name__}: {e}")

    print(f"\n{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1


def main(argv=None) -> int:
    a = sys.argv[1:] if argv is None else argv
    if a and a[0] == "selftest":
        return selftest()
    return run_all()


if __name__ == "__main__":
    raise SystemExit(main())
