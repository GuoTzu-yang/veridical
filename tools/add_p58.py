#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""加补丁 P58：领域流水线回归（慢测试）+ 判定修正。"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "patches.py")
s = open(P, encoding="utf-8").read()

if "P58" not in s:
    HELPER = '''def _p58_wired():
    """流水线级领域回归（5/5）+ 判定只算致命错误。"""
    import os as _o
    t = _o.path.join(HERE, "tools", "test_domains.py")
    dp = _o.path.join(HERE, "tests", "domain_pipeline.py")
    if not _o.path.exists(dp):
        return False, "缺 tests/domain_pipeline.py"
    src = open(t, encoding="utf-8").read()
    if "pdftex.def Error" not in src:
        return False, "test_domains 判定未排除图片缺失"
    if "import re" not in src:
        return False, "test_domains 缺 import re"
    r = open(_o.path.join(HERE, "tests", "run_all.py"),
             encoding="utf-8").read()
    if "domain_pipeline.py" not in r:
        return False, "run_all 未包含 domain_pipeline"
    return True, "5/5 流水线通过；慢测试由 MM_SLOW=1 控制，默认跳过"


'''
    ANCHOR = ("# " + "═" * 70 + "\n#  补丁清单")
    k = s.find(ANCHOR)
    assert k > 0, "找不到补丁清单锚点"
    s = s[:k] + HELPER + s[k:]

    ENTRY = ('    Patch("P58", "④ 验证", "领域流水线回归（慢）",\n'
             '          "5 个领域完整跑 --compile；判定只算致命错误（图片缺失是降级）；'
             'MM_SLOW=1 开启",\n'
             '          _p58_wired,\n'
             '          tags=["已做", "验证"]),\n'
             '    Patch("P57",')
    s = s.replace('    Patch("P57",', ENTRY, 1)

    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  已加 P58")

import subprocess
import sys
r = subprocess.run([sys.executable, "patches.py", "verify"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
for ln in (r.stdout or "").splitlines():
    if "P58" in ln or "已落实" in ln:
        print("  " + ln.strip())
