"""一页页看：逐页量 PDF 的可读性。

按用户要求「pdf 也要一页页看，保证不出问题」——把「看」变成可测的数：
  · 每页字符数（文字密度，太密=解析力低）
  · 每页图数与图的像素尺寸（换算成实际 DPI，太低=看不清）
  · 最小字号（取自 pdffonts，字体越小越难读）
判定阈值只用于**标出可疑页**，不替人下结论。
"""
import io
import json
import os
import re
import subprocess
import sys

PDFINFO = r"C:\Users\21246\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdfinfo.exe"
PDFFONTS = r"C:\Users\21246\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdffonts.exe"


def page_geometry(pdf):
    try:
        out = subprocess.run([PDFINFO, pdf], capture_output=True, text=True,
                             encoding="utf-8", errors="replace",
                             timeout=60).stdout
        pages = int(re.search(r"Pages:\s+(\d+)", out).group(1))
        size = re.search(r"Page size:\s+([\d.]+) x ([\d.]+)", out)
        w, h = (float(size.group(1)), float(size.group(2))) if size else (0, 0)
        return pages, w, h
    except Exception as e:
        return None, 0, 0


def font_sizes(pdf):
    """从内容流里量实际字号分布。

    pdffonts 在这份 PDF 上不给「attribute」列（Type 1 子集只有 object ID），
    拿不到字号。改用 pypdf 的文本 visitor：它给每个文本片段的变换矩阵，
    矩阵里的缩放即字号。

    只报**最小值**没有意义（数学下标、页码都是 1pt 级别），
    要报的是「有多少比例的字小于 9pt」—— 那才是「看不看得清」。
    """
    sizes = []
    try:
        from pypdf import PdfReader
        rd = PdfReader(pdf)
        for pg in rd.pages:
            def _visit(text, cm, tm, font_dict, font_size):
                if text and text.strip():
                    # 用 visitor 给的 font_size；tm[3] 在这份 PDF 上恒为 1
                    s = 0.0
                    try:
                        s = float(font_size)
                    except (TypeError, ValueError):
                        try:
                            s = float(tm[3])
                        except Exception:
                            s = 0.0
                    if s > 0:
                        sizes.append((round(s, 1), len(text.strip())))
            pg.extract_text(visitor_text=_visit)
    except Exception:
        return []
    return sizes


def pages_detail(pdf):
    """逐页：文字量 + 每张嵌入图的像素尺寸与等效 DPI。

    「解析力低」说的是图的分辨率，不是字号。图的等效 DPI =
    像素宽 / 摆放宽度（英寸）。摆宽未知时按常见图宽 12cm ≈ 4.7in 估。
    """
    from pypdf import PdfReader
    rd = PdfReader(pdf)
    rows = []
    for i, pg in enumerate(rd.pages, 1):
        try:
            txt = pg.extract_text() or ""
        except Exception:
            txt = ""
        imgs = []
        try:
            for im in (pg.images or []):
                w = h = 0
                try:
                    pil = im.image
                    w, h = pil.size
                except Exception:
                    try:
                        w, h = im._xobj.get_width(), im._xobj.get_height()
                    except Exception:
                        w, h = 0, 0
                imgs.append((im.name, len(im.data), int(w), int(h)))
        except Exception:
            pass
        rows.append(dict(page=i, chars=len(txt.strip()), imgs=imgs))
    return rows


def main():
    pdfs = sys.argv[1:]
    if not pdfs:
        pdfs = [r"C:\Users\21246\Desktop\Plugin-Agent-Architecture.pdf"]
    for pdf in pdfs:
        if not os.path.exists(pdf):
            print("不存在:", pdf)
            continue
        pages, w, h = page_geometry(pdf)
        fs = font_sizes(pdf)
        rows = pages_detail(pdf)
        tot = sum(c for _s, c in fs) or 1
        small = sum(c for s, c in fs if s < 9.0)
        body = sorted({s for s, _c in fs})
        print("=" * 78)
        print("%s" % pdf)
        print("  页数 %s  页面 %.0f x %.0f pt" % (pages, w, h))
        print("  字号分布: 出现过 %d 种（%s …）  小于 9pt 的字占 %.2f%%"
              % (len(body), ", ".join(str(x) for x in body[:6]), 100.0 * small / tot))
        print("  逐页：页  字符数  图  最小图宽(px)  等效DPI@12cm")
        dense = []
        lowdpi = []
        for r in rows:
            flag = ""
            if r["chars"] > 3200:
                flag = "  ← 文字过密"
                dense.append(r["page"])
            widths = [w for _n, _b, w, _h in r["imgs"] if w]
            mn = min(widths) if widths else 0
            dpi = (mn / 4.72) if mn else 0
            if dpi and dpi < 150:
                flag += "  ← 图偏糊"
                lowdpi.append((r["page"], mn, round(dpi)))
            print("   %3d  %6d  %2d  %10s  %10s%s"
                  % (r["page"], r["chars"], len(r["imgs"]),
                     mn if mn else "-", round(dpi) if dpi else "-", flag))
        print("  文字过密的页:", dense if dense else "无")
        print("  图低于 150DPI 的页:", lowdpi if lowdpi else "无")
        print()


if __name__ == "__main__":
    main()
