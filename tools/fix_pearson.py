import ast, os, re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "gate.py")
s = open(P, encoding="utf-8").read()

# 删掉刚才插错位置的 _pearson（连同它前面的定位）
i = s.find("def _pearson(a, b):")
if i > 0:
    j = s.find("def main(", i)
    # 只删到下一个 def 之前
    k = s.find("\ndef ", i + 10)
    if k > 0:
        s = s[:i] + s[k + 1:]
    else:
        s = s[:i] + s[j:]

# 用法改成内联
OLD = '                _rho = _pearson(_xv, _yv)'
assert OLD in s
NEW = ('                _aa = np.asarray(_xv, dtype=float)\n'
       '                _bb = np.asarray(_yv, dtype=float)\n'
       '                _mm = ~(np.isnan(_aa) | np.isnan(_bb))\n'
       '                _rho = (float(np.corrcoef(_aa[_mm], _bb[_mm])[0, 1])\n'
       '                        if _mm.sum() > 2 else 0.0)')
s = s.replace(OLD, NEW, 1)

# 确保 import numpy as np
if "import numpy as np" not in s:
    s = s.replace("import os", "import os\nimport numpy as np", 1)

ast.parse(s); compile(s, P, "exec")
open(P, "w", encoding="utf-8", newline="\n").write(s)
print("  改为内联 corrcoef")