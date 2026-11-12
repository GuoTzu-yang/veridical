#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify.py —— 数字溯源：论文里的每个数字必须来自插件（第 150 轮建）

为什么这是最重要的一道闸门
--------------------------
LLM 最危险的不是「想错」，是「编数字」。
一个编出来的 R²=0.85 会让整篇论文的论证建立在假数据上，
而且**看起来完全正常** —— 这是肉眼看不出来的错。

做法
----
1. 从 .tex 里抽出所有数字（排除页数、年份、文献编号、公式编号）
2. 从插件的结构化输出里抽出所有数字
3. 差集 = 未溯源数字

只做**双向容差匹配**：0.00743 和 0.0074342 视为同一个数
（论文里通常保留 3-5 位有效数字）。
"""

from __future__ import annotations

import json
import os
import re

# 论文里这些数字不需要溯源（版式与引用，不是计算结果）
SKIP_PATTERNS = [
    r"\\section", r"\\subsection", r"\\label", r"\\ref", r"\\cite",
    r"\\bibitem", r"\\begin", r"\\end", r"\\usepackage", r"\\documentclass",
    r"\\includegraphics", r"\\caption", r"\\item",
]
# 文献年份、页数、编号常见范围
PLAUSIBLE_META = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 16, 24, 30, 31, 365}


def _strip_noise(line: str) -> str:
    """剥掉版式命令，但**不整行丢弃**。

    第 110 轮（红队 F1 的连带发现）：原来只要行里出现 `\\begin`/`\\end`
    这类命令，整行就被返回空串。于是
      · 单行 tex（整个正文和 `\\begin{document}` 在同一行）→ 0 个候选
        → 溯源率 100% → 空洞通过；
      · 正文里提到 `\\begin{itemize}` 的段落 → 整段数字不受检查。
    现在的做法：把命令及其参数换成空格，行里若还剩内容就继续抽取。
    """
    s = line
    for pat in SKIP_PATTERNS:
        # 带参数的形态：\cmd{...} / \cmd[...]{...}
        s = re.sub(pat + r"\*?(?:\[[^\]]*\])?\{[^{}]*\}", " ", s)
        # 裸命令形态
        s = re.sub(pat + r"\*?", " ", s)
    if not re.search(r"[0-9]", s):
        return ""
    # LaTeX 的区间写法 0.19--0.57 / 1965--1970：`--` 是破折号不是减号。
    # 不处理时，正则会在 "0.19--0.57" 里抽出 "0.19" 和 "-0.57"，
    # 后一个是幻觉数（原文并没有 -0.57 这个值）。
    s = re.sub(r"(?<=[\d.])--(?=[\d.])", " ", s)
    s = re.sub(r"(?<=[\d.])\u2013(?=[\d.])", " ", s)      # en dash
    s = re.sub(r"(?<=[\d.])\u2014(?=[\d.])", " ", s)      # em dash
    return s


def _blank_multiline_args(text: str) -> str:
    r"""把**跨行**的 \cmd{...} 参数抹成等长空格，保留换行。

    为什么要这一步：`extract_numbers` 逐行处理，而
    `\geometry{a4paper, left=3.0cm, right=3.0cm,\n  top=2.8cm, ...}`
    的闭合括号在下一行，所以单行正则永远匹配不上，`2.8` 就被当成
    「论文里的一个数」报无出处 —— 那是版面参数，不是主张。
    抹成空格而不是删除：行号与列位置不变，报错上下文仍然对得上。
    """
    def _repl(m):
        head, inner = m.group(1), m.group(2)
        return head + "{" + re.sub(r"[^\n]", " ", inner) + "}"

    return re.sub(r"(\\[a-zA-Z]+\*?(?:\[[^\]]*\])?)\{((?:(?!\{|\})[\s\S])*)\}",
                  _repl, text)


def extract_numbers(text: str, skip_meta: bool = True) -> list[tuple[str, str]]:
    """抽出 (原始字符串, 行) —— 保留原文以便报错时定位。"""
    out = []
    # 前导区（\begin{document} 之前）全是宏定义与版面参数：
    # \definecolor{ink}{HTML}{8A3324}、\@startsection{-2.4ex\@plus…}、
    # \geometry{top=2.8cm}。它们不是论文主张，先整段切掉再数。
    # 保留行数：用等量空行替换，报错时的行号仍指得回去。
    m = re.split(r"(\\begin\{document\})", text, maxsplit=1)
    if len(m) == 3:
        head, _mark, body = m
        text = re.sub(r"[^\n]", " ", head) + _mark + body
    # 参考文献条目里的卷期页码没有计算出处，也不该有（第 110 轮，红队 F2 的一半）：
    # 27(2)、97--111、arXiv:2211.09527 是文献元数据，不是本论文的结果。
    # 把它们整段抹掉，而不是记成「未溯源」——否则每篇有引用的论文都被扣分。
    text = re.sub(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}",
                  " ", text, flags=re.S)
    # 表格列宽这类**版式参数**不是主张：\begin{tabular}{@{}llL{8.4cm}@{}}
    # 里的 8.4 若是被当数字，每篇有自定义列宽的论文都被扣分（第 111 轮）。
    for _env in ("tabular", "array", "tabularx"):
        text = re.sub(r"\\\\begin\\{" + _env + r"\\}\\{[^{}]*\\}", " ",
                      text)
    # 列宽这类版式参数：L{8.4cm} / p{6.6cm} / m{2cm}（嵌套括号，单独处理）
    text = re.sub(r"[LpmbX]\\{\\s*[\\d.]+\\s*(?:cm|mm|pt|em)\\s*\\}", " ", text)
    text = _blank_multiline_args(text)
    for line in text.splitlines():
        s = _strip_noise(line)
        if not s:
            continue
        # 去掉 \ref{...} \cite{...} 里的内容
        s = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?\{[^{}]*\}", " ", s)
        # ── 分词前先做三项归一（第 110 轮，见下）──
        # 原来的 `-?\d+(?:\.\d+)?` 会把三类正常数字切碎，
        # 于是「切碎的碎片」被当成「没有出处的数字」，直接压低了溯源率：
        #   ① 科学计数法 3.3342e-12  →  "3.3342" 与 "-12"
        #   ② 年份区间   1970-1975   →  "1970" 与 "-1975"（负号被当减号）
        #   ③ 千分位     51,737      →  "51" 与 "737"
        # 这不是论文写错，是**度量本身**错 —— 正是本文要抓的那类缺陷。
        s = re.sub(r"(\d{4})\s*[-\u2013\u2014]\s*(\d{4})", r"\1 \2", s)
        s = re.sub(r"(?<=\d),(?=\d{3}\b)", "", s)
        # ④ LaTeX 千分位 10{,}233 / 10\,233 → 10233（第 112 轮）。
        #    不还原的话会被切成 "10" 与 "233" 两个无源数字。
        s = re.sub(r"(?<=\d)\{,\}(?=\d{3})", "", s)
        s = re.sub(r"(?<=\d)\\?,(?=\d{3}\b)", "", s)
        # ⑤ 列宽这类版式参数：L{8.4cm} / p{6.6cm}（嵌套括号，单独处理）
        s = re.sub(r"[LpmbX]\{\s*[\d.]+\s*(?:cm|mm|pt|em)\s*\}", " ", s)
        for m in re.finditer(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", s):
            tok = m.group(0)
            try:
                v = float(tok)
            except ValueError:
                continue
            if skip_meta and v in PLAUSIBLE_META:
                continue
            out.append((tok, line.strip()[:80]))
    return out


def _decimals(x: float) -> int:
    """这个数写出了几位小数（用 repr，避开科学计数法）。"""
    r = repr(float(x))
    if "e" in r or "E" in r:
        # 1e-05 这类：按有效位数算
        mant = r.split("e")[0].split("E")[0]
        return len(mant.replace("-", "").replace(".", "").lstrip("0"))
    if "." not in r:
        return 0
    return len(r.split(".")[1])


def _written_decimals(tok: str) -> int | None:
    """按**论文里写出来的样子**数精度。这是全项目唯一的实现。

    第 122 轮（红队独立诊断 §3.5c）：交接文件说「单一分词器」已经统一了
    两套口径，其实只统一了 **token 集合**，没统一 **精度** ——
    `freeze.check_paper` 用 `freeze._decimals`，`verify.trace` 用
    `verify._written_decimals`。同一份产物于是出现
    「gate PASS 116/116、verify 报 88.0%」这种自相矛盾。
    现在 freeze._decimals 直接委托本函数，只剩这一处。

    科学计数法必须按**有效位数**换算，返回值可以是负数：
        "5.924e+04" → -1（最低位在十位）
        "1.96e-11"  → 13
    原来遇到 `e` 直接返回 None，调用方退回 `repr(float)` 的小数位
    （"15410.0" → 1 位），于是 15409.069 写的 1.541e+04 判不过。
    """
    t = str(tok).strip().replace("\u2212", "-").rstrip("%").replace(",", "")
    m = re.fullmatch(r"([+-]?)(\d+)(?:\.(\d+))?[eE]([+-]?\d+)", t)
    if m:
        intpart = m.group(2)
        frac = m.group(3) or ""
        exp = int(m.group(4))
        digits = len(intpart.lstrip("0") or "0") + len(frac)
        return digits - 1 - exp
    return len(t.split(".")[1]) if "." in t else 0


def _near(a: float, b: float, decimals: int | None = None) -> bool:
    """论文里的 a 能不能由输出里的 b 解释。

    一条判据：**a 必须是 b 按 a 的小数位舍入的结果**。

        round(b, decimals(a)) == a

    它同时挡住两种作弊，又放过真实舍入：

      真实舍入   a=0.00743(5位)  b=0.0074342   round(b,5)=0.00743   ✓
      编个高分   a=0.9999(4位)   b=1.0         round(1.0,4)=1.0     ✗
      改第 3 位  a=0.9999(4位)   b=0.9975      round(0.9975,4)≠a    ✗

    关键是 round 不会「补精度」：1.0 舍到 4 位还是 1.0，不会变成 0.9999。
    之前用「相对误差 0.5%」判，1.0 与 0.9999 只差 0.01%，就漏了。

    百分比换算（0.5918 与 59.18）先做 scale 再走同一条判据。
    """
    if a == b:
        return True
    da = _decimals(a) if decimals is None else decimals

    def _ok(x: float) -> bool:
        try:
            return abs(round(x, da) - a) <= 1e-12
        except (ValueError, OverflowError):
            return False

    if _ok(b):
        return True
    for scale in (100.0, 0.01):
        if _ok(b * scale):
            return True
    return False
def collect_output_numbers(outputs) -> list[float]:
    """从插件的结构化输出里收集所有数（递归 JSON）。"""
    nums = []

    def walk(o):
        if isinstance(o, bool):
            return
        if isinstance(o, (int, float)):
            nums.append(float(o))
        elif isinstance(o, str):
            for m in re.finditer(r"-?\d+(?:\.\d+)?", o):
                try:
                    nums.append(float(m.group(0)))
                except ValueError:
                    pass
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                walk(v)

    walk(outputs)
    return nums


def trace(tex: str, outputs) -> dict:
    """主函数。返回 ok / untraced / traced_ratio。"""
    cand = extract_numbers(tex)
    pool = collect_output_numbers(outputs)
    untraced = []
    for tok, line in cand:
        try:
            v = float(tok)
        except ValueError:
            continue
        # 用 token 的书写精度，而不是 float 的 repr（见 _written_decimals）
        dec = _written_decimals(tok)
        if not any(_near(v, p, dec) for p in pool):
            untraced.append(dict(token=tok, line=line))
    total = len(cand)
    return dict(ok=not untraced,
                n_numbers=total,
                n_untraced=len(untraced),
                traced_ratio=(1 - len(untraced) / total) if total else 1.0,
                untraced=untraced)


def _looks_self_proved(obj) -> bool:
    """这份 JSON 是不是「拿论文自己的数当溯源表」？

    第 122 轮（红队独立诊断 §3.5d）：`freeze.check_paper` 有
    `_self_proving` 检查，`verify` 没有 —— 于是 A2 那条攻击
    （用论文里的数生成冻结表，再让论文去这张表里「溯源」）
    能绕过 verify 门。判据与 freeze 保持一致：条目全带 path 且
    path 全是 self/paper/tex（或空）时，视为自证。
    """
    if not isinstance(obj, dict):
        return False
    items = obj.get("items")
    if not isinstance(items, list) or not items:
        return False
    paths = [str((it or {}).get("path") or "") for it in items
             if isinstance(it, dict)]
    if not paths:
        return False
    return all(p.strip().lower() in ("", "self", "paper", "tex")
               for p in paths)


def load_outputs(out_dir: str) -> list:
    """把插件落在 out/ 下的结构化产物读进来当溯源池。

    原来只读 .json —— 而插件的一等产物大量是 CSV
    （abilities.csv / layers.csv / topsis.csv / greedy_vs_opt.csv …），
    只读 JSON 会让「来源就在隔壁表里」的数被判成无出处。
    CSV 按文本行读（不解析列类型），数字仍由 collect_output_numbers 统一抽取。

    第 122 轮：自我冻结的 JSON 不进池（见 _looks_self_proved）。
    """
    pool = []
    for root, _dirs, files in os.walk(out_dir):
        for f in files:
            if f.startswith("."):
                continue
            p = os.path.join(root, f)
            if f.endswith(".json"):
                try:
                    obj = json.load(open(p, encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if _looks_self_proved(obj):
                    continue
                pool.append(obj)
            elif f.endswith(".csv"):
                try:
                    pool.append(open(p, encoding="utf-8",
                                     errors="replace").read())
                except OSError:
                    continue
    return pool


def report(r: dict) -> str:
    L = [f"数字溯源：{r['n_numbers'] - r['n_untraced']}/{r['n_numbers']} "
         f"({r['traced_ratio'] * 100:.1f}%)"]
    if r["untraced"]:
        L.append(f"  ⚠ {r['n_untraced']} 个数字在插件输出里找不到来源：")
        for u in r["untraced"][:15]:
            L.append(f"    · {u['token']}  ← {u['line']}")
        if r["n_untraced"] > 15:
            L.append(f"    … 还有 {r['n_untraced'] - 15} 个")
        L.append("  这些数字必须删掉或改成插件算出来的值。")
    return "\n".join(L)


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

    outs = {"fit": {"best": {"rmse": 0.0074342, "r2": 0.5918}},
            "pareto": {"front": 9}}
    pool = collect_output_numbers(outs)
    ck("从输出收集到数字", len(pool) >= 3, str(sorted(pool)[:3]))

    tex_ok = (r"$R^2 = 0.5918$ and CV RMSE $= 0.00743$, "
              r"the front has 9 points.")
    r = trace(tex_ok, outs)
    ck("合法论文全溯源", r["ok"], f"{r['traced_ratio']:.2f}")

    tex_bad = r"$R^2 = 0.8500$ and CV RMSE $= 0.00743$."
    r2 = trace(tex_bad, outs)
    ck("编的 R²=0.85 被抓出来", not r2["ok"] and r2["n_untraced"] >= 1,
       str([u["token"] for u in r2["untraced"]]))

    # 百分比 vs 小数
    ck("59.18 与 0.5918 视为同源",
       _near(59.18, 0.5918), "百分比换算")
    # 方向很重要：论文里的数是输出里的数的**舍入**才算同源。
    # 反过来（论文比输出多写几位）不算 —— 输出不足以确认那几位。
    ck("论文是输出的舍入（0.00743 <- 0.0074342）",
       _near(0.00743, 0.0074342), "精度差异")
    ck("0.5918 与 0.8500 不视为同源", not _near(0.5918, 0.85))
    # 防编造：输出精度比论文低，或同精度但数不同，都不能算同源
    ck("论文精度高于输出时不算同源（1.0 不足以确认 0.9999）",
       not _near(0.9999, 1.0))
    ck("同精度但数不同不算同源（0.9999 vs 0.9975）",
       not _near(0.9999, 0.9975))

    # 元数据不该被当成计算数字
    tex_meta = r"\section{Summary} \label{sec:1} \cite{ref2024}"
    ck("章节/标签/引用不产生数字",
       len(extract_numbers(tex_meta)) == 0,
       str(extract_numbers(tex_meta)))

    # ── 第 87 轮补：抽取器自身的三个坑 ──────────────────────────────
    # ① 破折号区间不是负数
    t_dash = r"the interval is $[0.19, 0.57]$ and 0.19--0.57 holds, 1965--1970 too"
    toks = [t for t, _l in extract_numbers(t_dash)]
    ck("区间写法不产生幻影负数",
       not any(t.startswith("-") for t in toks), str(toks))
    # ② 写成整数的 52 是 0 位小数，不能按 1 位判（否则 52.5 配不上）
    ck("写成整数时按 0 位小数判", _written_decimals("52") == 0)
    ck("写成 52.0 时按 1 位小数判", _written_decimals("52.0") == 1)
    ck("52 <- 52.5 视为同源（舍入）", _near(52.0, 52.5, _written_decimals("52")))
    # 但防编造的那条不能被放松：0.9999 仍需输出有 4 位
    ck("0.9999 仍要求输出有 4 位精度",
       not _near(0.9999, 1.0, _written_decimals("0.9999")))
    # ③ 前导区与跨行命令参数不算主张
    t_pre = ("\\documentclass{article}\n\\definecolor{ink}{HTML}{8A3324}\n"
             "\\geometry{a4paper, top=2.8cm,\n  bottom=2.8cm}\n"
             "\\begin{document}\nCV RMSE is 0.00743 here.\n\\end{document}\n")
    tok2 = [t for t, _l in extract_numbers(t_pre)]
    ck("前导区的宏定义不产生数字",
       "3324" not in tok2 and "2.8" not in tok2, str(tok2))
    ck("正文数字仍然抽得到", "0.00743" in tok2, str(tok2))

    print(f"\n{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1


def main(argv=None) -> int:
    """命令行：查一篇真实论文的数字溯源。

        python verify.py <paper.tex> [--out-dir 产物目录] [--json]

    原来 __main__ 只跑 selftest，新会话想查自己的论文没法用。
    """
    import argparse
    ap = argparse.ArgumentParser(description="数字溯源")
    ap.add_argument("tex", nargs="?", default="",
                    help="paper.tex 路径；也可以直接给产物目录，自动找 paper.tex")
    ap.add_argument("--out-dir", default="")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if not a.tex:
        # 没有参数：跑自测（保持原行为）
        return selftest()
    import os as _o
    # 位置参数给成目录是很容易犯的错（文档里两种说法都出现过）。
    # 原来的实现直接 open(dir) → PermissionError: Permission denied: 'out/arch'，
    # 那既不解释原因，也会被当成权限问题去查。
    tex = a.tex
    if _o.path.isdir(tex):
        cand = _o.path.join(tex, "paper.tex")
        if not _o.path.exists(cand):
            print("这是一个目录，且里面没有 paper.tex：%s" % tex)
            print("请给 paper.tex 的路径，或给包含 paper.tex 的产物目录。")
            return 2
        tex = cand
    if not _o.path.exists(tex):
        print("找不到文件：%s" % tex)
        return 2
    if not _o.path.isfile(tex):
        print("这不是普通文件：%s" % tex)
        return 2
    d = a.out_dir or _o.path.dirname(_o.path.abspath(tex))
    try:
        t = open(tex, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError) as e:
        print("读不了 %s：%s: %s" % (tex, type(e).__name__, e))
        return 2
    outs = load_outputs(d)
    r = trace(t, outs)
    if a.json:
        import json as _j
        print(_j.dumps(r, ensure_ascii=False, indent=2, default=str))
    else:
        print(report(r))
    # 原来读 r.get("unmatched")，而 trace() 返回的键是 "untraced"，
    # 于是退出码恒为 0 —— 红队 F2 抓到的。
    return 0 if not (r.get("untraced") or []) else 1


if __name__ == "__main__":
    raise SystemExit(main())
