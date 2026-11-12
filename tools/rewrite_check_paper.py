"""重写 freeze.check_paper：按「书写精度」判，而不是按容差判（第 114 轮）。

为什么
------
原来用 2% 相对容差 → 编造的数只要靠近真实值就过关（种子缺陷基准抓到的漏洞）。
直接把容差收紧又会把**合法四舍五入**判成造假（表里 0.0074342，论文写 0.00743）。

正确规则只有一条：把冻结值**按论文书写的小数位数四舍五入**，再比。于是
  0.00743 vs 0.0074342  → round(0.0074342, 5) = 0.00743  ✓ 合法舍入
  0.847192 vs 任何真实值 → 需要某个冻结值正好等于 0.847192，几乎不可能  ✗
另外保留「单点高精度未溯源直接 FAIL」：声称可溯源就等于承诺没有无出处的计算值。
"""
import io
import re

P = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch\freeze.py"
s = io.open(P, encoding="utf-8").read()

i = s.index("def check_paper(")
j = s.index("\ndef ", i + 10)

new = '''def _decimals(tok: str) -> int:
    """书写的小数位数（"0.00743" -> 5；"59.18" -> 2）。"""
    if "." not in tok:
        return 0
    return len(tok.split(".")[1])


def _match_written(v: float, dec: int, frozen_vals) -> bool:
    """论文写的 v（保留 dec 位）是否是某个冻结值的合法写法。

    三个方向都试：原值、×100（百分比写法）、÷100（小数写法）。
    """
    tol = 0.5 * (10 ** -dec) + 1e-12
    for f in frozen_vals:
        for cand_v, cand_f in ((abs(v), abs(f)),
                               (abs(v), abs(f) * 100.0),
                               (abs(v), abs(f) / 100.0)):
            if abs(cand_v - cand_f) <= tol:
                return True
    return False


def check_paper(tex: str, frozen: dict, must: int = 3,
                max_untraced: float = 0.10) -> dict:
    """论文里的关键数，能不能在冻结表找到出处？

    判据（第 114 轮）：
      ① 每个候选值按其**书写精度**四舍五入后，必须等于某个冻结值
         （或它的百分比/小数写法）；
      ② 未溯源比例 <= max_untraced（容忍版面常数）；
      ③ **单点检测**：只要有一个 >=3 位小数的值未溯源，就判失败 ——
         这是种子缺陷基准逼出来的：10% 额度会吸收单个编造数。
    """
    # 先剥掉 LaTeX 的可选参数：\\includegraphics[width=0.68\\textwidth]
    _t = re.sub(r"\\[[^\\]]*\\]", " ", tex)
    toks = re.findall(r"(?<![\\w.])-?\\d+\\.\\d+(?![\\w.])", _t)
    pairs = []
    for tok in toks:
        try:
            v = float(tok)
        except ValueError:
            continue
        if abs(v) < 1e6:
            pairs.append((v, _decimals(tok)))
    # 同一个值可能以不同精度出现：按 (值, 精度) 去重
    seen = set()
    uniq = []
    for v, dec in pairs:
        key = (round(v, 6), dec)
        if key in seen:
            continue
        seen.add(key)
        uniq.append((v, dec))

    frozen_vals = [it["value"] for it in frozen.get("items", [])]
    traced, untraced = [], []
    for v, dec in uniq:
        if _match_written(v, dec, frozen_vals):
            traced.append(v)
        else:
            untraced.append((v, dec))

    n = len(uniq)
    ratio = (len(untraced) / n) if n else 0.0
    hp = [(v, d) for v, d in untraced if d >= 3]
    return dict(
        ok=(len(traced) >= min(must, n)) and ratio <= max_untraced and not hp,
        n_numbers=n, n_traced=len(traced),
        untraced_ratio=round(ratio, 4),
        untraced=[v for v, _d in untraced[:20]],
        high_precision_untraced=[v for v, _d in hp[:5]],
        high_precision_bad=bool(hp),
        note=("未溯源值要么是笔误，要么是手写常数；"
              "单点高精度未溯源一律判失败（声称可溯源就要做到）。"),
    )

'''

s = s[:i] + new + s[j + 1:]
io.open(P, "w", encoding="utf-8", newline="\n").write(s)
print("check_paper 已按书写精度重写")
