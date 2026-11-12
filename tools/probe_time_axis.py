"""量：统一时间轴判据后，题库里哪些列被判成时间轴、有没有误伤 y。"""
import io
import json
import os
import sys

sys.path.insert(0, r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch")
import numpy as np  # noqa: E402
import mm  # noqa: E402

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
cfg = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))

print("=" * 78)
print("统一判据后的时间轴识别")
print("=" * 78)
bad_y = []
for name, it in cfg.items():
    fz = os.path.join(HERE, it["out"], "冻结数字.json")
    if not os.path.exists(fz):
        continue
    fd = json.load(io.open(fz, encoding="utf-8"))
    src = str(fd.get("source") or "").split(" · ")[0].strip()
    cands = [os.path.join(HERE, "out", "data", src),
             os.path.join(HERE, "out", "data", src + ".xlsx")]
    data = next((c for c in cands if os.path.exists(c)), None)
    if not data:
        print("  %-16s 数据找不到" % name)
        continue
    ds = mm.DS(data)
    ax = mm.time_axis_cols(ds)
    y = fd.get("y")
    # 旧判据对照
    old = []
    for nm in ds.num_names:
        if mm.is_time_like(nm):
            old.append(nm)
    y_hit = y in ax
    if y_hit:
        bad_y.append((name, y, ax))
    print("  %-16s 新判据=%-34s 旧(is_time_like)=%s%s"
          % (name, str(ax)[:34], str(old)[:40], "   ← y 被判成轴！" if y_hit else ""))

print()
print("y 被判成时间轴的题:", bad_y if bad_y else "无")
