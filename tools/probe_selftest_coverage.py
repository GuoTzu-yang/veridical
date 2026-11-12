"""逐个跑「未登记模块」的 selftest，记录结果。

只读：不改任何文件。输出 Markdown 表，供决定钉哪些。
"""
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable

MODULES = [
    "aitaste.py", "cards.py", "chk_cross.py", "cite.py", "dataprof.py",
    "distill.py", "gate.py", "innovation.py", "kb_loader.py", "kind.py",
    "limit.py", "patches.py", "pipeline.py", "plot_mpl.py", "q4.py",
    "review.py", "rules.py", "rules_apcm.py", "rules_apmcm.py",
    "score.py", "verify_math.py",
    "tools/dp.py", "tools/fit_params.py", "tools/mip.py",
    "tools/net_metrics.py", "tools/queueing.py", "tools/stat_tests.py",
    "tools/topsis.py",
]
# 去重（列表里我手写了两条同义名，按实际文件为准）
MODULES = [m for m in dict.fromkeys(MODULES)]


def run(mod):
    p = os.path.join(HERE, mod)
    if not os.path.exists(p):
        return mod, None, 0.0, "文件不存在"
    t0 = time.time()
    try:
        r = subprocess.run([PY, p, "selftest"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           cwd=HERE, timeout=120)
        out = (r.stdout or "") + (r.stderr or "")
        n = len(re.findall(r"\[PASS\]", out))
        tail = [x.strip() for x in out.splitlines()
                if "ALL PASS" in x or "FAILED" in x]
        return mod, r.returncode, time.time() - t0, \
            (tail[-1] if tail else out.strip().splitlines()[-1:][0]
             if out.strip() else "(无输出)")
    except subprocess.TimeoutExpired:
        return mod, -1, time.time() - t0, "超时 120s"


def main():
    print("| 模块 | 退出码 | 秒 | PASS 数 | 结论 |")
    print("|---|---|---|---|---|")
    bad = []
    for mod in MODULES:
        m, code, dt, tail = run(mod)
        npass = len(re.findall(r"\[PASS\]", tail)) if code is not None else 0
        if code != 0:
            bad.append((m, code, tail))
        print(f"| `{m}` | {code} | {dt:.1f} | {npass} | {tail[:70]} |")
    print()
    print("非零退出:", len(bad))
    for m, c, t in bad:
        print(f"  {m}  exit={c}  {t[:100]}")


if __name__ == "__main__":
    main()
