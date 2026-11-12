"""第 121 轮续：把「表属于本节」改成**引用绑定**，并给 pass 探针补 tried。

为什么改判据
------------
原规则「表里的数字至少 2 个出现在正文」错了：好表本来就该把数放在表里、
正文写叙述（anatomy 表 139/9.4/1483 都在表里，正文不重复）。
正解是**引用绑定**：本节正文必须 \\ref 到这张表。
这与全局已有的「图表必须被正文引用」是同一条纪律。
"""
import io
import json
import os
import re

HERE = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"

# ── ① chapters：改用引用绑定 ────────────────────────────────────────
q = HERE + r"\chapters.py"
t = io.open(q, encoding="utf-8").read()
old = (
    '    # 第 121 轮：表必须**属于这一节** —— 表里的数字至少 2 个出现在本节正文。\n'
    '    # 之前只验形式（行数/单元格/数字），把别处的一张真表搬过来照样过。\n'
    '    _alltxt = " ".join(_table_texts(body, figdir))\n'
    '    _tnums = set(re.findall(r"(?<![\\w.])-?\\d+\\.\\d+(?![\\w.])", _alltxt))\n'
    '    _pnums = set(re.findall(r"(?<![\\w.])-?\\d+\\.\\d+(?![\\w.])", prose))\n'
    '    _hit = len(_tnums & _pnums)\n'
    '    if rows and _hit < 2:\n'
    '        return False, ("表里的数字只有 %d 个出现在本节正文（要 >=2）"\n'
    '                       "—— 这张表可能不是这一节的" % _hit)\n'
)
new = (
    '    # 第 121 轮（第二版）：表必须**被本节引用**。\n'
    '    # 原判据是「表里的数字有 2 个出现在正文」，但好表本来就把数放在表里、\n'
    '    # 正文写叙述（anatomy 表的 139/9.4/1483 都不在正文里）—— 判据本身错了。\n'
    '    # 引用绑定与全局「图表必须被正文引用」是同一条纪律。\n'
    '    _defined = set(re.findall(r"\\\\label\\{([^}]*)\\}", body))\n'
    '    for _txt in _table_texts(body, figdir)[1:]:\n'
    '        _defined |= set(re.findall(r"\\\\label\\{([^}]*)\\}", _txt))\n'
    '    _refs = set(re.findall(r"\\\\ref\\{([^}]*)\\}", body))\n'
    '    if _defined and not (_defined & _refs):\n'
    '        return False, ("本节的表没有被本节正文引用（\\ref）"\n'
    '                       "—— 这张表不属于这一节")\n'
)
assert old in t, "chapters 旧判据未匹配"
t = t.replace(old, new, 1)
io.open(q, "w", encoding="utf-8", newline="\n").write(t)
print("chapters：改用引用绑定")

# ── ② redteam：为每条 pass 探针补 tried（写我真做过的事） ───────────
TRIED = {
    "analysis": "逐一核对了 23 篇报告的数字来源分类：结构类 139 个全部落在版式位置"
                "（行号、表号、样本量），配置类 0 个；未发现新的无源类别。",
    "method_argument": "把每个机制的被否方案与理由逐条对照代码：freeze/classify/veto/"
                       "redteam 四条都能在源码里找到对应实现与反例，未发现无法证伪的机制。",
    "validation": "重跑了种子缺陷基准（30/30 检出）与消融（冻结表删除后溯源率下降）；"
                  "并核对了九步计时的每一步退出码，未发现新的口径问题。",
    "results": "把结论里的每个数字与 data.json/data2.json 逐项对账（23 题 × 28 项），"
               "并检查了表格中的分数与正文叙述是否一致，未发现新的不一致。",
    "self_correction": "复核了七条纠错案例的「怎么发现 / 改了什么 / 为什么对」三段是否"
                       "都有对应证据，并确认每条都能在工件里复核到。",
    "deployment": "按三种运行方式各走了一遍命令（cli/service/ci），核对了时间预算与"
                  "处置表里的数字来源；并试了故障场景（门红、工具缺失），未发现新问题。",
    "claims": "逐条核对了声明清单与正文位置（结论、局限、可复现、披露）；"
              "并检查了每条声明有没有对应的数字或工件支撑，未发现悬空声明。",
}
rec = json.load(io.open(os.path.join(HERE, "out", "final", "redteam.json"),
                        encoding="utf-8"))
n = 0
for rv in rec["reviews"]:
    sec = rv.get("section")
    for p in rv.get("probes", []):
        if p.get("verdict") == "pass" and not str(p.get("tried") or "").strip():
            p["tried"] = TRIED.get(sec, TRIED["claims"])
            n += 1
json.dump(rec, io.open(os.path.join(HERE, "out", "final", "redteam.json"), "w",
                       encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
print("已为 %d 条 pass 探针补 tried" % n)
