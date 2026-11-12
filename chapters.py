"""chapters.py —— 把「一篇论文必须有的五件事」变成可判定的检查（第 111 轮）。

为什么要有这个模块
------------------
用户的要求不是「论文里最好有这几节」，而是**插件强制它们存在**：
少一样就出不了稿。原来的 23 项 gate 只查形式（有没有摘要、图、引用），
不查「有没有把问题拆开」「有没有论证」「有没有交代自己错在哪」「能不能落地」。
这四样正是评审给分的地方，也正是 LLM 最容易省掉的地方。

四个检查，每个都**能失败**（不是有就过、没有就 N/A）：

  analysis        分析题的思路：是否把研究对象拆开，并有分类证据（表/图）
  method_argument 解题的思路/方法/技巧：方法是否配了「被否掉的替代方案 + 理由」
  self_correction 自己哪里错、怎么发现、怎么改、为什么改对
  deployment      方案落地：运行方式、时间预算、失败处置

判据都是**结构 + 词面**的组合，且都写在这里，别人可以复核：
  · 结构：要有独立小节（\\section 或 \\subsection），不是散句；
  · 词面：小节内要出现该检查专属的信号词，且达到下限；
  · 反空洞：信号词在图注或表格里凑数不算，必须出现在正文段落里。

为什么不并进 gate.py：gate.py 已经 1400+ 行，五项各有自己的判据，
放在一起会让「哪条判据改过」无法追踪。这里独立成模块，gate 只调它。
"""
import io
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

# ── 判据表：每项的信号词与下限 ──────────────────────────────────────
SPEC = {
    "analysis": dict(
        title="分析题的思路",
        heads=("analysis", "analysing", "analyzing", "decompos", "分解", "剖析"),
        signals=("decompos", "classif", "four classes", "five classes",
                 "where does", "anatomy", "taxonomy of the object",
                 "分解", "分类", "逐类"),
        need_signal=3,
        need_table=True,
        hint="写一节「把问题拆开」：对象由哪几类构成、每类性质如何、"
             "由此得到哪几条设计要求；并给出分类表或分类图。"),
    "method_argument": dict(
        title="解题方法与论证",
        heads=("method", "approach", "模型建立", "方法"),
        signals=("rejected alternative", "rather than", "instead of",
                 "would change", "why this", "alternative we",
                 "否决", "替代方案", "而不是"),
        need_signal=4,
        need_table=True,
        hint="每个方法都要配「被否掉的替代方案 + 为什么不用它 + 什么证据会改变主意」；"
             "最省事的形式是一张 方法/替代/理由 表。"),
    "self_correction": dict(
        title="自我纠错与论证",
        heads=("what was wrong", "self-correct", "correction", "错在", "纠错"),
        signals=("wrong", "how found", "change", "why this is right",
                 "错在", "怎么发现", "怎么改", "为什么这个改法"),
        need_signal=8,          # 每条案例至少四段信号，两例即 8
        need_table=False,
        hint="逐条写清：错在哪 → 怎么发现的（哪个测量暴露的）→ 改了什么 → "
             "为什么这个改法是对的（而不是「现在绿了」）。"),
    "deployment": dict(
        title="落地与推广",
        heads=("deployment", "deploy", "operat", "落地", "推广", "production"),
        signals=("mode", "playbook", "time budget", "run it", "cost",
                 "first response", "落地", "运行方式", "时间预算", "处置"),
        need_signal=4,
        need_table=True,
        hint="写清三种运行方式、逐阶段时间预算、出问题时的处置表，"
             "以及成本（机器时间 vs 编辑时间）。"),
}


def _sections(tex: str):
    """切出可检查的块：每个 \\section（含其全部子节）+ 每个 \\subsection。

    第 111 轮修正：原来按 `\\(?:sub)?section` 切，于是
    `\\section{Analysis}` 后紧跟 `\\subsection{Step 1}` 时，
    父节的 body 只剩下一个换行 —— 内容全在子节里，检查器读到空串。
    现在父节 body 延伸到下一个 \\section，并把子节也单独列为候选块。
    """
    # ① 父节：body 到下一个 \section 为止（包含所有子节）
    parts = re.split(r"\n\\section\{([^}]*)\}", "\n" + tex)
    units = []
    for i in range(1, len(parts), 2):
        body = parts[i + 1] if i + 1 < len(parts) else ""
        units.append((parts[i], body))
        # ② 子节：单独也作为候选（父节标题不匹配时仍能找到内容）
        subs = re.split(r"\n\\subsection\{([^}]*)\}", "\n" + body)
        for j in range(1, len(subs), 2):
            units.append((subs[j], subs[j + 1] if j + 1 < len(subs) else ""))
    return units


def _prose_only(body: str) -> str:
    """剥掉表格体与图体，但**保留表注** —— 表注是作者写的论证。

    第 111 轮修正：原来把 `\\begin{table}...\\end{table}` 整段删掉，
    于是「方法/替代/理由」这类表格里的论证被判成「没有论证」。
    现在只删到 `\\caption` 之前的部分，caption 里的话仍算作者的论述；
    同时表格体里的信号词依旧不算（防止用表体凑数）。
    """
    def _keep_caption(env):
        pat = (r"\\begin\{" + env + r"\}(.*?)\\end\{" + env + r"\}")

        def repl(m):
            inner = m.group(1)
            cap = re.search(r"\\caption\{(.*?)\}(?=[\s\S]*$)", inner, re.S)
            return " " + (cap.group(1) if cap else " ")
        return re.sub(pat, repl, body, flags=re.S)

    for env in ("table", "longtable", "figure"):
        body = _keep_caption(env)
    return body


def _check_one(kind: str, tex: str, figdir: str = "") -> dict:
    spec = SPEC[kind]
    secs = _sections(tex)
    # ① 找到对应小节：标题含 heads 任一
    hits = [(t, b) for t, b in secs
            if any(h.lower() in t.lower() for h in spec["heads"])]
    if not hits:
        return dict(id=kind, ok=False, level="FAIL",
                    detail=f"没有「{spec['title']}」小节 —— {spec['hint']}")
    title, body = hits[0]
    # 先把空白归一：why this is right 被折行时就数不到了
    # （第 118 轮：fixture 恰好折行，判据误报 0 例）
    prose = re.sub(r"\s+", " ", _prose_only(body).lower())
    # ② 信号要够
    if kind == "self_correction":
        # 这一项按「案例 × 四个标记」计数：至少两例，每例都要四段齐全
        groups = [("wrong",), ("how found", "how we found"),
                  ("change", "changed"), ("why this is right", "why the fix")]
        per = [sum(prose.count(w) for w in g) for g in groups]
        n_sig = min(per) if per else 0
        need = 2
        if n_sig < need:
            return dict(id=kind, ok=False, level="FAIL",
                        detail=(f"「{title}」完整案例只有 {n_sig} 例"
                                f"（四段计数 {per}）—— {spec['hint']}"))
    else:
        n_sig = sum(1 for w in spec["signals"] if w.lower() in prose)
        need = spec["need_signal"]
        if n_sig < need:
            return dict(id=kind, ok=False, level="FAIL",
                        detail=(f"「{title}」只有 {n_sig}/{need} 个信号词"
                                f" —— {spec['hint']}"))
    # ③ 需要证据（表或图）的项要看有没有
    if spec["need_table"]:
        has = ("\\begin{table}" in body or "\\begin{longtable}" in body
               or "\\begin{figure}" in body or "\\input{" in body)
        if not has:
            return dict(id=kind, ok=False, level="WARN",
                        detail=f"「{title}」有论述但没有分类/对照证据（表或图）")
    # 第 118 轮：信号词不够了，还要过结构性判据（防止堆词过关）
    ok_s, why = _structure(kind, body, prose, figdir)
    if not ok_s:
        return dict(id=kind, ok=False, level="FAIL",
                    detail=f"「{title}」{why} —— {spec['hint']}")
    return dict(id=kind, ok=True, level="PASS",
                detail=f"「{title}」：{n_sig} 个信号词 + {why}")


def _table_texts(body: str, figdir: str = ""):
    """本节正文 + 它用 \\input 引进来的表文件。"""
    out = [body]
    if figdir:
        for m in re.finditer(r"\\input\{([^}]*)\}", body):
            p = os.path.join(figdir, m.group(1))
            if not p.endswith(".tex"):
                p += ".tex"
            if os.path.exists(p):
                out.append(io.open(p, encoding="utf-8").read())
    return out


def _has_numeric_cell(body: str, figdir: str = "") -> bool:
    """表里是否有带数字的单元格 —— 真数据表几乎总有。"""
    for t in _table_texts(body, figdir):
        for m in re.finditer(r"\\begin\{tabular\}(.*?)\\end\{tabular\}",
                             t, re.S):
            if re.search(r"\d", m.group(1)):
                return True
    return False


def _cells_in_prose(body: str, figdir: str, prose: str) -> int:
    """有多少个单元格原文出现在正文里（说明这张表被正文讨论过）。"""
    n = 0
    for t in _table_texts(body, figdir):
        for m in re.finditer(r"\\begin\{tabular\}(.*?)\\end\{tabular\}",
                             t, re.S):
            for cell in re.split(r"&|\\\\", m.group(1)):
                c = re.sub(r"\\(?:top|mid|bottom)rule|\\hline", " ", cell)
                c = re.sub(r"\s+", " ", c).strip()
                if len(c) >= 4 and c.lower() in prose:
                    n += 1
    return n


def _table_quality(body: str, figdir: str = "") -> tuple:
    """表的"实质度"：有效行数、(表内容词 ∩ 正文比例)。

    空壳表的特征：每行只有一两个字符，或表里的词跟本节毫无关系。
    第 119 轮：堵「造一张 3 行空表就能过 analysis」这条路。
    """
    texts = [body]
    if figdir:
        for m in re.finditer(r"\\input\{([^}]*)\}", body):
            p = os.path.join(figdir, m.group(1))
            if not p.endswith(".tex"):
                p += ".tex"
            if os.path.exists(p):
                texts.append(io.open(p, encoding="utf-8").read())
    rows = 0
    words = set()
    for t in texts:
        for m in re.finditer(r"\\begin\{tabular\}(.*?)\\end\{tabular\}",
                             t, re.S):
            for line in m.group(1).split(r"\\"):
                cells = [c.strip() for c in line.split("&")]
                cells = [c for c in cells if c and c not in ("\\midrule",
                                                             "\\toprule",
                                                             "\\bottomrule")]
                if len(cells) >= 2 and sum(len(c) for c in cells) >= 8:
                    rows += 1
                    for c in cells:
                        words |= {w for w in re.findall(r"[A-Za-z]{4,}",
                                                        c.lower())}
    return rows, words


def _table_rows(body: str, figdir: str = "") -> int:
    """数表格行数：以 LaTeX 换行（两个反斜杠）结尾的行。

    第 118 轮：论文常把表放进 `\\input{tab_x.tex}`，只看正文会数到 0 行，
    于是「有分类表」被判成没有。
    """
    n = len(re.findall(r"\\\\\s*$", body, re.M))
    if figdir:
        for m in re.finditer(r"\\input\{([^}]*)\}", body):
            p = os.path.join(figdir, m.group(1))
            if not p.endswith(".tex"):
                p += ".tex"
            if os.path.exists(p):
                n += len(re.findall(r"\\\\\s*$",
                                    io.open(p, encoding="utf-8").read(), re.M))
    return n


def _has_table_with(body: str, words) -> bool:
    """该节里是否存在一张表，其表头含 words 之一。"""
    for m in re.finditer(r"\\begin\{tabular\}(.*?)\\end\{tabular\}",
                         body, re.S):
        head = m.group(1).split(r"\\")[0].lower()
        if any(w.lower() in head for w in words):
            return True
    return False


def _structure(kind: str, body: str, prose: str, figdir: str = "") -> tuple:
    """结构性判据：光有信号词过不去。返回 (ok, 原因)。"""
    n_words = len(prose.split())
    rows, table_words = _table_quality(body, figdir)
    # 空壳表的判据（第 119 轮，第二版）：
    # 60% 词汇重合太粗 —— 真表的词本来就不必在正文里重复（cli/daemon/stamp）。
    # 改成**二选一**：表里有数字证据，或有 >=2 个单元格原文出现在正文里。
    # 一张只有破折号和占位符的表两样都没有。
    # 第 121 轮（第二版）：表必须**被本节引用**。
    # 原判据是「表里的数字有 2 个出现在正文」，但好表本来就把数放在表里、
    # 正文写叙述（anatomy 表的 139/9.4/1483 都不在正文里）—— 判据本身错了。
    # 引用绑定与全局「图表必须被正文引用」是同一条纪律。
    # 只认 table/figure 环境里的标签 —— \section 的 \label 不是表的标签
    # （第 121 轮第三版：曾把 sec:wrong 当表标签，误判了纠错节）
    _defined = set()
    for _m in re.finditer(
            r"\\begin\{(?:table|longtable|figure)\}(.*?)\\end\{(?:table|longtable|figure)\}",
            body, re.S):
        _defined |= set(re.findall(r"\\label\{([^}]*)\}", _m.group(1)))
    for _txt in _table_texts(body, figdir)[1:]:
        _defined |= set(re.findall(r"\\label\{([^}]*)\}", _txt))
    _refs = set(re.findall(r"\\ref\{([^}]*)\}", body))
    if _defined and not (_defined & _refs):
        return False, ("本节的表没有被本节正文引用（\ref）"
                       "—— 这张表不属于这一节")
    if rows and not (_has_numeric_cell(body, figdir)
                     or _cells_in_prose(body, figdir, prose) >= 2):
        if not (_has_numeric_cell(body, figdir)
                or _cells_in_prose(body, figdir, prose) >= 2):
            return False, ("表既没有数字证据，也没有单元格原文进入正文"
                           "—— 像是空壳表")
    if kind == "analysis":
        if rows < 3:
            return False, "分析节没有 >=3 行的分类表（%d 行）" % rows
        names = sum(1 for c in ("structural", "configuration", "temporal",
                                "tabulated", "computed", "class")
                    if c in prose)
        if names < 2:
            return False, "正文里没有点名 >=2 个类别（%d）" % names
        if n_words < 45:
            return False, "分析节正文只有 %d 词（<45）" % n_words
        return True, "表 %d 行、点名 %d 类、%d 词" % (rows, names, n_words)

    if kind == "method_argument":
        if not _has_table_with(body, ("alternative", "rejected", "理由",
                                      "rather than", "否")):
            return False, "没有「替代方案/否决」列的表"
        if rows < 3:
            return False, "方法表只有 %d 行" % rows
        if not any(w in prose for w in ("would change", "否决", "替代", "reject")):
            return False, "正文没说「什么会改变主意」"
        return True, "替代表 %d 行" % rows

    if kind == "self_correction":
        cases = len(re.findall(
            r"\\(?:subsection|paragraph)\{[^}]*(?:case|wrong|错在|案例)",
            body, re.I))
        if cases < 2:
            return False, "案例标题只有 %d 个（要 >=2）" % cases
        # 每个案例要有证据（数字或 \ref）。注意用 r"\d" 而不是 r"\\d"：
        # 后者匹配的是字面上的反斜杠加 d（第 118 轮又踩了一次）。
        blocks = re.split(r"\\(?:subsection|paragraph)\{", body)
        weak = 0
        for b in blocks[1:]:
            if not re.search(r"\d|\\ref\{", b):
                weak += 1
        if weak >= len(blocks) - 1:
            return False, "所有案例里都没有数字或引用（纯抒情）"
        return True, "%d 个案例，含证据" % cases

    if kind == "deployment":
        if not _has_table_with(body, ("mode", "playbook", "方式", "处置",
                                      "budget", "预算", "response")):
            return False, "没有运行方式/处置表"
        if rows < 3:
            return False, "部署表只有 %d 行" % rows
        if n_words < 45:
            return False, "部署节正文只有 %d 词（<45）" % n_words
        return True, "部署表 %d 行、%d 词" % (rows, n_words)

    return True, ""


def check(figdir: str) -> list:
    """对一个论文目录跑四项检查，返回 list[dict]。"""
    p = os.path.join(figdir, "paper.tex")
    if not os.path.exists(p):
        return [dict(id=k, ok=False, level="FAIL",
                     detail="没有 paper.tex —— 五件事无从检查")
                for k in SPEC]
    tex = io.open(p, encoding="utf-8").read()
    return [_check_one(k, tex, figdir) for k in SPEC]


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

    # 空文档：四项都必须 FAIL（不许 N/A、不许默过）
    import tempfile
    td = tempfile.mkdtemp(prefix="chap_empty_")
    io.open(os.path.join(td, "paper.tex"), "w", encoding="utf-8").write(
        "\\begin{document}\\end{document}")
    r = check(td)
    ck("空文档四项全 FAIL", all(not x["ok"] for x in r),
       str([x["level"] for x in r]))

    # 信号词只出现在**表格体**里（不是表注）→ 仍必须 FAIL。
    # 表注算作者论证（第 111 轮的修正），表体不算。
    td2 = tempfile.mkdtemp(prefix="chap_cap_")
    io.open(os.path.join(td2, "paper.tex"), "w", encoding="utf-8").write(
        "\\section{Analysis}\n"
        "\\begin{table}\n\\begin{tabular}{l}\n"
        "decompos classif anatomy where does taxonomy of the object\n"
        "\\end{tabular}\n\\caption{nothing here}\n\\end{table}\n")
    r2 = check(td2)
    an = [x for x in r2 if x["id"] == "analysis"][0]
    ck("信号词只在图注里不算（仍 FAIL）", not an["ok"], an["detail"][:40])

    # 合格样本：分析 + 方法 + 纠错 + 落地
    td3 = tempfile.mkdtemp(prefix="chap_ok_")
    # 合格样本放在独立 fixture 文件里：内联字符串的转义已经坑过四次
    _fx = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "tests", "fixtures", "chapter_good.tex")
    good = io.open(_fx, encoding="utf-8").read()
    io.open(os.path.join(td3, "paper.tex"), "w", encoding="utf-8").write(good)
    r3 = check(td3)
    # 堆词样本：信号词齐全、正文够长，但没有表、没有案例 → 必须 FAIL
    td4 = tempfile.mkdtemp(prefix="chap_fake_")
    io.open(os.path.join(td4, "paper.tex"), "w", encoding="utf-8").write(
        "\\section{Analysis of the problem}\n"
        "We decompose the object into classes; the classification is anatomy "
        "of the object; we ask where does each number come from. "
        + "filler " * 40 + "\n")
    r4 = check(td4)
    an4 = [x for x in r4 if x["id"] == "analysis"][0]
    ck("堆词但没有表 → FAIL", not an4["ok"], an4["detail"][:44])

    ck("合格样本四项全 PASS", all(x["ok"] for x in r3),
       str([(x["id"], x["detail"][:24]) for x in r3 if not x["ok"]]))
    ck("四项 id 固定", [x["id"] for x in r3] == list(SPEC))

    print()
    print(f"{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad}/{n}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        raise SystemExit(selftest())
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out", "final")
    for x in check(d):
        print(f"  [{x['level']}] {x['id']:<16} {x['detail']}")
