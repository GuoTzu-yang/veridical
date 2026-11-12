"""rtB / results board: locate the engineering log and the selftest-coverage numbers.

Read-only. Prints only.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINAL = os.path.join(ROOT, "out", "final")

TARGET_BYTES = 132523

print("=== files with size == %d (record_bytes in data.json) ===" % TARGET_BYTES)
found = []
for base in [ROOT]:
    for r, ds, fs in os.walk(base):
        ds[:] = [x for x in ds if x not in (".git", "__pycache__", "node_modules", ".venv")]
        for f in fs:
            p = os.path.join(r, f)
            try:
                sz = os.path.getsize(p)
            except OSError:
                continue
            if sz == TARGET_BYTES:
                found.append(p)
for p in found:
    print("  ", os.path.relpath(p, ROOT))
if not found:
    print("   none at exactly that size")

print("\n=== *.jsonl / ledger-like files > 50 kB (candidate engineering log) ===")
for r, ds, fs in os.walk(ROOT):
    ds[:] = [x for x in ds if x not in (".git", "__pycache__", "node_modules", ".venv")]
    for f in fs:
        if not f.endswith((".jsonl", ".log")):
            continue
        p = os.path.join(r, f)
        sz = os.path.getsize(p)
        if sz > 50000:
            print("  %-70s %d bytes (%.1f KiB / %.1f kB)" %
                  (os.path.relpath(p, ROOT), sz, sz / 1024, sz / 1000))

print("\n=== where do '20 of 46' / '51 of 51' come from? grep sources+artifacts ===")
pat = re.compile(r"(20\s*(of|/)\s*46|51\s*(of|/)\s*51|n_modules_with_selftest|selftest_cover|n_selftests)")
for r, ds, fs in os.walk(ROOT):
    ds[:] = [x for x in ds if x not in (".git", "__pycache__", "node_modules", ".venv", "fig")]
    for f in fs:
        if not f.endswith((".py", ".json", ".tex", ".md")):
            continue
        p = os.path.join(r, f)
        try:
            t = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        hits = [ln.strip() for ln in t.splitlines() if pat.search(ln)]
        if hits:
            print("\n", os.path.relpath(p, ROOT))
            for h in hits[:8]:
                print("    ", h[:150])
