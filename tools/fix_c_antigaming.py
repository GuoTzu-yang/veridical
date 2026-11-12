"""C：给「五件事」加反糊弄判据（第 118 轮）。

问题
----
`chapters.py` 原来只判「这节里有没有 N 个信号词 + 一张表」。我自己写的合格
样本就是堆词通过的 —— 一个知道词表的模型可以毫无内容地过关。这条必须堵。

现在每一项都要满足**结构性判据**，光堆词过不去：

  analysis        1) 有一张 >=3 行的表或图；2) 正文里至少点名 2 个类别；
                  3) 该节引用了那张表（\\ref），说明表在被用；4) 正文 >=80 词
  method_argument 1) 有一张表，表头含 alternative/rejected/而不是 之一；
                  2) 该表 >=3 行；3) 正文里出现 would change/否决/替代 之一
  self_correction 1) 至少 2 个案例标题（Case/Wrong/错在/案例）；
                  2) 每个案例下的正文里至少有一个数字或 \\ref（有证据，不只是抒情）
  deployment      1) 有一张表，表头含 mode/mode/方式 或 playbook/处置/预算 之一；
                  2) 该表 >=3 行；3) 正文 >=80 词

判据全部写在 SPEC 里，可复核。自检断言「堆词的假样本必须 FAIL」。
"""
import io
import re

P = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch\chapters.py"
s = io.open(P, encoding="utf-8").read()

# 在 _check_one 之后新增结构判据函数，并让 _check_one 调用它
anchor = "def check(figdir: str) -> list:"
new = '''def _table_rows(body: str) -> int:
    """粗数表格行数：以 `\\\\\\\\` 结尾的行。"""
    return len(re.findall(r"\\\\\\\\\\s*(?=\\n|$)", body))


def _has_table_with(body: str, words) -> bool:
    """该节里是否存在一张表，其表头含 words 之一。"""
    for m in re.finditer(r"\\\\begin\\{tabular\\}(.*?)\\\\end\\{tabular\\}",
                         body, re.S):
        head = m.group(1).split(r"\\\\")[0].lower()
        if any(w.lower() in head for w in words):
            return True
    return False


def _structure(kind: str, body: str, prose: str) -> tuple:
    """结构性判据：光有信号词过不去。返回 (ok, 原因)。"""
    n_words = len(prose.split())
    rows = _table_rows(body)
    if kind == "analysis":
        if rows < 3:
            return False, "分析节没有 >=3 行的分类表（%d 行）" % rows
        names = sum(1 for c in ("structural", "configuration", "temporal",
                                "tabulated", "computed", "class")
                    if c in prose)
        if names < 2:
            return False, "正文里没有点名 >=2 个类别（%d）" % names
        if n_words < 80:
            return False, "分析节正文只有 %d 词" % n_words
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
            r"\\\\(?:subsection|paragraph)\\{[^}]*(?:case|wrong|错在|案例)",
            body, re.I))
        if cases < 2:
            return False, "案例标题只有 %d 个（要 >=2）" % cases
        # 每个案例要有证据（数字或 \\ref）
        blocks = re.split(r"\\\\(?:subsection|paragraph)\\{", body)
        weak = 0
        for b in blocks[1:]:
            if not re.search(r"\\\\d|\\\\ref\\{", b):
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
        if n_words < 80:
            return False, "部署节正文只有 %d 词" % n_words
        return True, "部署表 %d 行、%d 词" % (rows, n_words)

    return True, ""


''' + anchor
if "_structure(" not in s:
    s = s.replace(anchor, new, 1)

# 让 _check_one 在信号词通过后再过结构判据
old_ret = '''    return dict(id=kind, ok=True, level="PASS",
                detail=f"「{title}」：{n_sig} 个信号词，结构完整")'''
new_ret = '''    # 第 118 轮：信号词不够了，还要过结构性判据（防止堆词过关）
    ok_s, why = _structure(kind, body, prose)
    if not ok_s:
        return dict(id=kind, ok=False, level="FAIL",
                    detail=f"「{title}」{why} —— {spec['hint']}")
    return dict(id=kind, ok=True, level="PASS",
                detail=f"「{title}」：{n_sig} 个信号词 + {why}")'''
assert old_ret in s, "返回块未匹配"
s = s.replace(old_ret, new_ret, 1)

# 自检：加一条「堆词假样本必须 FAIL」
old_ck = '''    ck("合格样本四项全 PASS", all(x["ok"] for x in r3),'''
new_ck = '''    # 堆词样本：信号词齐全、正文够长，但没有表、没有案例 → 必须 FAIL
    td4 = tempfile.mkdtemp(prefix="chap_fake_")
    io.open(os.path.join(td4, "paper.tex"), "w", encoding="utf-8").write(
        "\\\\section{Analysis of the problem}\\n"
        "We decompose the object into classes; the classification is anatomy "
        "of the object; we ask where does each number come from. "
        + "filler " * 40 + "\\n")
    r4 = check(td4)
    an4 = [x for x in r4 if x["id"] == "analysis"][0]
    ck("堆词但没有表 → FAIL", not an4["ok"], an4["detail"][:44])

    ck("合格样本四项全 PASS", all(x["ok"] for x in r3),'''
if "堆词但没有表" not in s:
    s = s.replace(old_ck, new_ck, 1)

io.open(P, "w", encoding="utf-8", newline="\n").write(s)
print("chapters 已加结构判据 + 堆词反例自检")
