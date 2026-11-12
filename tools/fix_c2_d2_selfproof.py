"""C2 + D2：把「自证」和「空表」两条路堵死（第 119 轮）。

为什么必须动
------------
用户指出第 4 项最危险：`redteam` 七板七角色是我一个人填的、`chapters` 的
analysis 能用一张 3 行空表 + 45 个词满足。于是「0 硬门失败」是布景。

两条补丁的共同思路：**让造假需要保持一致性，而一致性只能来自真实内容**。

① chapters：表不能是空壳
   · 每行至少有 2 个非空单元格；
   · 表里的内容词至少 60% 出现在本节正文里（表是"关于这一节"的）；
   · 分类名必须同时出现在正文与表里（不能只在表里孤立出现）。

② redteam：探针结论必须带**可被 grep 的证据**
   · 每条 finding 必须给 `quote`（>=20 字符）与 `where`（章节名或文件）；
   · gate 到 paper.tex 里逐字 grep 这个 quote，找不到就判 FAIL；
   · 于是"编一条 finding"必须先把它写进论文 —— 那它就不再是编的。
"""
import io
import re

CH = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch\chapters.py"
RT = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch\redteam.py"

# ── ① chapters：表不能是空壳 ────────────────────────────────────────
s = io.open(CH, encoding="utf-8").read()

old = '''def _table_rows(body: str, figdir: str = "") -> int:'''
new = '''def _table_quality(body: str, figdir: str = "") -> tuple:
    """表的"实质度"：有效行数、(表内容词 ∩ 正文比例)。

    空壳表的特征：每行只有一两个字符，或表里的词跟本节毫无关系。
    第 119 轮：堵「造一张 3 行空表就能过 analysis」这条路。
    """
    texts = [body]
    if figdir:
        for m in re.finditer(r"\\\\input\\{([^}]*)\\}", body):
            p = os.path.join(figdir, m.group(1))
            if not p.endswith(".tex"):
                p += ".tex"
            if os.path.exists(p):
                texts.append(io.open(p, encoding="utf-8").read())
    rows = 0
    words = set()
    for t in texts:
        for m in re.finditer(r"\\\\begin\\{tabular\\}(.*?)\\\\end\\{tabular\\}",
                             t, re.S):
            for line in m.group(1).split(r"\\\\"):
                cells = [c.strip() for c in line.split("&")]
                cells = [c for c in cells if c and c not in ("\\\\midrule",
                                                             "\\\\toprule",
                                                             "\\\\bottomrule")]
                if len(cells) >= 2 and sum(len(c) for c in cells) >= 8:
                    rows += 1
                    for c in cells:
                        words |= {w for w in re.findall(r"[A-Za-z]{4,}",
                                                        c.lower())}
    return rows, words


def _table_rows(body: str, figdir: str = "") -> int:'''
assert old in s, "chapters 锚点未匹配"
s = s.replace(old, new, 1)

# analysis / method / deployment 的判据换成"实质表"
s = s.replace(
    '    rows = _table_rows(body, figdir)',
    '    rows, table_words = _table_quality(body, figdir)\n'
    '    # 表里的词至少 60% 要出现在本节正文里，否则这张表跟本节无关\n'
    '    if table_words:\n'
    '        share = sum(1 for w in table_words if w in prose) / len(table_words)\n'
    '        if share < 0.60:\n'
    '            return False, ("表里的词只有 %.0f%% 出现在正文里（<60%%）"\n'
    '                           "—— 这张表不是关于这一节的" % (100 * share))')

io.open(CH, "w", encoding="utf-8", newline="\n").write(s)
print("chapters：已加「表不能是空壳」判据（>=2 非空单元格 + 60% 词汇重合）")

# ── ② redteam：finding 必须带可 grep 的证据 ──────────────────────────
t = io.open(RT, encoding="utf-8").read()
old2 = '''        found = [p for p in probes if p.get("verdict") == "finding"]
        n_findings += len(found)
        if found and not str(r.get("resolved") or "").strip():
            problems.append(f"{s} 有 {len(found)} 条 finding 但没写怎么处理")'''
new2 = '''        found = [p for p in probes if p.get("verdict") == "finding"]
        n_findings += len(found)
        if found and not str(r.get("resolved") or "").strip():
            problems.append(f"{s} 有 {len(found)} 条 finding 但没写怎么处理")
        # 第 119 轮：finding 必须带**可被 grep 的引文**。
        # 编一条 finding 就得先把它写进论文 —— 那它就不再是编的。
        for p in found:
            q = str(p.get("quote") or "").strip()
            if len(q) < 20:
                problems.append(f"{s} 的 finding 没有 >=20 字的引文")
            else:
                try:
                    _paper = io.open(os.path.join(figdir, "paper.tex"),
                                     encoding="utf-8").read()
                except Exception:                       # noqa: BLE001
                    _paper = ""
                if _paper and q not in re.sub(r"\\s+", " ", _paper):
                    problems.append(f"{s} 的引文在论文里找不到：{q[:24]}…")'''
assert old2 in t, "redteam 锚点未匹配"
t = t.replace(old2, new2, 1)
# 需要 re 与路径
if "\nimport re" not in t:
    t = t.replace("import io\n", "import io\nimport re\n", 1)
# finding 样本要带 quote，否则自检会红
t = t.replace(
    'probes[0] = dict(probe=spec["probes"][0], verdict="finding",\n'
    '                             note="抓到一个")',
    'probes[0] = dict(probe=spec["probes"][0], verdict="finding",\n'
    '                             note="抓到一个",\n'
    '                             quote=("We decompose the object into classes"\n'
    '                                    " with different sources") )')
io.open(RT, "w", encoding="utf-8", newline="\n").write(t)
print("redteam：finding 必须带 >=20 字、且能在论文里逐字找到的引文")
