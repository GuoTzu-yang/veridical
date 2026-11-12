"""advise 的自检（第 106 轮新增）。

原来 advise.py **没有任何自检** —— 它是「定题」这条命令的实现，
是整条流水线最前面的一步，却不在 46 个带自检模块里。

要点：
  · optimize 分支以前不可达（只有 forecast/explain/evaluate/unclear 四个赋值）
  · 单标签表达不了混合题（题库自己的 题型.json 就是多标签）
  · 目标名给的是论文显示名，要用 ds.pick 解析
"""
import os
import sys
import tempfile

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import advise  # noqa: E402
import mm  # noqa: E402


def _ck(bad, n, name, cond, detail=""):
    n[0] += 1
    if not cond:
        bad[0] += 1
        print(f"  [FAIL] {name}" + (f"  — {detail}" if detail else ""))
    else:
        print(f"  [PASS] {name}" + (f"  — {detail}" if detail else ""))


def _mk(cols: dict, rows: int = 40):
    tmp = tempfile.mkdtemp(prefix="adv_")
    p = os.path.join(tmp, "t.xlsx")
    df = pd.DataFrame(cols)
    df.to_excel(p, index=False)
    return mm.DS(p)


def selftest() -> int:
    bad = [0]
    n = [0]
    rng = np.random.default_rng(7)

    # ① 解释型：给了 y 和 x
    ds = _mk({"响应": rng.normal(10, 1, 40) + np.arange(40) * 0.1,
              "因子A": rng.normal(0, 1, 40),
              "因子B": rng.normal(0, 1, 40),
              "目标": rng.normal(5, 1, 40)})
    r = advise.diagnose(ds, "响应", ["因子A"])
    _ck(bad, n, "给了 y 和 x → 主标签 explain",
        r["kind"] == "explain", r["kind"])
    _ck(bad, n, "没带目标列时不报 optimize",
        "optimize" not in (r.get("kinds") or []),
        str(r.get("kinds")))

    # ② 带目标列 → 追加 optimize，且目标被解析成真实列名
    r2 = advise.diagnose(ds, "响应", ["因子A"], objectives=["目标"])
    _ck(bad, n, "带目标列 → kinds 追加 optimize",
        "optimize" in (r2.get("kinds") or []), str(r2.get("kinds")))
    _ck(bad, n, "optimize 分支可达（以前永远选不到）",
        r2["kind"] == "explain" and r2["kinds"][-1] == "optimize",
        str(r2["kinds"]))
    _ck(bad, n, "目标列被解析成数据里的真实列名",
        r2.get("objectives") == ["目标"], str(r2.get("objectives")))
    _ck(bad, n, "带目标时给出 solve/pareto 方法链",
        any("solve" in c for c in r2["chains"])
        and any("pareto" in c for c in r2["chains"]))

    # ③ 目标名给的是显示名（数据里没有这一列）→ 解析不到就不硬塞
    r3 = advise.diagnose(ds, "响应", ["因子A"], objectives=["根本不存在的列"])
    _ck(bad, n, "解析不到的目标列不硬塞进 kinds",
        "optimize" not in (r3.get("kinds") or []), str(r3.get("kinds")))

    # ④ 不给 y、给多个指标 → 评价型
    r4 = advise.diagnose(ds, None, [])
    _ck(bad, n, "不给 y → 评价型 evaluate",
        r4["kind"] == "evaluate", r4["kind"])

    # ⑤ 时间轴 → forecast
    # 注意：列名要用 time_cols 认得的词（「时间/时刻/时点…」）。
    # mm.is_time_like 认得更宽（年份/月份/年度…），但 time_cols 更严 ——
    # 这两套判据在真实数据上并不等价（第 106 轮量过：8 道题的列被
    # is_time_like 判成时间轴，其中 等待时间/停留时间 是测量值、
    # 1950/2005 是按年份分箱的列，都不是时间轴）。这里按现状取样，
    # 免得把「尚未统一」这件事藏进测试里。
    ds2 = _mk({"时间": np.arange(1, 41),
               "销量": rng.normal(100, 5, 40) + np.arange(40)})
    r5 = advise.diagnose(ds2, "销量", [])
    _ck(bad, n, "有时间轴列 → 主标签 forecast",
        r5["kind"] == "forecast", r5["kind"])

    # ⑥ 信息不足
    ds3 = _mk({"唯一一列": rng.normal(0, 1, 40)})
    r6 = advise.diagnose(ds3, None, [])
    _ck(bad, n, "信息不足 → unclear",
        r6["kind"] == "unclear", r6["kind"])

    # ⑦ kinds 一定包含 kind（老调用方只读 kind，不能被破坏）
    for _r in (r, r2, r4, r5, r6):
        _ck(bad, n, "kinds 必含 kind（向后兼容）",
            _r["kind"] in (_r.get("kinds") or []),
            f"{_r['kind']} vs {_r.get('kinds')}")

    # ⑧ 题面线索（第 107 轮）：network/simulation 这些只看数据认不出来
    r7 = advise.diagnose(ds, "响应", ["因子A"], objectives=["目标"],
                          statement="transport network flow under capacity limits")
    _ck(bad, n, "题面里的 network 线索被认出来",
        "network" in (r7.get("kinds") or []), str(r7.get("kinds")))
    r8 = advise.diagnose(ds, "响应", ["因子A"], objectives=["目标"],
                          statement="monte carlo simulation of queue length")
    _ck(bad, n, "题面里的 simulation 线索被认出来",
        "simulation" in (r8.get("kinds") or []), str(r8.get("kinds")))
    r9 = advise.diagnose(ds, "响应", ["因子A"], objectives=["目标"],
                          statement="production planning with conflicting objectives")
    _ck(bad, n, "题面里的 multiobjective 线索被认出来",
        "multiobjective" in (r9.get("kinds") or []), str(r9.get("kinds")))
    _ck(bad, n, "题面线索也留下依据（可复核）",
        any("题面" in e for e in r7.get("evidence") or []),
        str(r7.get("evidence"))[:90])
    r10 = advise.diagnose(ds, "响应", ["因子A"], objectives=["目标"])
    _ck(bad, n, "没给题面时不硬编题型",
        len(r10.get("kinds") or []) <= 2, str(r10.get("kinds")))

    # ⑨ 显式声明的题型（第 108 轮）：LLM 读完题面最清楚，插件是能力层
    r11 = advise.diagnose(ds, "响应", ["因子A"], objectives=["目标"],
                          declared_kinds=["network", "mechanism"])
    _ck(bad, n, "显式声明的题型进入 kinds",
        "network" in (r11.get("kinds") or [])
        and "mechanism" in (r11.get("kinds") or []), str(r11.get("kinds")))
    _ck(bad, n, "显式声明也有依据（可复核）",
        any("--types" in e for e in r11.get("evidence") or []),
        str(r11.get("evidence"))[:100])
    _ck(bad, n, "显式声明的题型也带方法链",
        any("graph" in c for c in r11.get("chains") or []),
        str(r11.get("chains"))[:120])
    r12 = advise.diagnose(ds, "响应", ["因子A"], objectives=["目标"],
                          declared_kinds=["unclear"])
    _ck(bad, n, "声明 unclear 不会污染题型",
        "unclear" not in (r12.get("kinds") or []) or r12["kind"] == "unclear",
        str(r12.get("kinds")))

    print(f"\n{'ALL PASS' if bad[0] == 0 else 'FAILED'}  {n[0] - bad[0]}/{n[0]}")
    return 0 if bad[0] == 0 else 1


if __name__ == "__main__":
    sys.exit(selftest())
