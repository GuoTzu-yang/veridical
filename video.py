#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
video.py —— 把建模流程做成动画（第 88 轮建）

为什么做这个
------------
用户明确要「流程视频」。本机没有 ffmpeg（在装），但 Pillow 12.3 能写多帧 GIF，
所以先用 GIF 保证**一定有产物**，ffmpeg 到位后再升级 MP4。

设计取舍
--------
不做"幻灯片轮播"——那只是把图连起来，没有信息增量。
每帧都带三样东西：
  1. 当前阶段的图（或数据快照）
  2. 阶段名与序号（观众知道进行到哪一步）
  3. **这一阶段的真实数字**（不是装饰，是从分析结果里取出来的）

这样视频本身就是一份可读的分析摘要，而不是装饰品。
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
]

BAR_H = 74          # 顶部信息条高度
PAD = 26


def _font(size: int):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _fit(img: Image.Image, w: int, h: int) -> Image.Image:
    """等比缩放进 (w,h)，不足处补白。不拉伸——拉伸会让坐标轴失真。"""
    r = min(w / img.width, h / img.height)
    nw, nh = max(1, int(img.width * r)), max(1, int(img.height * r))
    out = img.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", (w, h), (255, 255, 255))
    canvas.paste(out, ((w - nw) // 2, (h - nh) // 2))
    return canvas


def build_frames(steps: list[dict], size: tuple[int, int] = (1280, 800),
                 hold: int = 1) -> list[Image.Image]:
    """steps: [{title, image(路径或None), note, text_only}]"""
    W, H = size
    frames = []
    n = len(steps)
    for i, st in enumerate(steps, 1):
        canvas = Image.new("RGB", (W, H), (252, 252, 253))
        d = ImageDraw.Draw(canvas)

        # ---- 顶部信息条 ----
        d.rectangle([0, 0, W, BAR_H], fill=(28, 42, 58))
        d.text((PAD, 14), f"Step {i}/{n}", font=_font(22),
               fill=(150, 200, 255))
        d.text((PAD + 130, 12), str(st.get("title", "")),
               font=_font(26), fill=(255, 255, 255))

        # ---- 进度条 ----
        bw = W - 2 * PAD
        d.rectangle([PAD, BAR_H - 8, PAD + bw, BAR_H - 3], fill=(52, 66, 84))
        d.rectangle([PAD, BAR_H - 8,
                     PAD + int(bw * i / n), BAR_H - 3], fill=(80, 180, 255))

        # ---- 主体 ----
        top = BAR_H + PAD
        note = str(st.get("note", ""))
        note_lines = _wrap(note, 46)[:6] if note else []
        note_h = len(note_lines) * 30 + (16 if note_lines else 0)

        img_path = st.get("image")
        if img_path and os.path.exists(img_path):
            body_h = H - top - note_h - PAD
            with Image.open(img_path) as im:
                im = im.convert("RGB")
                canvas.paste(_fit(im, W - 2 * PAD, body_h), (PAD, top))
        else:
            # 没有图也没有大字时**不能留白** —— 留白等于告诉观众
            # 这一步没有内容，但实际是图没生成。必须说清楚。
            big = str(st.get("big", "")).strip()
            if big:
                y = top + 40
                for ln in big.split("\n"):
                    d.text((PAD + 10, y), ln, font=_font(34),
                           fill=(30, 40, 55))
                    y += 46
            else:
                d.rectangle([PAD, top + 30, W - PAD, top + 190],
                            outline=(200, 90, 90), width=3)
                d.text((PAD + 24, top + 62),
                       "[no figure for this step]",
                       font=_font(30), fill=(170, 60, 60))
                d.text((PAD + 24, top + 108),
                       "run mmkit plot to generate it",
                       font=_font(22), fill=(120, 60, 60))

        # ---- 底部说明（真实数字在这里）----
        if note_lines:
            y = H - PAD - note_h + 8
            for ln in note_lines:
                d.text((PAD, y), ln, font=_font(21), fill=(70, 80, 95))
                y += 30
        frames.append(canvas)

    # 每个阶段多停几帧，否则看不清
    if hold > 1:
        out = []
        for f in frames:
            out.extend([f] * hold)
        return out
    return frames


def _wrap(s: str, width: int) -> list[str]:
    """按显示宽度折行（中文按 2 计）。"""
    out, cur, w = [], "", 0
    for ch in s:
        cw = 2 if ord(ch) > 0x2E80 else 1
        if w + cw > width:
            out.append(cur)
            cur, w = ch, cw
        else:
            cur += ch
            w += cw
    if cur:
        out.append(cur)
    return out


def save_gif(frames: list[Image.Image], out: str, ms: int = 900) -> dict:
    """存 GIF。调色板量化到 256 色——否则文件会大到几十 MB。"""
    if not frames:
        return dict(path=None, why="没有帧")
    pal = [f.convert("P", palette=Image.ADAPTIVE, colors=256) for f in frames]
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    pal[0].save(out, save_all=True, append_images=pal[1:],
                duration=ms, loop=0, optimize=True)
    return dict(path=out, frames=len(frames), ms=ms,
                bytes=os.path.getsize(out))


def save_mp4(frames: list[Image.Image], out: str, fps: int = 2) -> dict:
    """用 ffmpeg 转 MP4。没有 ffmpeg 就返回 None，不报错。"""
    import shutil
    import subprocess
    import tempfile

    # 先找 PATH，再找 imageio_ffmpeg 自带的二进制 ——
    # 后者的意义：GitHub 被墙时装不上 ffmpeg，但 PyPI 通，这一条是唯一可行的通路。
    exe = shutil.which("ffmpeg")
    if not exe:
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:                              # noqa: BLE001
            exe = None
    if not exe or not os.path.exists(exe):
        return dict(path=None,
                    why="ffmpeg 不可用（PATH 与 imageio_ffmpeg 都没找到）")
    td = tempfile.mkdtemp(prefix="vid_")
    for i, f in enumerate(frames):
        f.save(os.path.join(td, f"f{i:05d}.png"))
    cmd = [exe, "-y", "-framerate", str(fps), "-i",
           os.path.join(td, "f%05d.png"),
           "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", out]
    r = subprocess.run(cmd, capture_output=True, timeout=600)
    if r.returncode != 0:
        return dict(path=None,
                    why="ffmpeg 失败: " +
                        (r.stderr or b"").decode("utf-8", "replace")[-160:])
    return dict(path=out, frames=len(frames), fps=fps,
                bytes=os.path.getsize(out))
