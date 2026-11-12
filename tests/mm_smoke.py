#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mm.py 的回归：把「数据事实」钉成断言。

这里钉的不是"程序能跑"，而是**这份附件算出来的具体结果**。
哪天数据换了、算法改错了，这些断言会先红。

钉住的事实（APMCM 2026 B 题，84 行）：
    1. 表头在第 2 行，7 个数值列 —— 自动识别没猜错
    2. 「样本编号」是 ID 列 —— 不该进 VIF
    3. 线性结构 CV 最优，二次差 18.3% —— 与 craft.py 独立算出的一致
    4. 帕累托前沿 12 个点
    5. 权重扫描最稳的是 #64（占 61% 权重空间）
    6. 熵权法 TOPSIS 排名第一也是 #64  ← 两条独立路径撞同一个点
    7. 对数/幂律判"不适用"（自变量含 0）
"""

from __future__ import annotations

import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

fails = []


def check(name, cond, detail=""):
    tag = "[PASS]" if cond else "[FAIL]"
    print(f"  {tag} {name}" + (f"  — {detail}" if detail else ""))
    if not cond:
        fails.append(name)


def run(args):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    r = subprocess.run([sys.executable, os.path.join(ROOT, "mm.py")] + args,
                       capture_output=True, cwd=ROOT, env=env, timeout=300)
    return r.returncode, ((r.stdout or b"") + (r.stderr or b"")).decode(
        "utf-8", "replace")


def main() -> int:
    # ---------- load ----------
    code, out = run(["load"])
    check("load 退出码 0", code == 0, f"exit={code}")
    check("表头自动识别在第 2 行", "表头第 2 行" in out)
    m = re.search(r"(\d+) 行 × (\d+) 数值列", out)
    check("行数/列数", m is not None and m.group(1) == "84" and m.group(2) == "7",
          m.group(0) if m else "没找到")

    # ---------- eda ----------
    code, out = run(["eda"])
    check("eda 退出码 0", code == 0, f"exit={code}")
    check("识别出 ID 列（样本编号）",
          "ID 列，不进模型" in out,
          "ID 列如果进了 VIF，相关矩阵会被带偏")
    check("相关矩阵在", "相关矩阵" in out)
    check("有异常值被标出来", "异常值" in out)

    # ---------- fit ----------
    code, out = run(["fit", "--y", "热阻", "--x", "宽度,深高,排数"])
    check("fit 退出码 0", code == 0, f"exit={code}")
    check("对数/幂律判不适用（含 0）",
          out.count("自变量含 0，取不了对数") >= 2,
          "这条消失说明数据被过滤了")
    # 数据事实：线性最优
    m = re.search(r"最优：(\S+)\s+CV=", out)
    check("最优结构是线性", m is not None and m.group(1) == "线性",
          m.group(1) if m else "没找到")
    # 二次比线性差 —— 具体降幅允许随折划分微变，但方向必须是负
    m2 = re.search(r"二次\s+([\d.]+)\s+(-[\d.]+%)", out)
    check("二次结构相对线性为负收益",
          m2 is not None and m2.group(2).startswith("-"),
          m2.group(0) if m2 else "没找到")

    # ---------- opt ----------
    code, out = run(["opt", "--min", "热阻,压降,温度"])
    check("opt 退出码 0", code == 0, f"exit={code}")
    m = re.search(r"帕累托前沿：(\d+) / (\d+)", out)
    check("前沿 12 / 84", m is not None and m.group(1) == "12"
          and m.group(2) == "84", m.group(0) if m else "没找到")
    m2 = re.search(r"行 #(\d+)\s+占\s+(\d+)% 权重空间", out)
    check("最稳解是 #64", m2 is not None and m2.group(1) == "64",
          m2.group(0) if m2 else "没找到")

    # ---------- score ----------
    code, out = run(["score", "--cost", "热阻,压降,温度"])
    check("score 退出码 0", code == 0, f"exit={code}")
    m = re.search(r"1\s+#(\d+)\s+[\d.]+", out)
    check("熵权 TOPSIS 第一名也是 #64",
          m is not None and m.group(1) == "64",
          "两条独立路径（权重扫描 / 熵权评价）撞同一个点，是交叉验证")

    # ---------- sens ----------
    code, out = run(["sens", "--y", "热阻", "--x", "宽度,深高,排数"])
    check("sens 退出码 0", code == 0, f"exit={code}")
    check("灵敏度给出最敏感项", "最敏感" in out)

    print()
    if fails:
        print(f"  失败 {len(fails)} 项：{fails}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
