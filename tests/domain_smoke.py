#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""领域层回归：假设与公式必须按学科走，不能全用统计模板。

评审原话：「用纯线性回归去拟合…缺乏物理机理的支撑」。
这里钉住三件事：判对领域、假设是专业假设、公式与无量纲数真的进了论文。
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

import domain  # noqa: E402
import mm  # noqa: E402
import paper  # noqa: E402

bad = 0
n = 0


def ck(name, cond, detail=""):
    global bad, n
    n += 1
    if cond:
        print(f"  [PASS] {name}" + (f"  — {detail}" if detail else ""))
    else:
        bad += 1
        print(f"  [FAIL] {name}" + (f"  — {detail}" if detail else ""))


print("=" * 74)
print("一、领域识别（词边界，不能被 alpha 里的 ph 误伤）")
print("=" * 74)
ck("无关键词 → generic",
   domain.detect(["alpha", "beta", "gamma"], "")["key"] == "generic",
   domain.detect(["alpha", "beta", "gamma"], "")["key"])
ck("水厂列名 → water",
   domain.detect(["R/W PH", "NTU", "ALUM"], "")["key"] == "water")
ck("热管理 → heat_transfer",
   domain.detect(["热阻", "压降"],
                 "manifold heat sink")["key"] == "heat_transfer")
ck("'-' 之类的分隔符不会造成误匹配",
   domain.detect(["a-b", "c"], "")["key"] == "generic")

print()
print("=" * 74)
print("二、假设必须是专业假设，不是通用统计套话")
print("=" * 74)
det = domain.detect(["热阻", "压降"], "heat sink cooling")
a = domain.assumptions(det, 84)
ck("5 条以内", len(a) <= 5, str(len(a)))
joined = " ".join(a).lower()
ck("提到不可压/稳态", "incompressible" in joined or "steady" in joined,
   [x for x in a if "incompressible" in x.lower()][:1])
ck("提到辐射被忽略", "radiation" in joined,
   [x for x in a if "radiation" in x.lower()][:1])
ck("不含纯统计套话（'independent of each other'）",
   "independent of each other" not in joined, "已换成领域假设")
ck("小样本会补一条样本量说明", any("84" in x for x in a),
   [x for x in a if "84" in x][:1])

print()
print("=" * 74)
print("三、公式与无量纲数")
print("=" * 74)
eq, eq2 = domain.equations(det)
ck("有主公式", len(eq) > 100, f"{len(eq)} 字符")
ck("含 Nu 与 Re", "Nu" in eq and "Re" in eq, "Nusselt / Reynolds")
ck("有补充公式（性能指标）", len(eq2) > 50, f"{len(eq2)} 字符")
nums = domain.numbers_table(det)
ck("无量纲数 >= 2 个", len(nums) >= 2, str([x[0] for x in nums]))
ck("含 Reynolds number", any("Reynolds" in x[2] for x in nums))

print()
print("=" * 74)
print("四、生成的论文里真的有这些（不是只写在模块里）")
print("=" * 74)
xlsx = mm.find_xlsx()
if xlsx:
    ds = mm.DS(xlsx)
    ctx = dict(

        mechanism_mode="full",
    # 测试验证的是「完整机理」路径，显式指定 full；

    # 生产默认是 auto（按题型识别）。title="T", team="2600001",
               problem="optimising a manifold heat sink for chip cooling",
               y="无量纲热阻", x=["针肋宽度比", "歧管深高比"],
               n_rows=ds.n_rows, n_cols=len(ds.num_names))
    tex = paper.build(ctx)
    # 章节改名后是 "Model: governing relations"，大小写不同。
    # 这条断言防的是「领域层的控制方程没进论文」，不削弱它。
    ck("论文里有 governing relations 段",
       "governing relations" in tex.lower())
    ck("论文里有无量纲数表", "dimensionless" in tex.lower())
    ck("论文里有 Nu = C 公式", "Nu = C" in tex)
    ck("论文里有 Reynolds number", "Reynolds number" in tex)
    ck("论文里没有中文", not re.search(r"[\u4e00-\u9fff]", tex),
       f"{len(re.findall(chr(91)+chr(92)+'u4e00-'+chr(92)+'u9fff'+chr(93), tex))} 处")
    ck("领域名是英文", "heat transfer and thermal management" in tex,
       "det['domain']['en']")

print()
print("=" * 74)
print(f"{'ALL PASS' if bad == 0 else 'FAILED'}  {n - bad} 通过 / {bad} 失败")
print("=" * 74)
raise SystemExit(0 if bad == 0 else 1)
