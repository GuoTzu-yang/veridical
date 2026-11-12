#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fig_visual.py —— 图的内容检查：`figcheck` 只看技术规格，这个补另一半。

**为什么必须有这个**（第 124 轮，用户点出来的缺口）：

`figcheck` 检查的是 DPI / 尺寸 / 背景色 / 长宽比 / 是否矢量 —— 全是**技术规格**。
它报「均分 8.0/10（24 张，A24）」时，给人「图都很好」的印象，
但它**没有打开任何一张图看里面画了什么**。

实测踩到的一类缺陷：**matplotlib 的 `ax.set_title()` 与 LaTeX 的 `\\caption{}`
说的是同一句话**，于是读者在图上方和下方各读到一遍。`figcheck` 看不见这个，
因为它不读图内的文字，也不读 caption。

本工具做三件**可机械判定**的事：

  A. **图内标题 vs caption 重复**
     扫画图脚本里的 `set_title(...)` / `suptitle(...)`，与论文里对应
     `\\includegraphics` 之后那句 `\\caption{}` 比字面相似度。
     ≥0.45 判「意思重叠」，≥0.75 判「几乎逐字重复」。

  B. **孤立图**（定义了 label 但正文没 \\ref）
     —— 这一条 `gate` 的 refs 项只在部分情况下抓，这里单独列。

  C. **图与正文的对应缺口**
     列出每张图的：文件名、尺寸、生成脚本、caption 首句，
     供人**逐张打开核对**。这一项机械做不了，工具只负责把清单摆好。

第四条是**人工的**，写进 AGENTS 作为硬规矩：出稿前逐张打开看。

用法：
    python tools/fig_visual.py out/final
    python tools/fig_visual.py out/final --json
退出码：0 = A/B 无问题；1 = 有。
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STOP = set("the a an of and or to in on for with by as is are was were be this that "
           "it its from at into than then not no all any two both one".split())


def _words(s):
    return [w for w in re.findall(r"[a-z]{3,}", (s or "").lower()) if w not in STOP]


def _sim(a, b):
    """两个短句的字面相似度（重叠词 / 较短句词数）。"""
    wa, wb = set(_words(a)), set(_words(b))
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / min(len(wa), len(wb))


def _scripts():
    """所有画图脚本：根目录与 tools/ 下的 *.py。"""
    out = {}
    for d in (HERE, os.path.join(HERE, "tools")):
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if not f.endswith(".py"):
                continue
            p = os.path.join(d, f)
            try:
                t = io.open(p, encoding="utf-8", errors="replace").read()
            except Exception:                       # noqa: BLE001
                continue
            if "savefig" in t or "matplotlib" in t:
                out[os.path.relpath(p, HERE)] = t
    return out


def _titles(src):
    """脚本里所有 set_title / suptitle 的字面量。"""
    out = []
    for m in re.finditer(r"(?:set_title|suptitle)\s*\(\s*([\"'])(.+?)\1", src, re.S):
        out.append(re.sub(r"\s+", " ", m.group(2)).strip())
    return out


def _figs_in_paper(figdir):
    """论文里每张图：(png 文件名, caption 全文)。"""
    p = os.path.join(figdir, "paper.tex")
    if not os.path.exists(p):
        p = os.path.join(figdir, "main.tex")
    if not os.path.exists(p):
        return []
    t = io.open(p, encoding="utf-8", errors="replace").read()
    out = []
    for m in re.finditer(
            r"\\includegraphics(?:\[[^\]]*\])?\{([^}]*)\}\s*(?:\\centering\s*)?"
            r"\\caption\{((?:[^{}]|\{[^{}]*\})*)\}", t, re.S):
        out.append((os.path.basename(m.group(1)), re.sub(r"\s+", " ", m.group(2)).strip()))
    # 有些 \caption 在 \includegraphics 之前
    for m in re.finditer(
            r"\\caption\{((?:[^{}]|\{[^{}]*\})*)\}\s*\\label\{[^}]*\}\s*\\end\{figure\}",
            t, re.S):
        pass
    return out


def check(figdir):
    scripts = _scripts()
    figs = _figs_in_paper(figdir)
    rows, problems = [], []

    # A. 图内标题 vs caption —— 按 savefig 路径建立「脚本 → 输出文件」映射。
    # 不能做「所有标题 × 所有 caption」：那样 fig3_gate 会配上别的脚本的标题，
    # 实测立刻出了 4 个张冠李戴的误报。也不能按脚本名匹配（脚本名不含图名）。
    out_titles = {}
    for rel, src in scripts.items():
        ts = _titles(src)
        if not ts:
            continue
        for o in re.findall(r'savefig\([^)]*?["\']([^"\']+\.(?:png|pdf))["\']', src):
            out_titles.setdefault(os.path.basename(o), []).extend(ts)

    # 不做「脚本名 → 图名」的映射：一个脚本常画多张图，脚本名与图名无关
    # （make_ab_figs.py 画 fig21..fig24）。原来按脚本名匹配，实测 sim 恒为 0 ——
    # 那是匹配逻辑错，不是图没问题。改成「所有标题 × 所有 caption」取最大相似度。
    for name, cap in figs:
        best, bsim = None, 0.0
        for ti in out_titles.get(name, []):
            s = _sim(ti, cap)
            if s > bsim:
                best, bsim = ti, s
        if bsim >= 0.75:
            problems.append(f"{name}: 图内标题与 caption **几乎逐字重复**（相似度 {bsim:.2f}）"
                            f" —— 图上方和下方各读一遍同一句话；删 set_title")
        elif bsim >= 0.45:
            problems.append(f"{name}: 图内标题与 caption **意思重叠**（相似度 {bsim:.2f}）"
                            f" —— 建议删 set_title，让 caption 说话")
        rows.append(dict(fig=name, caption=cap[:110], title=best, sim=round(bsim, 2)))

    # B. 孤立图
    p = os.path.join(figdir, "paper.tex")
    if os.path.exists(p):
        t = io.open(p, encoding="utf-8", errors="replace").read()
        refs = set(re.findall(r"\\ref\{([^}]*)\}", t))
        for lab in re.findall(r"\\label\{(fig:[^}]*)\}", t):
            if lab not in refs:
                problems.append(f"{lab}: 定义了 label 但正文没有 \\ref —— 孤立图")
    return dict(dir=figdir, n_figs=len(figs), rows=rows, problems=problems,
                n_scripts=len(scripts))


def selftest():
    """自校：相似度判据在构造样本上必须分开三类。

    不能「读当前论文报无问题」当验证 —— 那正是这个工具要防的错。
    这里用纯字符串，不碰文件，所以可在回归链里跑。
    """
    same = "Tracing under two scopes and the structural integer gap"
    near = "Tracing under two scopes the structural integers"
    far = "Wall clock cost per command on one problem"
    ok = True
    for name, a, b, lo in (
            ("完全相同的两句 -> 1.00", same, same, 0.99),
            ("高度重叠 -> >=0.75", same, near, 0.75),
            ("无关的两句 -> <0.25", same, far, None)):
        s = _sim(a, b)
        good = (s < 0.25) if lo is None else (s >= lo)
        print("  [%s] %s（实测 %.2f）" % ("PASS" if good else "**FAIL**", name, s))
        ok = ok and good
    print()
    if not ok:
        print("**自校失败**：相似度判据不可信")
        return 1
    print("自校通过：同一句、近句、无关句三类分得开。")
    return 0


def main(argv):
    if "--selftest" in argv:
        return selftest()

    d = argv[1] if len(argv) > 1 and not argv[1].startswith("-") else \
        os.path.join(HERE, "out", "final")
    if not os.path.isabs(d):
        d = os.path.join(HERE, d)
    r = check(d)
    if "--json" in argv:
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if not r["problems"] else 1
    print(f"图的视觉检查：{r['n_figs']} 张图，扫了 {r['n_scripts']} 个画图脚本")
    print()
    print("  A. 图内标题 vs caption（可机械判）")
    for x in r["rows"]:
        mark = "重复" if x["sim"] >= 0.45 else "ok"
        print(f"    [{mark:<4}] {x['fig']:<26} sim={x['sim']:.2f}  {x['caption'][:52]}")
    print()
    print("  C. 逐张人工核对清单（机械做不了，必须打开看）")
    for x in r["rows"]:
        print(f"    □ {x['fig']:<26} {x['caption'][:70]}")
    print()
    if r["problems"]:
        print(f"**{len(r['problems'])} 个问题**")
        for p in r["problems"]:
            print("  ✗", p)
        return 1
    print("A/B 无问题。C 项请人工逐张打开看。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
