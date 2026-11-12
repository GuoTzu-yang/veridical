"""falsify.counterexamples 修 tie 缺陷：重尾重复值先聚合再判单调。

问题（第 86 轮实测）：
  queueing 的「服务台数」只有 5 个不同取值，共 24 行。滑窗按 x 排序后取
  连续 8 个点，窗口其实落在**同一取值的重复值内部**，量的是组内噪声，
  而不是沿 x 的反转。结果覆盖率算出 100%，看着像「处处违反」，
  实际是「窗口根本没跨过几个不同的 x」。

修法：
  1. 检测重尾 ties：不同取值数 < max(3, n/3) 时，先按 x 分组取 y 均值，
     在**组均值序列**上做滑窗（这才是「沿 x 的单调性」）。
  2. 聚合后 min_seg 自适应（至少 3，至多组数的一半），否则组数少时永远不成窗。
  3. 返回里如实报告 aggregated / n_groups / n_test，让调用方知道自己在看什么。
  4. 组数 < 3 时不下判断：ok=False 且 n_violating=0（与「样本不足」同一种诚实）。
"""
import io
import sys

P = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch\falsify.py"

OLD = '''    if len(pairs) < min_seg * 2:
        return dict(ok=False, why=f"样本不足（{len(pairs)} < {min_seg * 2}）",
                    n=len(pairs), segments=[], n_violating=0)
    pairs.sort(key=lambda p: p[0])
'''

NEW = '''    if len(pairs) < min_seg * 2:
        return dict(ok=False, why=f"样本不足（{len(pairs)} < {min_seg * 2}）",
                    n=len(pairs), segments=[], n_violating=0,
                    aggregated=False, n_groups=len({p[0] for p in pairs}),
                    n_test=len(pairs))
    pairs.sort(key=lambda p: p[0])

    # ── 重尾 ties：先聚合再判单调 ──────────────────────────────────
    # 滑窗按 x 排序取连续点。若 x 只有少数几个不同取值（例如「服务台数」
    # 只有 1..5，共 24 行），窗口会落在同一取值的重复值内部，量的是组内
    # 噪声而不是沿 x 的方向。实测 queueing 因此算出「100% 覆盖」的假象。
    _distinct = len({p[0] for p in pairs})
    _aggregated = False
    if _distinct < max(3, len(pairs) // 3):
        _groups = {}
        for a, b in pairs:
            _groups.setdefault(a, []).append(b)
        pairs = sorted((a, sum(v) / len(v)) for a, v in _groups.items())
        _aggregated = True
        # 组数少时必须放宽窗口，否则永远凑不满
        min_seg = max(3, min(min_seg, len(pairs) // 2))
        if len(pairs) < 3:
            return dict(ok=False,
                        why=f"x 只有 {len(pairs)} 个不同取值，无法判单调",
                        n=len(pairs), segments=[], n_violating=0,
                        aggregated=True, n_groups=_distinct,
                        n_test=len(pairs))
'''

OLD_RET = '''    merged = _merge(segments)
    return dict(ok=not merged, n=len(pairs),
                n_violating=len(merged),'''

NEW_RET = '''    merged = _merge(segments)
    return dict(ok=not merged, n=len(pairs),
                aggregated=_aggregated, n_groups=_distinct,
                n_test=len(pairs),
                n_violating=len(merged),'''


def main():
    src = io.open(P, encoding="utf-8").read()
    orig = src
    for name, old, new in (("tie 聚合", OLD, NEW), ("返回值", OLD_RET, NEW_RET)):
        if old not in src:
            print("FAIL: %s 锚点未命中" % name)
            return 2
        src = src.replace(old, new, 1)
        print("OK %s" % name)
    if src == orig:
        print("NO CHANGE")
        return 0
    io.open(P, "w", encoding="utf-8", newline="\n").write(src)
    print("written %s" % P)
    return 0


if __name__ == "__main__":
    sys.exit(main())
