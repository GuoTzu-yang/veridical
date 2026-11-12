import ast
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EDITS = [
    # 写数据的脚本：输出目录改成 out/data
    ("tools/make_kind_data.py",
     'OUT = os.path.join(HERE, "out", "kinds")',
     'OUT = os.path.join(HERE, "out", "data")'),
    ("tools/make_sim.py",
     'OUT = os.path.join(HERE, "out", "kinds")',
     'OUT = os.path.join(HERE, "out", "data")'),
    ("tools/probe_diag.py",
     'ds = mm.DS("out/scope_test.xlsx")',
     'ds = mm.DS("out/data/scope_test.xlsx")'),
]
for f, old, new in EDITS:
    p = os.path.join(HERE, f)
    s = open(p, encoding="utf-8").read()
    if old not in s:
        print("  [skip] %s" % f)
        continue
    s = s.replace(old, new)
    open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("  patched %s" % f)

# genfigs_domains.py：读数据从 out/data
p = os.path.join(HERE, "tools", "genfigs_domains.py")
s = open(p, encoding="utf-8").read()
s = s.replace('xl = os.path.join(HERE, "out", "domains", name + ".xlsx")',
              'xl = os.path.join(HERE, "out", "data", name + ".xlsx")')
s = s.replace('xl = os.path.join(HERE, "out", "kinds", name + ".xlsx")',
              'xl = os.path.join(HERE, "out", "data", name + ".xlsx")')
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("  patched tools/genfigs_domains.py")

# test_domains.py：数据写 out/data，产物留 out/domains
p = os.path.join(HERE, "tools", "test_domains.py")
s = open(p, encoding="utf-8").read()
s = s.replace('OUT = os.path.join(HERE, "out", "domains")',
              'DATA = os.path.join(HERE, "out", "data")\n'
              'OUT = os.path.join(HERE, "out", "domains")\n'
              'os.makedirs(DATA, exist_ok=True)')
s = s.replace('mk(os.path.join(OUT, "', 'mk(os.path.join(DATA, "')
s = s.replace('xl = os.path.join(OUT, name + ".xlsx")',
              'xl = os.path.join(DATA, name + ".xlsx")')
s = s.replace('print(f"  数据集已写入 {OUT}")', 'print(f"  数据集已写入 {DATA}")')
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("  patched tools/test_domains.py")