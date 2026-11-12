import os
import shutil
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = os.path.join(HERE, "out", "runs", "chemical", "paper.tex")
dst = os.path.join(HERE, "out", "runs", "chemical", "_forged.tex")
t = open(src, encoding="utf-8").read()
# 编一个极具吸引力但完全假的数字，塞进摘要
fake = ("The model achieves an R-squared of 0.9999 and a "
        "cross-validated RMSE of 0.000123, which is unprecedented. ")
i = t.find(r"\begin{abstract}")
j = t.find("\n", i) + 1
t2 = t[:j] + fake + t[j:]
open(dst, "w", encoding="utf-8", newline="\n").write(t2)
print("  已生成伪造版：%s" % os.path.basename(dst))
print("  插入的内容：R-squared of 0.9999 / RMSE of 0.000123")