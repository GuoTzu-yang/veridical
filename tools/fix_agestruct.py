import json
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(HERE, "runs.json")
cfg = json.load(open(P, encoding="utf-8"))
# 原来 y=80 - 84, x 含 "Reference date (as of 1 July)"（日期列）
# 日期当解释变量没有意义，而且论文里反复出现 "reference date as of"
# 把句式重复分推到 85。改成年轻年龄段预测老年段。
cfg["age_struct"] = {
    "data": "age_struct.xlsx",
    "y": "80 - 84",
    "x": "0 - 4,5 - 9,10 - 14,15 - 19,20 - 24",
    "min": "80 - 84,0 - 4,20 - 24",
    "problem": "age structure of national populations: young cohorts against the elderly",
    "out": "out/runs/age_struct",
}
json.dump(cfg, open(P, "w", encoding="utf-8", newline="\n"),
          ensure_ascii=False, indent=1)
print("  age_struct 配置已改（去掉日期列）")