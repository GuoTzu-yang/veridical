import ast
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "verify.py")
s = open(P, encoding="utf-8").read()

OLD = '''def _near(a: float, b: float) -> bool:
    """两个数是否是「同一个数的不同精度」。"""
    if a == b:
        return True
    d = max(abs(a), abs(b), 1e-12)
    # 相对误差 0.5%（覆盖 3 位有效数字的舍入）
    if abs(a - b) / d <= 0.005:
        return True'''
assert OLD in s, "no anchor"
NEW = '''def _decimals(x: float) -> int:
    """这个数写出了几位小数（用 repr，避开科学计数法）。"""
    r = repr(float(x))
    if "e" in r or "E" in r:
        # 1e-05 这类：按有效位数算
        mant = r.split("e")[0].split("E")[0]
        return len(mant.replace("-", "").replace(".", "").lstrip("0"))
    if "." not in r:
        return 0
    return len(r.split(".")[1])


def _near(a: float, b: float) -> bool:
    """两个数是否是「同一个数的不同精度」。

    这里必须区分方向：论文里的数 a 要能被输出里的 b 解释。
    如果 b 的精度比 a 低太多，b 不足以确认 a ——
    `1.0` 的舍入区间是 [0.95, 1.05)，任何落在里面的数都会「匹配」，
    于是编一个 0.9999 就能靠某个 1.0 蒙混过关（实测漏抓）。
    允许的精度差是 2 位（覆盖 0.0074342 -> 0.00743 这种舍入）。
    """
    if a == b:
        return True
    if _decimals(b) < _decimals(a) - 2:
        return False
    d = max(abs(a), abs(b), 1e-12)
    # 相对误差 0.5%（覆盖 3 位有效数字的舍入）
    if abs(a - b) / d <= 0.005:
        return True'''
s = s.replace(OLD, NEW, 1)
ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  _near 已区分精度方向")