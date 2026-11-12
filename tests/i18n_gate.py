#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多语言回归：CJK 总闸不许再无条件生效。

背景
----
第 57 轮抓到：mmkit.py 里那道「残留中文一律替成 variable」的总闸，
是为热沉题的 ASCII 约束加的（中文列名漏进 tex 会产生 23 个编译错误）。
但它**无条件**生效，于是 --lang zh 刚被 _localize 换成中文的章节标题
又被替回 variable —— 多语言功能被自己加的安全网闷死，而且静默。

为什么要有这条测试
----------------
多语言不是主力路径，热沉题永远正常。**没有测试，这个 bug 会立刻复发**，
而且复发时没人看得出来（英文稿完全正常）。

本测试不编译 —— 中文排版需要 ctex/xeCJK，本机 MiKTeX 没装。
只查 tex 内容，够抓这类回归。
"""
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
CJK = re.compile(r"[\u4e00-\u9fff]+")
SECT = re.compile(r"\\section\*?\{([^}]*)\}")


def run(lang, texdir, data):
    os.makedirs(texdir, exist_ok=True)
    r = subprocess.run(
        [PY, "mmkit.py", "run", "--data", data,
         "--y", "产量", "--x", "反应温度,操作压力",
         "--min", "产量,能耗,次品率",
         "--tex", os.path.join(texdir, "paper.tex"),
         "--team", "2612345", "--problem", "chemical reactor yield",
         "--lang", lang, "--no-gate"],
        capture_output=True, text=True, encoding="utf-8",
        errors="replace", cwd=HERE)
    p = os.path.join(texdir, "paper.tex")
    if not os.path.exists(p):
        return None, r.stdout or ""
    return open(p, encoding="utf-8").read(), r.stdout or ""


def main():
    tmp = os.path.join(HERE, "out", "i18n_test")
    shutil.rmtree(tmp, ignore_errors=True)
    data = os.path.join(HERE, "out", "data", "scope_test.xlsx")
    bad = 0

    # ① --lang zh：章节标题应是中文，不能是 variable
    tex, out = run("zh", os.path.join(tmp, "zh"), data)
    if tex is None:
        print("  [FAIL] zh 没有产出 tex")
        bad += 1
    else:
        secs = SECT.findall(tex)
        zh_secs = [s for s in secs if CJK.search(s)]
        var_secs = [s for s in secs if s.strip() == "variable"]
        n_cjk = len(CJK.findall(tex))
        ok = bool(zh_secs) and not var_secs
        if not ok:
            bad += 1
        print("  [%s] zh: 章节 %d 个（中文 %d / variable %d），"
              "全文中文片段 %d 处"
              % ("PASS" if ok else "FAIL", len(secs), len(zh_secs),
                 len(var_secs), n_cjk))
        if var_secs:
            print("        variable 标题说明 CJK 总闸又无条件生效了")
        print("        中文标题例: %s" % (zh_secs[0][:24] if zh_secs else "-"))
        if "\u9700\u8981\u5b8f\u5305" not in out:
            print("  [WARN] zh 没报缺宏包（缺 ctex 时应明确说出来）")

    # ② --lang en：全文 0 处中文
    tex, _ = run("en", os.path.join(tmp, "en"), data)
    if tex is None:
        print("  [FAIL] en 没有产出 tex")
        bad += 1
    else:
        n = len(CJK.findall(tex))
        ok = n == 0
        if not ok:
            bad += 1
        print("  [%s] en: 全文中文残留 %d 处（应为 0）"
              % ("PASS" if ok else "FAIL", n))

    shutil.rmtree(tmp, ignore_errors=True)
    print()
    print("%s  %d/2" % ("ALL PASS" if bad == 0 else "FAILED", 2 - bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())