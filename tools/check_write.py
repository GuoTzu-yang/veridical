#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_write.py —— 写后校验：文件里有没有被转义污染的控制字符（第 124 轮）。

**为什么需要这个工具**

本项目的所有写文件操作，有一半是经 PowerShell 的 heredoc (`@"..."@`) 传给
python 的。PowerShell 用反引号做转义，于是这些字符会被静默改写：

    `a  ->  BEL (\\x07)          `t  ->  TAB (\\x09)
    `n  ->  LF                   `0  ->  NUL
    `$  ->  $（这个碰巧对）

实测踩到的四次：

    1. `aidc2026` 在 README 里变成 `<BEL>idc2026`
    2. `tab:ablation` 在大纲里变成 `<TAB>ab:ablation`
    3. `.Replace(a, b, 1)` —— .NET 的 String.Replace 只有两个参数
    4. `$git: $git` —— `$git:` 被当成驱动器限定符

**前两个是本工具能抓的**：它们留下的是控制字符，而控制字符在文本里没有理由出现。

**规矩**（写进 AGENTS）：含反斜杠、反引号、引号的内容，用 write 工具直接写，
不经过 shell。这个工具是那条规矩的兜底，因为规矩靠记会忘。

用法：
    python tools/check_write.py FILE [FILE...]
    python tools/check_write.py --dir out/final
    python tools/check_write.py --selftest
退出码：0 = 干净；1 = 有污染。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 文本文件的后缀（二进制不扫）
TEXT_EXT = {".md", ".tex", ".py", ".json", ".txt", ".yml", ".yaml",
            ".html", ".css", ".js", ".ps1", ".cfg", ".ini", ".csv"}

# 任何文本文件都不该出现的控制字符
FORBIDDEN = {
    "\x07": "BEL（PowerShell 的 `a）",
    "\x00": "NUL（PowerShell 的 `0）",
    "\x08": "BS（`b）",
    "\x0c": "FF（`f）",
    "\x1b": "ESC",
    "\u200b": "零宽空格",
    "\u200c": "零宽非连接符",
    "\u200d": "零宽连接符",
    "\ufeff": "BOM（只允许出现在文件最开头）",
}

# 只在某些后缀里允许 TAB
TAB_ALLOWED = {".py", ".ps1", ".yml", ".yaml", ".cfg", ".ini", ".tex"}


def scan(path):
    """返回 (问题列表, 统计)。问题是一条 6 元组 (行号, 列号, 字符, 说明, 上下文)。"""
    probs = []
    try:
        raw = io.open(path, "rb").read()
    except Exception as e:                                  # noqa: BLE001
        return [(-1, -1, "", "打不开：%s" % e, "")], {}
    # UTF-16 BOM：PowerShell 的 `>` 重定向默认写 UTF-16，这是本机实测到的
    # 一大类污染（out/ 下 48 个 .txt 就是这样）。它让文件"能读"但内容全变。
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        enc = "UTF-16 LE" if raw[:2] == b"\xff\xfe" else "UTF-16 BE"
        return [(-1, -1, "UTF-16BOM",
                 "文件是 %s（PowerShell 重定向的默认编码），不是 UTF-8" % enc,
                 "")], {"binary": False}
    if b"\x00" in raw[:4096] and path.lower().endswith((".png", ".pdf", ".zip")):
        return [], {"binary": True}
    try:
        t = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        probs.append((-1, -1, "", "不是合法 UTF-8：%s" % e, ""))
        return probs, {"binary": False}

    ext = os.path.splitext(path)[1].lower()
    n_tab = 0
    n_cr = 0
    n_lf = 0

    for lineno, line in enumerate(t.split("\n"), 1):
        if line.endswith("\r"):
            n_cr += 1
        for col, ch in enumerate(line, 1):
            if ch == "\t":
                n_tab += 1
                if ext not in TAB_ALLOWED:
                    probs.append((lineno, col, "TAB",
                                  "在 %s 里不该有 TAB（PowerShell 的 `t）" % ext,
                                  line.strip()[:50]))
                continue
            if ch in FORBIDDEN:
                probs.append((lineno, col, repr(ch), FORBIDDEN[ch], line.strip()[:50]))
    n_lf = t.count("\n")

    # BOM 只允许在开头
    if t.startswith("\ufeff"):
        t2 = t[1:]
        if "\ufeff" in t2:
            probs.append((0, 0, "BOM", "BOM 出现在文件内部", ""))

    # CR 与 LF 混用
    if n_cr and n_cr != n_lf and n_lf:
        probs.append((-1, -1, "CRLF", "CR 与 LF 混用（%d 个 CR，%d 个 LF）" % (n_cr, n_lf), ""))

    return probs, {"binary": False, "tabs": n_tab, "cr": n_cr, "lf": n_lf}


def walk(d):
    out = []
    for root, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if x not in ("__pycache__", ".git", "external", "node_modules")]
        for f in files:
            if os.path.splitext(f)[1].lower() in TEXT_EXT:
                out.append(os.path.join(root, f))
    return out


SAMPLES = [
    ("tab_in_md", "out/_probe_clean.md", "# ok\n\n| a | b |\n|---|---|\n| 1 | 2 |\n"),
    ("tab_bad", "out/_probe_tab.md", "# ok\n\n| a |\tb |\n|---|---|\n| 1 | 2 |\n"),
    ("bel_bad", "out/_probe_bel.md", "# ok\n\n见 `aidc2026` 这段\n".replace("`a", "\x07")),
    ("zwsp_bad", "out/_probe_zw.md", "# ok\n\n隐\u200b藏\n"),
]


def selftest():
    """构造缺陷：干净样本必须过，三个污染样本必须被抓。"""
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    ok = True
    for name, rel, content in SAMPLES:
        p = os.path.join(HERE, rel)
        io.open(p, "w", encoding="utf-8", newline="").write(content)
        probs, _ = scan(p)
        os.remove(p)
        want = name == "tab_in_md"
        good = (len(probs) == 0) == want
        ok = ok and good
        print("  [%s] %-10s 问题 %d 个（期望%s）%s"
              % ("PASS" if good else "**FAIL**", name, len(probs),
                 "0" if want else ">0",
                 "" if not probs else "  |  " + probs[0][3][:40]))
    print()
    if not ok:
        print("**自校失败**：判据坏了")
        return 1
    print("自校通过：干净样本放行，TAB/BEL/零宽三类都抓住。")
    return 0


def main(argv):
    if not argv or argv[0] == "--selftest":
        return selftest()

    if argv[0] == "--dir":
        targets = walk(os.path.join(HERE, argv[1]) if not os.path.isabs(argv[1]) else argv[1])
    else:
        targets = [a if os.path.isabs(a) else os.path.join(HERE, a) for a in argv]

    total = 0
    bad_files = 0
    for p in targets:
        probs, _ = scan(p)
        if probs:
            bad_files += 1
            total += len(probs)
            print("**%s**" % os.path.relpath(p, HERE))
            for lineno, col, ch, why, ctx in probs[:6]:
                print("  L%-4s C%-3s %-6s %s" % (lineno, col, ch, why))
                if ctx:
                    print("        | %s" % ctx)
            if len(probs) > 6:
                print("  ……另有 %d 处" % (len(probs) - 6))

    print()
    print("扫了 %d 个文件，%d 个有污染，共 %d 处" % (len(targets), bad_files, total))
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
