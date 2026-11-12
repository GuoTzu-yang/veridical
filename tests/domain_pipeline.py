#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""流水线级领域回归（慢）：5 个领域各跑一次完整 mmkit --compile。

与 domain_compile.py 的分工
---------------------------
domain_compile.py    公式级：把 equation 包最小 document 编译，快（1-2 秒/个），
                     只验证公式本身能否渲染。
domain_pipeline.py   流水线级：完整跑 mmkit run --compile，慢（30-60 秒/个），
                     验证「这道题在这个领域上能出稿」——
                     中文泄漏、时间轴误判、必做项检查这些只有它能发现。

所以：公式级必跑（已进 run_all）；流水线级用 MM_SLOW=1 手动开启。
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), "tools", "test_domains.py")


def main():
    if os.environ.get("MM_SLOW") != "1":
        # 慢测试默认跳过，但**不能报成通过** —— 退出码 0 会让 run_all
        # 显示 OK，而这条什么都没测。用 0 但打醒目 SKIP，由 run_all 的
        # 输出可见性兜底（run_all 会打印子进程输出）。
        print("  [SKIP] 流水线级领域回归默认不跑（设 MM_SLOW=1 开启）")
        print("         公式级回归在 domain_compile.py，那条是必跑的")
        return 0
    if not os.path.exists(TOOL):
        print(f"  [FAIL] 找不到 {TOOL}")
        return 1
    r = subprocess.run([sys.executable, TOOL], cwd=os.path.dirname(HERE))
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(main())
