# -*- coding: utf-8 -*-
"""rt7: dump text files as UTF-8 with line numbers (avoid PS 5.1 ANSI breakage)."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

def dump(path, start=1, end=None, prefix=""):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    n = len(lines)
    if end is None or end > n:
        end = n
    print(f"===== {prefix}{os.path.basename(path)}  total_lines={n}  showing {start}..{end} =====")
    for i in range(start - 1, end):
        print(f"{i+1:5d}| {lines[i]}")
    print(f"===== end {os.path.basename(path)} =====")

if __name__ == "__main__":
    p = sys.argv[1]
    s = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    e = int(sys.argv[3]) if len(sys.argv) > 3 else None
    dump(p, s, e)
