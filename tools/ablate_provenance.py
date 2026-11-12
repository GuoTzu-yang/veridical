"""消融：把冻结数字表删掉，溯源率会塌到多少？

这就是「没有护栏的论文」的样子 —— 不是拿另一个模型来比自己（那样没有意义），
而是把护栏本身关掉，看同一个产物还能被追溯多少。
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
PY = sys.executable
OUT = os.path.join(HERE, "out", "final")


def trace(tex_dir):
    tex = os.path.join(tex_dir, "paper.tex")
    r = subprocess.run([PY, "verify.py", tex], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=HERE,
                       timeout=300)
    import re
    # verify.py 把比例打在 stderr（stdout 只给结构化摘要），
    # 只读 stdout 会拿到 None —— 第一版就这么错的（第 110 轮）。
    out = (r.stdout or "") + (r.stderr or "")
    m = re.search(r"(\d+)/(\d+)\s*\(([\d.]+)%\)", out)
    if not m:
        return None, None, None
    return int(m.group(1)), int(m.group(2)), float(m.group(3))


cfg = json.load(io.open(os.path.join(HERE, "runs.json"), encoding="utf-8"))
names = ["heat_sink", "queueing", "icm2006c", "evaluation", "population"]
rows = []
for n in names:
    src = os.path.join(HERE, cfg[n]["out"])
    if not os.path.exists(os.path.join(src, "paper.tex")):
        continue
    # ① 原样
    ok0, tot0, pct0 = trace(src)
    # ② 拷到临时目录、删掉冻结表
    tmp = tempfile.mkdtemp(prefix="abl_")
    dst = os.path.join(tmp, n)
    shutil.copytree(src, dst)
    for f in os.listdir(dst):
        # 只删冻结表。原来第二个条件把第一条件完全吞掉，
        # 等于把溯源池清空 —— 0.0% 是算术，不是测量（红队 F4）。
        if f.endswith("冻结数字.json"):
            try:
                os.remove(os.path.join(dst, f))
            except OSError:
                pass
    ok1, tot1, pct1 = trace(dst)
    shutil.rmtree(tmp, ignore_errors=True)
    rows.append(dict(name=n, with_table=pct0, without_table=pct1,
                     n_with=ok0, n_without=ok1,
                     # 分母也要记：表格里「孤儿 token 数」必须是量出来的，
                     # 不能由比例反推（第 110 轮我用反推填过表）
                     n_total=tot0, n_total_without=tot1))
    # 0.0 是假值：pct or -1 会把真实的 0% 打成 -1（第 110 轮踩过）
    _f = lambda v: ("%5.1f%%" % v) if v is not None else "  无法判定"
    print("  %-14s 有表 %s  ->  无表 %s" % (n, _f(pct0), _f(pct1)))

json.dump(rows, io.open(os.path.join(OUT, "ablation.json"), "w",
                        encoding="utf-8", newline="\n"),
          ensure_ascii=False, indent=1)
print("已写 out/final/ablation.json")
