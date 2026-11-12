"""量：CORE 里每个模块的「自报断言数」与「[PASS] 行数」是否一致。

只读。不一致的模块在钉数时容易钉错（第 100 轮 verify_math 就钉成了 20，实为 8）。
"""
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable

src = io.open(os.path.join(HERE, "tests", "run_all.py"), encoding="utf-8").read()
m = re.search(r"CORE\s*=\s*\[(.*?)\n\]", src, re.S)
entries = re.findall(r'\(\s*"([\w\.]+\.py)"\s*,\s*\[([^\]]*)\]\s*,\s*([^)]+)\)',
                     m.group(1))

print("| 模块 | 参数 | 自报 | [PASS] | 一致 |")
print("|---|---|---|---|---|")
mismatch = []
for mod, args, want in entries:
    argv = [PY, os.path.join(HERE, mod)]
    for a in re.findall(r'"([^"]+)"', args):
        argv.append(a)
    try:
        r = subprocess.run(argv, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", cwd=HERE,
                           timeout=180)
    except subprocess.TimeoutExpired:
        print(f"| {mod} | ? | 超时 | - | - |")
        continue
    out = (r.stdout or "") + (r.stderr or "")
    npass = out.count("[PASS]")
    mm = re.search(r"(?:ALL PASS|FAILED)\s+(\d+)/(\d+)", out)
    self_n = int(mm.group(2)) if mm else None
    same = (self_n == npass) if self_n is not None else None
    if same is False:
        mismatch.append((mod, self_n, npass, want.strip()))
    print(f"| {mod} | {args.strip() or '-'} | {self_n} | {npass} | "
          f"{'是' if same else ('否' if same is False else '无自报')} |")

print()
print("不一致（自报 ≠ [PASS] 行数）:", len(mismatch))
for mod, s, p, w in mismatch:
    print(f"  {mod}: 自报 {s} / [PASS] {p} / 当前钉数 {w}")
