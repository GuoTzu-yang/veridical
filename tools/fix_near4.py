import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "verify.py")
s = open(P, encoding="utf-8").read()
i = s.find("def _near(")
j = s.find("\ndef ", i + 10)
NEW = '''def _near(a: float, b: float) -> bool:
    """论文里的 a 能不能由输出里的 b 解释。

    两条一起用：

    ① 精度差 <= 2 位
       论文写 0.0074342（7 位）、输出只有 0.00743（5 位），差 2 位，允许。
       论文写 0.9999（4 位）、输出是 1.0（1 位），差 3 位，不允许 ——
       1.0 的舍入区间是 [0.95, 1.05)，任何数都能挂上去，编一个就溜了。
       实测漏抓过。

    ② 高位必须是低位的舍入
       0.0074342 与 0.00743  -> round(0.0074342, 5) == 0.00743   ✓
       0.9999   与 0.9975    -> round(0.9975, 4)    != 0.9999    ✗
       都是 4 位、差 0.24%，那是改数，不是舍入。

    百分比换算（0.5918 与 59.18）先做 scale 再走同一条判据。
    """
    if a == b:
        return True

    da, db = _decimals(a), _decimals(b)

    def _ok(x: float, y: float, dx: int, dy: int) -> bool:
        if abs(dx - dy) > 2:
            return False
        hi, lo, dlo = (x, y, dy) if dx >= dy else (y, x, dx)
        try:
            return abs(round(hi, dlo) - lo) <= 1e-12
        except (ValueError, OverflowError):
            return False

    if _ok(a, b, da, db):
        return True
    for scale in (100.0, 0.01):
        bs = b * scale
        if _ok(a, bs, da, _decimals(bs)):
            return True
    return False
'''
s = s[:i] + NEW + s[j + 1:]
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  _near 定稿：精度差+舍入关系")