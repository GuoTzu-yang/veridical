"""第 121 轮：把「自证」剩下的两条缝补上。

① redteam：verdict=pass 的探针也必须写 tried（>=30 字）。
   否则「没发现问题」和「根本没查」不可区分 —— 13 条 finding 这个数字
   的说服力全押在「查过」上，而「查过」目前是零成本的。

② chapters：表必须**属于这一节** —— 表里的数字至少 2 个出现在本节正文。
   之前只验形式（行数/单元格/数字），把别处的一张真表搬过来照样过。
"""
import io

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"

# ── ① redteam ──────────────────────────────────────────────────────
p = HERE + r"\redteam.py"
s = io.open(p, encoding="utf-8").read()
old = '        found = [p for p in probes if p.get("verdict") == "finding"]'
new = (
    '        # 第 121 轮：pass 也得有成本 —— 「没发现问题」必须写清试过什么。\n'
    '        # 否则「没找到」和「根本没查」不可区分（自证的最后一条缝）。\n'
    '        for _p in probes:\n'
    '            if _p.get("verdict") == "pass":\n'
    '                _t = str(_p.get("tried") or "").strip()\n'
    '                if len(_t) < 30:\n'
    '                    problems.append(\n'
    '                        f"{s} 的 pass 探针没写 tried（>=30 字，"\n'
    '                        "说明查过哪里、看了什么）")\n'
    '        found = [p for p in probes if p.get("verdict") == "finding"]'
)
assert old in s, "redteam 插入点未匹配"
s = s.replace(old, new, 1)
io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("redteam：pass 探针必须写 tried")

# ── ② chapters ─────────────────────────────────────────────────────
q = HERE + r"\chapters.py"
t = io.open(q, encoding="utf-8").read()
old2 = ('    if rows and not (_has_numeric_cell(body, figdir)\n'
        '                     or _cells_in_prose(body, figdir, prose) >= 2):')
new2 = (
    '    # 第 121 轮：表必须**属于这一节** —— 表里的数字至少 2 个出现在本节正文。\n'
    '    # 之前只验形式（行数/单元格/数字），把别处的一张真表搬过来照样过。\n'
    '    _alltxt = " ".join(_table_texts(body, figdir))\n'
    '    _tnums = set(re.findall(r"(?<![\\w.])-?\\d+\\.\\d+(?![\\w.])", _alltxt))\n'
    '    _pnums = set(re.findall(r"(?<![\\w.])-?\\d+\\.\\d+(?![\\w.])", prose))\n'
    '    _hit = len(_tnums & _pnums)\n'
    '    if rows and _hit < 2:\n'
    '        return False, ("表里的数字只有 %d 个出现在本节正文（要 >=2）"\n'
    '                       "—— 这张表可能不是这一节的" % _hit)\n'
    + old2
)
assert old2 in t, "chapters 插入点未匹配"
t = t.replace(old2, new2, 1)
io.open(q, "w", encoding="utf-8", newline="\n").write(t)
print("chapters：表必须属于本节（>=2 个数字重合）")
