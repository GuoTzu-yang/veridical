import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "verify.py")
s = open(P, encoding="utf-8").read()
i = s.find("def _near(")
j = s.find("\ndef ", i + 10)
NEW = '''def _near(a: float, b: float) -> bool:
    """论文里的 a 能不能由输出里的 b 解释。

    判据只有一条：**a 必须是 b 的舍入**（round(b, a 的小数位) == a）。

    为什么不看相对误差：
      b = 1.0，a = 0.9999，相对差 0.01% —— 看起来「同源」，但 1.0 的
      舍入区间是 [0.95, 1.05)，任何数都能挂上去，编一个 0.9999 就溜了。
      实测漏抓过。
      反过来 b = 0.9975，a = 0.9999，都是 4 位，差 0.24%，那是改数。

    这条判据同时覆盖两种情况：
      舍入       a=0.5918, b=0.59177  -> round(0.59177, 4) == 0.5918  ✓
      百分比     a=59.18,  b=0.5918   -> 先做 scale 换算再比
    """
    if a == b:
        return True
    da = _decimals(a)

    def _round_ok(x: float) -> bool:
        try:
            return abs(round(x, da) - a) <= 1e-12
        except (ValueError, OverflowError):
            return False

    if _round_ok(b):
        return True
    # 百分比 vs 小数：0.5918 与 59.18
    for scale in (100.0, 0.01):
        if _round_ok(b * scale):
            return True
    return False
'''
s = s[:i] + NEW + s[j + 1:]
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  _near 改为「a 必须是 b 的舍入」")