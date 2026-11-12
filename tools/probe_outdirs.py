import os
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for d in ("fig2", "a", "zh", "fig_mpl", "figcheck_selftest"):
    p = os.path.join(HERE, "out", d)
    if not os.path.isdir(p):
        print("  %s: 不存在" % d)
        continue
    fs = []
    for r, _, files in os.walk(p):
        for f in files:
            fp = os.path.join(r, f)
            fs.append((os.path.relpath(fp, p), time.strftime(
                "%m-%d %H:%M", time.localtime(os.path.getmtime(fp)))))
    fs.sort(key=lambda x: x[1])
    print("  out/%-18s %d 文件" % (d, len(fs)))
    for name, t in fs[:5]:
        print("      %-34s %s" % (name, t))
    print()