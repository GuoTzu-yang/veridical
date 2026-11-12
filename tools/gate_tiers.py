#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gate 分层：0 分项 / 半衰项 / 衰减项。

问题
----
现在 18 项是平权的：`??`（引用断裂，直接归零）和「图配色一般」
（扣几分）在报告里**同级**，都是 FAIL/WARN。读完不知道先修哪个。

依据
----
ultramath skill 库的《摘要写作增强》里写着评审的失分权重顺序：

    1. 先修 0 分项：缺结果、缺对应、方法笼统 —— 任一存在即归零风险
    2. 再修半衰项：创新淹没、验证单薄
    3. 最后修衰减项：衔接生硬、篇幅失控、术语不一致

做法
----
不改任何 chk_* 函数，只在 run_all 里给每条加 weight；
report 按三层分组，并给一句综合风险。
"""
import ast
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "gate.py")
s = open(P, encoding="utf-8").read()

if "GATE_WEIGHT" not in s:
    TABLE = '''# ── 失分层级 ──
# zero  一票归零：编译不过、数字不可溯源、引用断裂、领域污染…
# half  扣一半：摘要、摘要跨页、创新性、题型必做项
# decay 扣几分：措辞、图质量、反例
GATE_WEIGHT = {
    "compile": "zero",     # 编译不过就没有论文
    "pdf": "zero",         # 没有 PDF
    "numbers": "zero",     # 数字不可溯源 = 造假嫌疑
    "rules": "zero",       # 竞赛规则 7 项
    "bare_pct": "zero",    # 裸 % 会吞掉半句话（踩过）
    "refs": "zero",        # \\ref 断裂 = 正文印出 ??
    "domain": "zero",      # 领域污染 = 标题与摘要矛盾
    "leakage": "zero",     # 数据泄漏 = 方法论错误
    "math": "zero",        # 对拍不过 = 算错
    "abstract": "half",    # 评委 90 秒看摘要
    "abs_page": "half",    # 摘要跨页是格式硬伤
    "innovation": "half",  # 评审权重 30%
    "required": "half",    # 题型必做项漏了就少一块
    "rigor": "decay",      # 措辞
    "aitaste": "decay",    # AI 味
    "figures": "decay",    # 图质量
    "falsify": "decay",    # 反例
}
_ORDER = ("zero", "half", "decay")
_CN = {"zero": "0 分项", "half": "半衰项", "decay": "衰减项"}


'''
    k = s.find("def run_all(")
    s = s[:k] + TABLE + s[k:]

    # run_all：给每条加 weight，并返回分层统计
    OLD = '''    hard = [c for c in checks if c["tier"] == HARD]
    # 硬门：N/A 不算失败（还没到那一步），只有 FAIL 才算
    hard_ok = all(c["status"] in ("PASS", "N/A") for c in hard)
    return dict(
        checks=checks,
        all_pass=hard_ok,
        hard_fail=[c["id"] for c in hard if c["status"] == "FAIL"],
        warns=[c["id"] for c in checks if c["status"] == "WARN"],
        na=[c["id"] for c in checks if c["status"] == "N/A"],
    )'''
    NEW = '''    for c in checks:
        c["weight"] = GATE_WEIGHT.get(c["id"], "decay")
    hard = [c for c in checks if c["tier"] == HARD]
    # 硬门：N/A 不算失败（还没到那一步），只有 FAIL 才算
    hard_ok = all(c["status"] in ("PASS", "N/A") for c in hard)
    # 分层统计：每层「通过数 / 总数」+ 失败项
    tiers = {}
    for w in _ORDER:
        sub = [c for c in checks if c["weight"] == w]
        if not sub:
            continue
        ok = [c for c in sub if c["status"] in ("PASS", "N/A")]
        tiers[w] = dict(total=len(sub), ok=len(ok),
                        fail=[c["id"] for c in sub if c["status"] == "FAIL"],
                        warn=[c["id"] for c in sub if c["status"] == "WARN"])
    # 综合风险：有 0 分项失败 → 高；有半衰项失败 → 中；只有衰减 → 低
    if tiers.get("zero", {}).get("fail"):
        risk = "高（存在归零风险）"
    elif tiers.get("half", {}).get("fail"):
        risk = "中（关键项未过）"
    elif any(t.get("fail") for t in tiers.values()):
        risk = "低（仅衰减项）"
    else:
        risk = "低"
    return dict(
        checks=checks,
        all_pass=hard_ok,
        hard_fail=[c["id"] for c in hard if c["status"] == "FAIL"],
        warns=[c["id"] for c in checks if c["status"] == "WARN"],
        na=[c["id"] for c in checks if c["status"] == "N/A"],
        tiers=tiers,
        risk=risk,
    )'''
    assert OLD in s, "run_all 锚点未匹配"
    s = s.replace(OLD, NEW, 1)

    # report：先给分层摘要，再列明细
    OLD2 = '''    L = [f"质量门：{'通过' if r['all_pass'] else '未通过'}"
         f"（硬门失败 {len(r['hard_fail'])}，警告 {len(r['warns'])}，"
         f"未适用 {len(r['na'])}）", ""]'''
    NEW2 = '''    L = [f"质量门：{'通过' if r['all_pass'] else '未通过'}"
         f"（硬门失败 {len(r['hard_fail'])}，警告 {len(r['warns'])}，"
         f"未适用 {len(r['na'])}）", ""]
    # 先给按失分权重分的三层，再看明细
    for _w in _ORDER:
        _t = (r.get("tiers") or {}).get(_w)
        if not _t:
            continue
        _bad = _t["fail"] + _t["warn"]
        _mark = "OK  " if not _bad else ("FAIL" if _t["fail"] else "WARN")
        _tail = ("  ← " + ", ".join(_bad[:4])) if _bad else ""
        L.append(f"  [{_mark}] {_CN[_w]:<7}{_t['ok']}/{_t['total']} 通过"
                 + _tail)
    if r.get("risk"):
        L.append(f"  综合风险：{r['risk']}")
    L.append("")'''
    assert OLD2 in s, "report 锚点未匹配"
    s = s.replace(OLD2, NEW2, 1)

    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  gate 已分层")

import subprocess
import sys
r = subprocess.run([sys.executable, "gate.py", "out/fig"],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", cwd=HERE)
print(r.stdout)
