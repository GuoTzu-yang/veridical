import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "verify.py")
s = open(P, encoding="utf-8").read()
i = s.find("def _near(")
j = s.find("\ndef ", i + 10)
NEW = '''def _near(a: float, b: float) -> bool:
    """论文里的 a 能不能由输出里的 b 解释。

    一条判据：**a 必须是 b 按 a 的小数位舍入的结果**。

        round(b, decimals(a)) == a

    它同时挡住两种作弊，又放过真实舍入：

      真实舍入   a=0.00743(5位)  b=0.0074342   round(b,5)=0.00743   ✓
      编个高分   a=0.9999(4位)   b=1.0         round(1.0,4)=1.0     ✗
      改第 3 位  a=0.9999(4位)   b=0.9975      round(0.9975,4)≠a    ✗

    关键是 round 不会「补精度」：1.0 舍到 4 位还是 1.0，不会变成 0.9999。
    之前用「相对误差 0.5%」判，1.0 与 0.9999 只差 0.01%，就漏了。

    百分比换算（0.5918 与 59.18）先做 scale 再走同一条判据。
    """
    if a == b:
        return True
    da = _decimals(a)

    def _ok(x: float) -> bool:
        try:
            return abs(round(x, da) - a) <= 1e-12
        except (ValueError, OverflowError):
            return False

    if _ok(b):
        return True
    for scale in (100.0, 0.01):
        if _ok(b * scale):
            return True
    return False
'''
s = s[:i] + NEW + s[j + 1:]
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  _near 终版：round(b, da) == a")