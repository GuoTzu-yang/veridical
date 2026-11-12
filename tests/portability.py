#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可移植性回归测试：核心代码不得跨题借路径。

同一个病发作过三次
------------------
44 轮  mmkit._collect_figures 的第三个目录是仓库默认题的 out/fig
54 轮  paper.py 三处硬编码 <repo>/out/fig/{surfaces,tornado,cand}.pdf
55 轮  mmkit.video 的 fig_dirs 第三个目录同样是它

共同症状：在 model1-arch/ 里跑一切正常，换个目录跑就静默丢内容 ——
不报错，图/表就是不出现。用户看到的是「我的论文少了残差诊断」，
实际是代码去别处借了别人的图，或者压根没生成。

豁免：selftest 里的固定路径是有意为之
（abstract.py / innovation.py / patches.py / gate.py 的自测段）。
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

# 核心代码：这些模块参与实际出稿
CORE = ("mmkit.py", "paper.py", "mm.py", "plot_mpl.py", "figcheck.py")
# 有意固定路径的自测文件
EXEMPT = ("abstract.py", "innovation.py", "patches.py", "gate.py",
          "aitaste.py", "cards.py", "cases.py", "rules.py")

# 跨题借路径的特征：os.path.join(..., "out", "fig")
RX = re.compile(r'os\.path\.join\(\s*os\.path\.dirname\(\s*'
                r'os\.path\.abspath\(__file__\)\s*\)\s*,\s*\n?\s*'
                r'"out"\s*,\s*"fig"')


def main():
    bad = []
    for f in CORE:
        p = os.path.join(HERE, f)
        if not os.path.exists(p):
            continue
        s = open(p, encoding="utf-8").read()
        for m in RX.finditer(s):
            line = s[:m.start()].count("\n") + 1
            bad.append("%s:%d" % (f, line))
    # 额外规则：核心代码不得依赖当前工作目录
    cwd_hits = []
    for f in CORE:
        p = os.path.join(HERE, f)
        if not os.path.exists(p):
            continue
        s = open(p, encoding="utf-8").read()
        if "os.getcwd()" in s:
            cwd_hits.append(f)
    print("  核心模块跨题借路径：%d 处" % len(bad))
    for b in bad:
        print("    " + b)
    print("  依赖当前工作目录：%d 处" % len(cwd_hits))
    for c in cwd_hits:
        print("    " + c)
    n = len(bad) + len(cwd_hits)
    print()
    print("%s  %d/%d" % ("ALL PASS" if n == 0 else "FAILED", 2 - n, 2))
    return 0 if n == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())