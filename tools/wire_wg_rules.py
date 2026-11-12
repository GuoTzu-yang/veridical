#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 writing-guard 的 42 条正则规则接进 aitaste.py。

设计
----
· 按 category 分组报告（claim_calibration / rhetorical_pattern /
  llm_associated / academic_style / process_residue / formatting）
· 每条规则按 severity 计分：high 8 / medium 4 / low 2
· **不超过原作者的 maxHits**（防刷屏；这也是密度判据的近似）
· 新增部分分数上限 40，与原有 5 项分开算，避免把总分压死
"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "aitaste.py")
s = open(P, encoding="utf-8").read()

if "check_wg_rules" not in s:
    FUNC = '''

# ══ writing-guard 的 42 条规则（提取自 dsh-plugin-writing-guard 2.0.1）══
_WG = {"rules": None}
_WG_SEV = {"high": 8, "medium": 4, "low": 2}
_WG_CN = {
    "claim_calibration": "声称与证据距离",
    "rhetorical_pattern": "修辞套路",
    "llm_associated": "大模型高频词",
    "academic_style": "学术文风",
    "process_residue": "修改过程残留",
    "formatting": "排版习惯",
}


def _wg_rules():
    if _WG["rules"] is None:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "kb", "ai_rules.json")
        try:
            import json
            _WG["rules"] = json.load(open(p, encoding="utf-8"))["rules"]
        except Exception:                       # noqa: BLE001
            _WG["rules"] = []
    return _WG["rules"]


def check_wg_rules(t: str) -> dict:
    """按 writing-guard 的规则查，按 category 汇总。"""
    rules = _wg_rules()
    if not rules:
        return dict(name="细分规则", found=[], total=0, score=0,
                    by_cat={})
    by_cat, found, score = {}, [], 0
    for r in rules:
        try:
            cre = re.compile(r["regex"])
        except re.error:
            continue
        ms = cre.findall(t)
        if not ms:
            continue
        n = min(len(ms), r.get("maxHits", 99))
        cat = r.get("category", "?")
        by_cat[cat] = by_cat.get(cat, 0) + n
        score += _WG_SEV.get(r.get("severity", "low"), 2)
        found.append(dict(id=r["id"], cat=cat, n=n,
                          label=r.get("label", "")))
    found.sort(key=lambda x: -x["n"])
    return dict(name="细分规则", found=found, total=sum(by_cat.values()),
                score=min(40, score), by_cat=by_cat)


'''
    # 插在 analyze 之前
    k = s.find("def analyze(")
    s = s[:k] + FUNC + s[k:]

    # analyze 里加进去
    OLD = '''    checks = [check_ai_phrases(body), check_template(body),
              check_problem_list(body_nt), check_repetition(body),
              check_paragraphs(body)]'''
    NEW = '''    checks = [check_ai_phrases(body), check_template(body),
              check_problem_list(body_nt), check_repetition(body),
              check_paragraphs(body), check_wg_rules(body)]'''
    assert OLD in s, "analyze 锚点未匹配"
    s = s.replace(OLD, NEW, 1)

    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  aitaste.py 已接入 42 条规则")

import subprocess
import sys
r = subprocess.run([sys.executable, "aitaste.py", "out/fig/paper.tex"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
print(r.stdout[:2200])
