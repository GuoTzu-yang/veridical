"""给 freeze.check_paper 打两个补丁（第 114 轮，种子缺陷基准逼出来的）。

问题（实测）
------------
给已有论文植入一个不存在的数（0.847192），`numbers` 仍然 PASS。原因有两个：

1. **10% 阈值看不见单点缺陷**：一个假数占 234 个 token 的 0.4%，永远撞不穿阈值。
   阈值原本是为了容忍版面常数，但「一个论文声称可溯源」与「允许 10% 没出处」
   是两件事，前者不该有豁免额度。
2. **2% 相对容差让编造数躲进邻域**：`_close(a,b,0.02)` 意味着任何与真实值相差
   2% 以内的数都被判为「溯源成功」。真实测量值是 6~8 位有效数字，
   2% 的邻域足够藏一个假数。

补丁
----
① 高精度值（小数位 >= 4）用**绝对**容差 1e-4 比，不再用 2% 相对容差。
② 只要存在**一个**未被溯源的高精度值，就判 FAIL，并把那个数点名。
   理由写进 note：声明可溯源就等于承诺「没有无出处的计算值」。
"""
import io

P = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch\freeze.py"
s = io.open(P, encoding="utf-8").read()

# ── ① 收紧容差：高精度值走绝对容差 ────────────────────────────────
old_close = '''def _close(a: float, b: float, rel: float = 0.02) -> bool:
    if a == b:
        return True
    d = max(abs(a), abs(b))
    return d > 0 and abs(a - b) / d <= rel'''
new_close = '''def _close(a: float, b: float, rel: float = 0.02) -> bool:
    """两个数是否「同一个值」。

    第 114 轮的修正：原来只有 2% 相对容差，于是任何与真实值相差 2% 以内的
    编造数都被判为溯源成功 —— 而真实测量值有 6~8 位有效数字，2% 的邻域
    足够藏一个假数。现在：
      · 幅度大（>=1）→ 相对容差 1e-4（四位小数以内算同一个数）
      · 幅度小（<1） → 绝对容差 1e-6
    仍然保留 rel 参数，供「百分比 vs 小数」这类跨量纲比较显式放宽。
    """
    if a == b:
        return True
    if rel != 0.02:                     # 调用方显式放宽时按原语义
        d = max(abs(a), abs(b))
        return d > 0 and abs(a - b) / d <= rel
    if max(abs(a), abs(b)) >= 1:
        return abs(a - b) <= 1e-4
    return abs(a - b) <= 1e-6'''
assert old_close in s, "_close 未匹配"
s = s.replace(old_close, new_close, 1)

# ── ② 单点高精度未溯源 → 直接 FAIL ────────────────────────────────
old_ret = '''    n = len(uniq)
    ratio = (len(untraced) / n) if n else 0.0
    return dict(
        ok=(len(traced) >= min(must, n)) and ratio <= max_untraced,'''
new_ret = '''    n = len(uniq)
    ratio = (len(untraced) / n) if n else 0.0
    # 第 114 轮：单点检测。一个高精度（>=4 位小数）的未溯源值，
    # 就是「有一个计算值没有出处」，不该被 10% 的额度吸收。
    _hp = [v for v in untraced
           if len(str(abs(v)).split(".")[-1].rstrip("0")) >= 3]
    _hp_bad = bool(_hp)
    return dict(
        ok=(len(traced) >= min(must, n)) and ratio <= max_untraced
           and not _hp_bad,
        high_precision_untraced=_hp[:5],
        high_precision_bad=_hp_bad,'''
assert old_ret in s, "返回值未匹配"
s = s.replace(old_ret, new_ret, 1)

io.open(P, "w", encoding="utf-8", newline="\n").write(s)
print("freeze.py 两处补丁已打：容差收紧 + 单点检测")
