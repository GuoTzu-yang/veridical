#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 skillforCUMCM/math-modeling-skill-pro 的案例库接入我们的 kb/。

拿到的东西（本地使用，用户已确认）：
  cases/      140 张 md 案例卡 + index.csv（12 列可检索字段）
  knowledge/  11 份方法论文档（问题类型/模型选择/验证/创新/写作…）

价值对比：
  我们的 kb/cards/ 只有 3 张假设卡；这里是 139 个真实国赛案例的
  决策链 + 迁移规则 + 证据锚点。

做法：
  ① 复制到 kb/external/cumcm-pro/（不覆盖我们自己的 cards）
  ② 写一个检索器：题目特征 → 相似案例
"""
import csv
import os
import shutil

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(os.environ.get("TEMP", "/tmp"),
                   "cumcm_pro", "math-modeling-skill-pro-main")
DST = os.path.join(HERE, "kb", "external", "cumcm-pro")

if not os.path.isdir(SRC):
    raise SystemExit("源目录不存在: " + SRC)

if os.path.isdir(DST):
    shutil.rmtree(DST)
os.makedirs(DST, exist_ok=True)
n = 0
for sub in ("cases", "knowledge", "templates"):
    s = os.path.join(SRC, sub)
    if not os.path.isdir(s):
        continue
    d = os.path.join(DST, sub)
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(s):
        fp = os.path.join(s, f)
        if os.path.isfile(fp):
            shutil.copy2(fp, os.path.join(d, f))
            n += 1
# SKILL.md 里的决策规则也留着（方法论）
shutil.copy2(os.path.join(SRC, "SKILL.md"), os.path.join(DST, "SKILL.md"))
n += 1
print(f"  复制 {n} 个文件 → kb/external/cumcm-pro/")

# ── 检索器 ──
RET = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按题目特征检索相似国赛案例。

索引字段（cases/index.csv）：
    problem_types / models / validation_methods / core_problem /
    data_features

用法：
    python kb/external/cumcm-pro/search.py "多目标 优化 敏感性 无量纲"
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
IDX = os.path.join(HERE, "cases", "index.csv")

ALIAS = {
    "多目标": ["优化", "pareto", "多目标"],
    "优化": ["优化"],
    "敏感性": ["敏感性", "稳健", "鲁棒"],
    "无量纲": ["无量纲", "量纲"],
    "评价": ["评价"],
    "聚类": ["聚类"],
    "回归": ["回归"],
    "预测": ["预测"],
    "机理": ["机理", "微分", "ode", "pde"],
    "统计": ["统计", "检验"],
}


def search(query, top=6):
    if not os.path.exists(IDX):
        return []
    rows = list(csv.DictReader(open(IDX, encoding="utf-8-sig")))
    terms = [t for t in query.replace("，", " ").split() if t]
    scored = []
    for r in rows:
        blob = " ".join(str(r.get(k) or "") for k in
                        ("problem_types", "models", "validation_methods",
                         "core_problem", "data_features", "title")).lower()
        score = 0
        hit = []
        for t in terms:
            cands = ALIAS.get(t, [t])
            if any(c.lower() in blob for c in cands):
                score += 1
                hit.append(t)
        if score:
            scored.append((score, hit, r))
    scored.sort(key=lambda x: -x[0])
    return scored[:top]


def main(argv=None):
    a = sys.argv[1:] if argv is None else argv
    q = a[0] if a else "多目标 优化 敏感性"
    res = search(q, int(a[1]) if len(a) > 1 else 6)
    print(f"  查询: {q}")
    print(f"  命中 {len(res)} 个案例\\n")
    for sc, hit, r in res:
        print(f"  [{sc}] {r.get('case_id')} {r.get('year')} "
              f"{r.get('paper_code')}  {r.get('title')[:34]}")
        print(f"       类型: {r.get('problem_types')}")
        print(f"       模型: {str(r.get('models'))[:70]}")
        print(f"       验证: {str(r.get('validation_methods'))[:60]}")
        print(f"       命中: {hit}")
        print(f"       卡: {r.get('card_path')}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''
open(os.path.join(DST, "search.py"), "w",
     encoding="utf-8", newline="\n").write(RET)
print("  检索器已写入 kb/external/cumcm-pro/search.py")
