"""PDF 逐页视觉检查（固定流程，含嵌套 PDF）。

为什么需要
----------
第 20 轮实测：gate 的 20 项里 abstract 100/100、numbers 64/64、abs_page PASS
全是绿灯，但论文第 2 页是半页空白、第 1 页摘要被切断。
**机器检查和人的眼睛是两件事**——版面问题（摘要跨页、表格溢出、图注被截、
公式错位、孤行、空白页）只能看，不能查。

本工具做三件事
--------------
1. 把每页渲染成 PNG，算「墨迹密度」（非白像素占比）
     · < 2%   → 近乎空白页（通常是一次分页事故）
     · > 58%  → 过密（表格/图溢出风险）
2. 检查论文里 \\includegraphics 引用的 **PDF 图**（嵌套 PDF），各自渲染首页，
   同样算墨迹密度 —— 图内空白过多往往是画布尺寸没裁。
3. 生成一份可逐张点开的清单，人眼复核用。

刻意不做自动「判定合格」：它只负责把可疑页挑出来，判断仍要人看。

用法
    python tools/pagecheck.py out/d2026c
    python tools/pagecheck.py out/d2026c --dpi 120
    python tools/pagecheck.py out/d2026c --no-nested
"""
import argparse
import glob
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# MiKTeX 自带 poppler 的 pdftoppm
CANDS = [
    r"C:\Users\21246\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdftoppm.exe",
    "pdftoppm",
]
INK_LOW = 0.02
INK_HALF = 0.05      # 非末页低于这个墨迹，通常是分页把大半页浪费了
INK_HIGH = 0.58


def find_ppm():
    for c in CANDS:
        if c == "pdftoppm" or os.path.exists(c):
            return c
    return None


def render(pdf, outdir, dpi=100, first=None, last=None):
    ppm = find_ppm()
    if not ppm:
        return []
    os.makedirs(outdir, exist_ok=True)
    for f in glob.glob(os.path.join(outdir, "*.png")):
        os.remove(f)
    cmd = [ppm, "-png", "-r", str(dpi)]
    if first:
        cmd += ["-f", str(first)]
    if last:
        cmd += ["-l", str(last)]
    cmd += [pdf, os.path.join(outdir, "pg")]
    subprocess.run(cmd, capture_output=True)
    return sorted(glob.glob(os.path.join(outdir, "pg-*.png")))


def ink_ratio(png, y0=0.0, y1=1.0):
    """指定纵向区间内的非白像素占比。

    只看整页会误判：散点图/线图天然是稀疏点阵，整页墨迹可能只有 4–5%，
    但页面其实排得满满的（图 + 图注 + 接续文字）。实测第 8 页就被误报成
    「半空页」。所以「半空」改用**页面下半部分**判断：真正被分页浪费掉的页，
    下半基本全空；有图表的页，下半总有图注或正文。
    """
    try:
        from PIL import Image
        im = Image.open(png).convert("L")
        w, h = im.size
        px = im.load()
        ya, yb = int(h * y0), int(h * y1)
        dark = 0
        total = 0
        for y in range(ya, yb, 3):
            for x in range(0, w, 3):
                total += 1
                if px[x, y] < 235:
                    dark += 1
        return dark / max(1, total)
    except Exception:
        return None


def ink_bottom(png):
    """页面下半 45% 的墨迹密度。"""
    return ink_ratio(png, 0.55, 1.0)


def find_images_tool():
    c = r"C:\Users\21246\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdfimages.exe"
    return c if os.path.exists(c) else None


def embedded_images(pdf):
    """pdfimages -list：每张嵌入位图的像素尺寸与**有效 DPI**。

    有效 DPI 才是印刷质量的判据：同一张 2000px 图，铺满整页宽只有 250 dpi，
    缩到半页宽就有 500 dpi。低于 150 印出来会糊。
    """
    tool = find_images_tool()
    if not tool:
        return None
    r = subprocess.run([tool, "-list", pdf], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    rows = []
    for line in (r.stdout or "").splitlines():
        p = line.split()
        if len(p) < 15 or not p[0].isdigit() or p[2] != "image":
            continue
        try:
            rows.append(dict(page=int(p[0]), w=int(p[3]), h=int(p[4]),
                             xppi=float(p[12]), yppi=float(p[13]),
                             size=p[14]))
        except (ValueError, IndexError):
            continue
    return rows


def nested_pdfs(tex):
    """找出 \\includegraphics 引用的 .pdf 文件。"""
    t = open(tex, encoding="utf-8").read()
    base = os.path.dirname(tex)
    out = []
    for m in re.finditer(r"\\includegraphics\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}", t):
        p = m.group(1).strip()
        if not p.lower().endswith(".pdf"):
            continue
        full = p if os.path.isabs(p) else os.path.join(base, p)
        out.append(full)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="PDF 逐页视觉检查")
    ap.add_argument("dir", help="包含 paper.pdf 的目录")
    ap.add_argument("--dpi", type=int, default=150,
                    help="渲染分辨率。100 太小：hyperref 的红框在 100dpi 会糊成 [?]，"
                         "实测把 Section 7 误看成未解析引用。默认 150。")
    ap.add_argument("--no-nested", action="store_true", help="不检查嵌套 PDF 图")
    a = ap.parse_args(argv if argv is not None else sys.argv[1:])

    pdf = os.path.join(a.dir, "paper.pdf")
    if not os.path.exists(pdf):
        print("没有 %s" % pdf)
        return 2
    outdir = os.path.join(a.dir, "render")
    pages = render(pdf, outdir, a.dpi)
    if not pages:
        print("渲染失败（找不到 pdftoppm？）")
        return 2

    print("逐页视觉检查：%s" % pdf)
    print("  渲染 %d 页 -> %s" % (len(pages), outdir))
    print()
    print("  %-6s %-10s %-9s %s" % ("页", "墨迹密度", "大小", "判定"))
    bad = []
    for i, p in enumerate(pages, 1):
        r = ink_ratio(p)
        rb = ink_bottom(p)
        kb = os.path.getsize(p) / 1024.0
        if r is None:
            flag = "无法计算"
        elif r < INK_LOW:
            flag = "**近乎空白页**"
            bad.append((i, "空白", r))
        elif rb is not None and rb < 0.015 and i != len(pages):
            # 用下半部分判定：真正被分页浪费的页，下半几乎全空
            flag = "**半空页（下半空白）**"
            bad.append((i, "半空", rb))
        elif r > INK_HIGH:
            flag = "**过密（溢出风险）**"
            bad.append((i, "过密", r))
        else:
            flag = "正常"
        print("  %-6d %-10s %-9.0fKB %s"
              % (i, ("%.1f%%" % (100 * r)) if r is not None else "-", kb, flag))

    if a.no_nested:
        nested = []
    else:
        nested = nested_pdfs(os.path.join(a.dir, "paper.tex"))
    if nested:
        print()
        print("  嵌套 PDF 图（%d 个）：" % len(nested))
        for full in nested:
            if not os.path.exists(full):
                print("    [缺失] %s" % full)
                continue
            nd = os.path.join(outdir, "nested_" + os.path.basename(full)[:-4])
            np_ = render(full, nd, a.dpi)
            r = ink_ratio(np_[0]) if np_ else None
            flag = ""
            if r is not None and r < INK_LOW:
                flag = "  **图内近乎空白**"
                bad.append((os.path.basename(full), "图空白", r))
            print("    %-34s 墨迹 %s%s"
                  % (os.path.basename(full),
                     ("%.1f%%" % (100 * r)) if r is not None else "-", flag))

    # ── 嵌入位图的有效分辨率 ──
    imgs = embedded_images(pdf)
    if imgs is None:
        print("\n  嵌入位图：找不到 pdfimages，跳过 DPI 检查")
    elif imgs:
        print()
        print("  嵌入位图（%d 张，有效 DPI 决定印刷清晰度）：" % len(imgs))
        print("    %-6s %-12s %-8s %-8s %s"
              % ("页", "像素", "x-ppi", "y-ppi", "判定"))
        for im in imgs:
            lo = min(im["xppi"], im["yppi"])
            hi = max(im["xppi"], im["yppi"])
            if lo < 150:
                flag = "**偏低，印出来会糊**"
                bad.append(("p%d 图" % im["page"], "DPI 低", lo / 100.0))
            elif abs(hi - lo) / hi > 0.02:
                flag = "**x/y 比例不一致（可能被拉伸）**"
                bad.append(("p%d 图" % im["page"], "比例异常", lo / 100.0))
            elif lo >= 300:
                flag = "优秀"
            else:
                flag = "合格"
            print("    %-6d %-12s %-8.0f %-8.0f %s"
                  % (im["page"], "%dx%d" % (im["w"], im["h"]),
                     im["xppi"], im["yppi"], flag))
    else:
        print("\n  嵌入位图：无（全文图表均为矢量，或未嵌图）")

    print()
    if bad:
        print("  ⚠ 有 %d 处需要人眼确认：" % len(bad))
        for k, why, r in bad:
            print("     · %s（%s，墨迹 %.1f%%）" % (k, why, 100 * r))
        print()
        print("  这些只是「可疑」，判定仍要看图：")
        print("    空白页   -> 通常是一次 \\newpage / \\clearpage 事故")
        print("    过密页   -> 表格或图超出页宽，或图未裁边")
        print("  逐张看图：直接用图片查看器打开 %s 里的 PNG。" % outdir)
        return 1
    print("  未发现空白页或过密页。仍建议逐张过一遍图与表。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
