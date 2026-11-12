# -*- coding: utf-8 -*-
"""rt7_grep.py —— 文件内检索/读取（替掉内联 python -c），只读。

用法:
    python tools/rt7_grep.py read  FILE [start] [end]
    python tools/rt7_grep.py grep  FILE PATTERN [--re]
    python tools/rt7_grep.py walk  DIR  PATTERN [--re] [--ext .tex,.md]
"""
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def read(p, s=1, e=None):
    L = io.open(p, encoding="utf-8", errors="replace").read().splitlines()
    n = len(L)
    e = n if (e is None or e > n) else e
    print(f"===== {p}  lines={n}  showing {s}..{e} =====")
    for i in range(s - 1, e):
        print(f"{i+1:5d}| {L[i]}")
    return 0


def grep(p, pat, use_re=False):
    rx = re.compile(pat if use_re else re.escape(pat))
    n = 0
    for i, l in enumerate(io.open(p, encoding="utf-8", errors="replace")):
        if rx.search(l):
            n += 1
            print(f"{p}:{i+1}| {l.rstrip()[:200]}")
    if not n:
        print(f"{p}: 0 hits for {pat!r}")
    return 0


def walk(d, pat, use_re=False, exts=None):
    rx = re.compile(pat if use_re else re.escape(pat))
    n = 0
    for dp, dn, fn in os.walk(d):
        dn[:] = [x for x in dn if x not in ("__pycache__", ".git")]
        for f in fn:
            if exts and not f.lower().endswith(tuple(exts)):
                continue
            p = os.path.join(dp, f)
            try:
                for i, l in enumerate(io.open(p, encoding="utf-8",
                                             errors="replace")):
                    if rx.search(l):
                        n += 1
                        print(f"{p}:{i+1}| {l.rstrip()[:200]}")
            except OSError:
                continue
    print(f"--- total {n} hits")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        raise SystemExit(2)
    cmd = a[0]
    use_re = "--re" in a
    a = [x for x in a if x != "--re"]
    ext = None
    if "--ext" in a:
        k = a.index("--ext")
        ext = [x if x.startswith(".") else "." + x
               for x in a[k + 1].split(",")]
        a = a[:k] + a[k + 2:]
    if cmd == "read":
        raise SystemExit(read(a[1], int(a[2]) if len(a) > 2 else 1,
                              int(a[3]) if len(a) > 3 else None))
    if cmd == "grep":
        raise SystemExit(grep(a[1], a[2], use_re))
    if cmd == "walk":
        raise SystemExit(walk(a[1], a[2], use_re, ext))
    print("unknown cmd", cmd)
    raise SystemExit(2)
