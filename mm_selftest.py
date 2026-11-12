"""mm.py 的自检（第 109 轮新增）。

mm.py 是计算内核 —— 整条流水线最底层、被引用最多的模块，
但它一直没有自检（46 个带自检的模块里没有它）。这里先覆盖
第 109 轮统一的时间轴/标识列判据，以及几个不该退化的基本不变量。

新增判据要同时防两种错：
  · 过度触发：把「等待时间」（分钟）、「1950」（按年份分箱的列名）当时间轴；
  · 不足触发：认不出「年份/月份/年度」这些真时间轴。
"""
import os
import sys
import tempfile

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import mm  # noqa: E402

_bad = [0]
_n = [0]


def ck(name, cond, detail=""):
    _n[0] += 1
    if not cond:
        _bad[0] += 1
        print(f"  [FAIL] {name}" + (f"  — {detail}" if detail else ""))
    else:
        print(f"  [PASS] {name}" + (f"  — {detail}" if detail else ""))


def _mk(cols):
    tmp = tempfile.mkdtemp(prefix="mmst_")
    p = os.path.join(tmp, "t.xlsx")
    pd.DataFrame(cols).to_excel(p, index=False)
    return mm.DS(p)


def selftest() -> int:
    rng = np.random.default_rng(11)

    # ── 时间轴：名字 + 取值都要像 ──
    ds_year = _mk({"年份": np.arange(1990, 2030),
                   "人口": rng.normal(1000, 50, 40)})
    ck("年份（一行一年）→ 判为时间轴",
       mm.time_axis_cols(ds_year) == ["年份"],
       str(mm.time_axis_cols(ds_year)))

    ds_month = _mk({"月份": np.arange(1, 41),
                    "销量": rng.normal(100, 5, 40)})
    ck("月份（一行一期）→ 判为时间轴",
       "月份" in mm.time_axis_cols(ds_month),
       str(mm.time_axis_cols(ds_month)))

    # 测量时长不是轴：名字含时间，但取值是量级（有重复、非等距序号）
    ds_wait = _mk({"等待时间": rng.gamma(2.0, 3.0, 60),
                   "服务台数": rng.integers(1, 6, 60)})
    ck("等待时间（测量值）→ 不是时间轴",
       mm.time_axis_cols(ds_wait) == [],
       str(mm.time_axis_cols(ds_wait)))
    ck("测量词被 is_time_axis_name 挡掉",
       mm.is_time_axis_name("等待时间") is False)

    # 年份分箱列：列名像年份，但列里装的是人口（量级，非等距）
    ds_bin = _mk({"1950": rng.normal(1e7, 1e6, 40),
                  "2005": rng.normal(1.2e7, 1e6, 40)})
    ck("按年份分箱的列（列名 1950/2005）→ 不是时间轴",
       mm.time_axis_cols(ds_bin) == [],
       str(mm.time_axis_cols(ds_bin)))
    ck("is_time_like 仍认为 1950 像时间（旧口径保留）",
       mm.is_time_like("1950") is True)

    # ── 标识列：与时间轴分开 ──
    ds_id = _mk({"方案编号": np.arange(1, 41),
                 "成本": rng.normal(100, 10, 40),
                 "得分": rng.normal(50, 5, 40)})
    ck("方案编号 → 判为标识列",
       mm.row_index_cols(ds_id) == ["方案编号"],
       str(mm.row_index_cols(ds_id)))
    ck("标识列不混进时间轴",
       mm.time_axis_cols(ds_id) == [], str(mm.time_axis_cols(ds_id)))
    _nr = dict(mm.non_response_cols(ds_id))
    ck("non_response_cols 给出类型标签", _nr.get("方案编号") == "id", str(_nr))

    # ── 基本不变量（防退化） ──
    ck("pick 认显示名（子串）", ds_id.pick(["成本"]) == ["成本"])
    try:
        ds_id.pick(["不存在的列"])
        ck("pick 匹配不到时抛错", False, "没抛错")
    except KeyError as e:
        ck("pick 匹配不到时抛错", "匹配不到列" in str(e), str(e)[:50])

    # suspect_leak 的阈值与分类
    ds_leak = _mk({"年份": np.arange(1, 41),
                   "响应": np.arange(1, 41) * 2.0 + 0.01})
    _sl = mm.suspect_leak(ds_leak, "响应", ["年份"])
    ck("suspect_leak 能抓到与年份近共线的列",
       bool(_sl) and _sl[0][0] == "年份", str(_sl)[:70])

    print()
    print(f"{'ALL PASS' if _bad[0] == 0 else 'FAILED'}  "
          f"{_n[0] - _bad[0]}/{_n[0]}")
    return 0 if _bad[0] == 0 else 1


if __name__ == "__main__":
    sys.exit(selftest())
