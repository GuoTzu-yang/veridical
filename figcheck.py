#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
figcheck.py —— 图表质量审查（第 9 轮，思路集成自 dsh-ultramath 的 check_figures.py）

取它的精华
----------
1. **10 分制四维**：标注完整性 3 / 配色科学性 3 / 排版审美 2 / 技术规范 2
2. **色盲不安全配色对**：红绿同时出现要扣分（这条我们原来完全没考虑）
3. **colormap 白名单**：只有 cividis/viridis/plasma/inferno/magma/
   RdBu_r/coolwarm/PiYG/PRGn 算合格
4. **背景纯白检查**：暖白底（如 #FFFCF8）扣分，印刷时偏黄
5. **Unicode 方块检测**：极端像素占比 > 5% 说明字体缺失、字变成了方块
6. **DPI 阈值 150**：低于这个值印刷会糊

去它的糟粕
----------
- 它的路径约定是 `问题N/图片/`，我们没有那种目录 —— 改成扫目录下所有 PNG
- 它把「是否用了 save_figure()」当加分项，那是它自家封装 —— 我们不认
- 它的配色分算法绕（`3.0 - ... if ... else 3.0`），简化为直接判定

我们加的
--------
**必须有同名 PDF**：只要有 PNG 没有 PDF，技术规范直接扣到 0。
数模论文的图进 LaTeX 应该是矢量；只有位图说明这条流水线没做对。

用法
    python figcheck.py out/fig_mpl            # 审一个目录
    python figcheck.py out/fig_mpl --md       # 同时写 Markdown 报告
    python figcheck.py selftest
"""

from __future__ import annotations

import os
import re
import sys

import numpy as np
from PIL import Image

# ── 配置（数值取自 ultramath，原样保留）──
COLORBLIND_UNSAFE_PAIRS = [
    ("red", "green"),
    ("#EE6677", "#228833"),
    ("#CC3311", "#117733"),
    ("#B85042", "#7E9B7E"),
]
RECOMMENDED_CMAPS = {
    "cividis", "viridis", "plasma", "inferno", "magma",
    "RdBu_r", "RdBu", "coolwarm", "PiYG", "PRGn",
}
MIN_FILE_KB = 5
MIN_WIDTH, MIN_HEIGHT = 600, 400
MIN_DPI = 150
# 像素预算：超过它就降采样再判，而不是整幅解码。
# 实测 out/runs/pop_panel/fig/corr.png 是 10515x10387 = 1.09 亿像素，
# 一次 convert("RGB") 约 437 MB，而 check_background / check_unicode_boxes
# 各解一次 —— 一张图就能把 gate 撑爆，并触发 PIL 的 DecompressionBomb 警告。
MAX_PIXELS = 30_000_000
# 把 PIL 自己的上限抬到预算之上，避免它先抛警告；
# 真正离谱的尺寸由 MAX_PIXELS 这条判据显式报出来。
Image.MAX_IMAGE_PIXELS = 4 * MAX_PIXELS

GRADE = ((8, "A"), (6, "B"), (4, "C"), (0, "D"))


# ══════════════════════════════════════════════════════════════════════
#  单项检查
# ══════════════════════════════════════════════════════════════════════
def _bounded_image(p: str):
    """开图并在超过像素预算时降采样。返回 (img, w, h, oversize)。

    降采样只用于像素级判据（背景色、极端像素占比）——这两项看的是整体
    色彩与比例，缩到 2000 px 长边不影响结论，却把内存从数百 MB 降到几十 MB。
    """
    img = Image.open(p)
    w, h = img.size
    px = w * h
    if px <= MAX_PIXELS:
        return img, w, h, False
    img.draft("RGB", (2000, 2000))       # JPEG 用；PNG 忽略
    img.thumbnail((2000, 2000))
    return img, w, h, True


def check_raster(p: str) -> dict:
    """DPI / 尺寸。"""
    try:
        img = Image.open(p)
    except OSError as e:
        return dict(ok=False, why=f"打不开：{e}", dpi=0, w=0, h=0, score=0.0)
    dpi = (img.info.get("dpi") or (72, 72))[0]
    w, h = img.size
    issues = []
    score = 1.0
    if dpi < MIN_DPI:
        issues.append(f"DPI={dpi:.0f} < {MIN_DPI}，印刷会糊")
        score = 0.4
    if w < MIN_WIDTH or h < MIN_HEIGHT:
        issues.append(f"尺寸 {w}x{h} 偏小")
        score = min(score, 0.5)
    # 过大不是「更好」：15 cm 版面塞进 1 万像素宽的热力图，格子细到读不出来，
    # 而且会把 PDF 撑大、把检查程序撑爆。
    if w * h > MAX_PIXELS:
        issues.append(f"尺寸 {w}x{h}（{w * h / 1e6:.1f}M 像素）过大："
                      f"按版面宽度无法辨认，且显著增大 PDF")
        score = min(score, 0.3)
    return dict(ok=not issues, issues=issues, dpi=dpi, w=w, h=h,
                score=score)


def check_size(p: str) -> dict:
    kb = os.path.getsize(p) / 1024
    if kb < MIN_FILE_KB:
        return dict(ok=False, size_kb=round(kb, 1), score=0.0,
                    issues=[f"文件仅 {kb:.1f}KB，可能空白或损坏"])
    if kb < 10:
        return dict(ok=True, size_kb=round(kb, 1), score=0.5,
                    issues=[f"文件偏小 {kb:.1f}KB"])
    return dict(ok=True, size_kb=round(kb, 1), score=1.0, issues=[])


def check_background(p: str) -> dict:
    """四角 + 四边中点是否纯白。暖白底扣分。"""
    try:
        img, _w, _h, _big = _bounded_image(p)
        arr = np.asarray(img.convert("RGB"))
    except OSError:
        return dict(ok=False, score=0.0, issues=["背景检查失败"])
    h, w = arr.shape[:2]
    pts = [arr[0, 0], arr[0, w - 1], arr[h - 1, 0], arr[h - 1, w - 1],
           arr[0, w // 2], arr[h - 1, w // 2],
           arr[h // 2, 0], arr[h // 2, w - 1]]
    r, g, b = np.mean(pts, axis=0)
    if (r, g, b) == (255, 255, 255):
        return dict(ok=True, bg="#FFFFFF", score=1.0, issues=[])
    hexc = f"#{int(r):02X}{int(g):02X}{int(b):02X}"
    if r >= 250 and g >= 250 and b >= 250:
        return dict(ok=False, bg=hexc, score=0.5,
                    issues=[f"背景 {hexc} 非纯白（暖白，印刷偏黄）"])
    return dict(ok=False, bg=hexc, score=0.2,
                issues=[f"背景 {hexc} 偏离白色较远"])


def check_unicode_boxes(p: str) -> dict:
    """极端像素占比过高 = 字变成了方块（字体缺失的典型症状）。"""
    try:
        img, _w, _h, _big = _bounded_image(p)
        arr = np.asarray(img.convert("RGB"))
    except OSError:
        return dict(ok=True, ratio=0.0, score=1.0, issues=[])
    # 只算**纯黑**。纯白是底色，正常图里白占大头，
    # 把白也算进去会让每张正常图都报 90%+（这是我自己写的 bug，
    # 检测器出错又一次 —— 文档里记过 7 次，这是第 8 次）。
    g = arr.mean(axis=2)
    ratio = float((g < 10).sum()) / g.size
    if ratio > 0.05:
        return dict(ok=False, ratio=round(ratio * 100, 1), score=0.0,
                    issues=[f"极端像素 {ratio * 100:.1f}%，疑似 Unicode "
                            f"方块（字体缺失）"])
    return dict(ok=True, ratio=round(ratio * 100, 1), score=1.0, issues=[])


def check_source_signal(src: str) -> dict:
    """从绘图源码里找质量信号。"""
    if not src:
        return dict(ok=None, score=0.0, issues=["没有绘图源码，无法判断标注"],
                    cmaps=[], colorblind_safe=True)
    issues = []
    score = 1.0
    cmaps = re.findall(r"""cmap\s*=\s*['"]([^'"]+)['"]""", src)
    bad = [c for c in cmaps
           if c not in RECOMMENDED_CMAPS and c not in ("gray", "Greys")]
    if bad:
        issues.append(f"非推荐 colormap: {sorted(set(bad))}")
        score -= 0.5

    # 色盲：红和绿同时出现
    red = re.search(r"#B85042|#EE6677|#CC3311|tab:red|'red'|\"red\"", src)
    green = re.search(r"#7E9B7E|#228833|#117733|'green'|\"green\"", src)
    safe = not (red and green)
    if not safe:
        issues.append("源码同时出现红与绿，色盲不友好")
        score -= 1.0

    if not re.search(r"set_[xy]label|xlabel|ylabel", src):
        issues.append("没有轴标签设置")
        score -= 0.5
    if re.search(r"imshow|heatmap", src) and not re.search(
            r"ax\.text|annotate", src):
        issues.append("有热力图但没有数值标注")
        score -= 0.5

    return dict(ok=not issues, issues=issues, score=max(0.0, min(3.0, score)),
                cmaps=sorted(set(cmaps)), colorblind_safe=safe)


def check_vector(png: str) -> dict:
    """我们加的：必须存在同名 PDF。

    位图进 LaTeX 会糊；没有 PDF 说明流水线还没做对。
    """
    pdf = os.path.splitext(png)[0] + ".pdf"
    if os.path.exists(pdf):
        return dict(ok=True, pdf=os.path.basename(pdf),
                    pdf_kb=round(os.path.getsize(pdf) / 1024, 1),
                    is_vector=True, score=1.0, issues=[])
    return dict(ok=False, pdf=None, is_vector=False, score=0.0,
                issues=["缺同名 PDF：图是位图，进 LaTeX 会糊"])


# ══════════════════════════════════════════════════════════════════════
#  汇总
# ══════════════════════════════════════════════════════════════════════
def audit_one(png: str, src_text: str = "") -> dict:
    ras = check_raster(png)
    siz = check_size(png)
    bg = check_background(png)
    uni = check_unicode_boxes(png)
    sig = check_source_signal(src_text)
    vec = check_vector(png)

    # 四维（上限与 ultramath 一致）
    d_annot = round(min(3.0, sig["score"]), 1)
    d_color = round(3.0 if sig["colorblind_safe"] and not any(
        "colormap" in x for x in sig["issues"]) else 1.5, 1)
    layout = round((ras["score"] + bg["score"]) / 2 * 2, 1)      # 满 2
    tech = round((siz["score"] + uni["score"]) / 2 * 2, 1)        # 满 2
    # 我们加的向量要求：没有 PDF 就把技术规范清零
    if not vec["ok"]:
        tech = 0.0

    total = round(d_annot + d_color + layout + tech, 1)
    grade = next(g for th, g in GRADE if total >= th)

    issues = (ras.get("issues", []) + siz.get("issues", [])
              + bg.get("issues", []) + uni.get("issues", [])
              + sig.get("issues", []) + vec.get("issues", []))
    return dict(file=os.path.basename(png), total=total, grade=grade,
                dims=dict(标注完整性=d_annot, 配色科学性=d_color,
                          排版审美=layout, 技术规范=tech),
                dpi=ras["dpi"], size_kb=siz["size_kb"],
                vector=vec["ok"], issues=list(dict.fromkeys(issues)))


def audit_dir(d: str, src_text: str = "", only=None) -> dict:
    """审一个目录。only 给定时只审这些文件名（论文引用的那些）。

    为什么需要 only：目录里可能有工具生成但论文没用的图（比如熵权条形图）。
    评审关心的是论文里出现的图，把没引用的图算进均分会冤枉论文。
    """
    pngs = sorted(f for f in os.listdir(d) if f.lower().endswith(".png"))
    if only:
        want = {str(x).replace(".png", "") for x in only}
        pngs = [f for f in pngs if f[:-4] in want]
    if not pngs:
        return dict(ok=False, why=f"{d} 下没有 PNG", results=[], avg=0.0)
    res = [audit_one(os.path.join(d, f), src_text) for f in pngs]
    avg = round(sum(r["total"] for r in res) / len(res), 1)
    return dict(ok=True, results=res, avg=avg, n=len(res),
                grades={g: sum(1 for r in res if r["grade"] == g)
                        for g in "ABCD"})


def report(r: dict) -> str:
    if not r.get("ok"):
        return f"  {r.get('why')}"
    L = [f"图表审查：{r['n']} 张，平均 {r['avg']}/10  "
         f"A{r['grades']['A']} B{r['grades']['B']} "
         f"C{r['grades']['C']} D{r['grades']['D']}", ""]
    for x in r["results"]:
        v = "PDF" if x["vector"] else "仅PNG"
        L.append(f"  [{x['grade']}] {x['file'][:26]:<28}{x['total']:>5}/10  "
                 f"{x['dpi']:.0f}dpi {x['size_kb']:>6.1f}KB {v}")
        for i in x["issues"]:
            L.append(f"        · {i}")
    return "\n".join(L)


# ══════════════════════════════════════════════════════════════════════
def selftest() -> int:
    bad = 0
    n = 0

    def ck(name, cond, detail=""):
        nonlocal bad, n
        n += 1
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}"
              + (f"  — {detail}" if detail else ""))
        if not cond:
            bad += 1

    here = os.path.dirname(os.path.abspath(__file__))
    import plot_mpl as P

    tmp = os.path.join(here, "out", "figcheck_selftest")
    os.makedirs(tmp, exist_ok=True)

    # 好图：300dpi + 纯白底 + 有 PDF + 好 colormap
    M = np.corrcoef(np.random.default_rng(0).normal(size=(4, 30)))
    P.plot_corr(M, ["a", "b", "c", "d"], out=os.path.join(tmp, "good"))
    r1 = audit_one(os.path.join(tmp, "good.png"), open(
        os.path.join(here, "plot_mpl.py"), encoding="utf-8").read())
    ck("好图有 PDF 矢量", r1["vector"])
    ck("好图评分 >= 6", r1["total"] >= 6, f"{r1['total']}/10 {r1['grade']}")

    # 无 PDF 的图 → 技术规范清零
    os.remove(os.path.join(tmp, "good.pdf"))
    r2 = audit_one(os.path.join(tmp, "good.png"), "")
    ck("缺 PDF 时技术规范为 0", r2["dims"]["技术规范"] == 0.0,
       str(r2["dims"]))
    ck("缺 PDF 被抓出", any("PDF" in i for i in r2["issues"]))

    # 色盲：源码里红绿同现
    s_bad = "plt.plot(c='red'); plt.plot(c='green'); ax.set_xlabel('x')"
    sig = check_source_signal(s_bad)
    ck("检出红绿同现", not sig["colorblind_safe"], str(sig["issues"])[:50])

    # 非推荐 colormap
    sig2 = check_source_signal("ax.imshow(M, cmap='jet'); ax.set_xlabel('x')")
    ck("检出非推荐 colormap", any("colormap" in i for i in sig2["issues"]))

    # 热力图缺标注
    sig3 = check_source_signal("ax.imshow(M, cmap='viridis'); "
                               "ax.set_xlabel('x')")
    ck("检出热力图缺数值标注",
       any("数值标注" in i for i in sig3["issues"]), str(sig3["issues"]))

    # 方块检测
    os.makedirs(tmp, exist_ok=True)
    blk = np.zeros((600, 600, 3), dtype=np.uint8) + 255
    # 黑块要够大才过 5% 阈值：600x600 的 5% = 18000 px ≈ 134x134。
    # 原来用 100x100（2.8%），改成只算纯黑后就不够了。
    blk[100:320, 100:320] = 0          # 220x220 = 13.4%，明确超过阈值
    Image.fromarray(blk).save(os.path.join(tmp, "blocks.png"))
    uni = check_unicode_boxes(os.path.join(tmp, "blocks.png"))
    ck("检出疑似 Unicode 方块", not uni["ok"], str(uni["issues"])[:50])

    # 纯白图 → 背景通过
    Image.fromarray(np.full((600, 600, 3), 255, dtype=np.uint8)).save(
        os.path.join(tmp, "white.png"))
    bg = check_background(os.path.join(tmp, "white.png"))
    ck("纯白底通过", bg["ok"], bg["bg"])

    # 暖白底 → 背景扣分
    warm = np.full((600, 600, 3), 255, dtype=np.uint8)
    warm[..., 2] = 248                 # 蓝通道略低 = 暖白
    Image.fromarray(warm).save(os.path.join(tmp, "warm.png"))
    bg2 = check_background(os.path.join(tmp, "warm.png"))
    ck("暖白底被扣分", not bg2["ok"] and bg2["score"] < 1.0, bg2["bg"])

    # 目录审查
    rr = audit_dir(tmp, "")
    ck("能审整个目录", rr["ok"] and rr["n"] >= 3, f"{rr['n']} 张")

    print(f"\n{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="图表质量审查")
    ap.add_argument("dir", nargs="?", default="")
    ap.add_argument("--src", default="", help="绘图源码路径（用于信号检查）")
    ap.add_argument("--md", action="store_true")
    a = ap.parse_args(argv)

    if not a.dir or a.dir == "selftest":
        return selftest()

    src = ""
    if a.src and os.path.exists(a.src):
        src = open(a.src, encoding="utf-8").read()
    r = audit_dir(a.dir, src)
    print(report(r))
    if a.md and r.get("ok"):
        p = os.path.join(a.dir, "图表质量报告.md")
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write("# 图表质量审查\n\n")
            f.write(f"平均 {r['avg']}/10，共 {r['n']} 张\n\n")
            f.write("| 文件 | 分 | 级 | 标注 | 配色 | 排版 | 技术 |\n")
            f.write("|---|---|---|---|---|---|---|\n")
            for x in r["results"]:
                d = x["dims"]
                f.write(f"| {x['file']} | {x['total']} | {x['grade']} | "
                        f"{d['标注完整性']} | {d['配色科学性']} | "
                        f"{d['排版审美']} | {d['技术规范']} |\n")
        print(f"\n  报告已写 {p}")
    return 0 if r.get("avg", 0) >= 6 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
