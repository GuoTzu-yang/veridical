#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证：用 meta/repos 替代 FTS files 做 stats，结果是否逐字相同。

不验证就换 = 拿正确性换速度。这里逐项比对集合。
"""
import os
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import kb  # noqa: E402

conn = sqlite3.connect(f"file:{kb.INDEX}?mode=ro", uri=True, timeout=120)


def timed(q):
    t0 = time.perf_counter()
    rows = conn.execute(q).fetchall()
    return time.perf_counter() - t0, rows


print("=== 原始实现（查 FTS 虚表 files）")
t1, n_files = timed("SELECT count(*) FROM files")
t2, r_files = timed("SELECT DISTINCT repo FROM files ORDER BY repo")
t3, c_files = timed("SELECT DISTINCT category FROM files ORDER BY category")
print(f"  count(*)          {t1:6.3f}s  {n_files[0][0]}")
print(f"  distinct repo     {t2:6.3f}s  {len(r_files)} 个")
print(f"  distinct category {t3:6.3f}s  {len(c_files)} 个")
print(f"  合计 {t1 + t2 + t3:6.3f}s")

print("\n=== 候选实现（查普通表 meta / repos）")
t4, n_meta = timed("SELECT count(*) FROM meta")
t5, r_meta = timed("SELECT DISTINCT repo FROM meta ORDER BY repo")
t6, c_repos = timed("SELECT DISTINCT category FROM repos ORDER BY category")
print(f"  count(*) meta     {t4:6.3f}s  {n_meta[0][0]}")
print(f"  distinct repo     {t5:6.3f}s  {len(r_meta)} 个")
print(f"  distinct category {t6:6.3f}s  {len(c_repos)} 个")
print(f"  合计 {t4 + t5 + t6:6.3f}s")

print("\n=== 逐项比对")
same_n = n_files[0][0] == n_meta[0][0]
print(f"  文件数相同: {same_n}  ({n_files[0][0]} vs {n_meta[0][0]})")
same_r = r_files == r_meta
print(f"  repo 列表逐字相同: {same_r}")
if not same_r:
    print(f"    只在 files: {set(r_files) - set(r_meta)}")
    print(f"    只在 meta : {set(r_meta) - set(r_files)}")
same_c = c_files == c_repos
print(f"  category 列表逐字相同: {same_c}")
if not same_c:
    print(f"    只在 files: {set(c_files) - set(c_repos)}")
    print(f"    只在 repos: {set(c_repos) - set(c_files)}")

print("\n=== repos.files 求和 vs meta 行数")
_, sum_files = timed("SELECT sum(files) FROM repos")
print(f"  sum(repos.files) = {sum_files[0][0]}   meta 行数 = {n_meta[0][0]}"
      f"   相同: {sum_files[0][0] == n_meta[0][0]}")

conn.close()
