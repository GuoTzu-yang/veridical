import os
import sys
import warnings

warnings.filterwarnings("ignore")
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(HERE, "external")
out = []
for root, dirs, files in os.walk(EXT):
    dirs[:] = [d for d in dirs if d not in (".git", "node_modules")]
    for f in files:
        if not f.lower().endswith((".xlsx", ".xls", ".csv", ".tsv")):
            continue
        p = os.path.join(root, f)
        try:
            sz = os.path.getsize(p)
        except OSError:
            continue
        if sz > 20 * 1024 * 1024:
            continue
        try:
            if f.lower().endswith((".csv", ".tsv")):
                sep = "\t" if f.lower().endswith(".tsv") else None
                d = pd.read_csv(p, nrows=500, sep=sep, low_memory=False,
                               encoding_errors="replace")
            else:
                xl = pd.ExcelFile(p)
                best = (-1, -1, None)
                for sh in xl.sheet_names:
                    try:
                        d2 = xl.parse(sh)
                    except Exception:
                        continue
                    nnum = sum(1 for c in d2.columns
                               if pd.api.types.is_numeric_dtype(d2[c]))
                    if nnum > best[0]:
                        best = (nnum, len(d2), sh)
                if best[2] is None:
                    continue
                d = xl.parse(best[2])
        except Exception:
            continue
        nnum = sum(1 for c in d.columns
                   if pd.api.types.is_numeric_dtype(d[c]))
        if nnum >= 3 and len(d) >= 20:
            out.append((f, len(d), nnum, sz,
                        os.path.relpath(p, HERE).replace("\\", "/")))

out.sort(key=lambda r: (-r[2], -r[1]))
seen = {}
print("  文件名                          行   数值列   大小    路径")
print("  " + "-" * 74)
for f, nrow, nnum, sz, rel in out:
    key = (f, nrow, nnum)
    if key in seen:
        continue
    seen[key] = rel
    print("  %-28s %5d %5d %7.0fK  %s"
          % (f[:28], nrow, nnum, sz / 1024, rel[:44]))
print()
print("  去重后 %d 个不同结构的候选" % len(seen))