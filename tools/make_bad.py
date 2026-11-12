import json
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 故意做的三份「坏提案」——LLM 最典型的三种走偏
CASES = {
    "bad1_empty.json": {
        "proposals": [
            {"route_id": "A", "title": "用物理机理建模",
             "method": "physics", "method_args": {},
             "success_criteria": {}, "falsifiable_assumption": ""},
            {"route_id": "B", "title": "用深度学习",
             "method": "deep learning", "method_args": {},
             "success_criteria": {}, "falsifiable_assumption": ""},
            {"route_id": "C", "title": "综合各种方法",
             "method": "ensemble", "method_args": {},
             "success_criteria": {}, "falsifiable_assumption": ""},
        ]
    },
    "bad2_same.json": {
        "proposals": [
            {"route_id": "A", "title": "回x1", "method": "run",
             "method_args": {"--data": "x.xlsx", "--y": "y", "--x": "a"},
             "success_criteria": {"cv_rmse_max": 1e9},
             "falsifiable_assumption": "a"},
            {"route_id": "B", "title": "回x1", "method": "run",
             "method_args": {"--data": "x.xlsx", "--y": "y", "--x": "a"},
             "success_criteria": {"cv_rmse_max": 1e9},
             "falsifiable_assumption": "a"},
            {"route_id": "C", "title": "回x1", "method": "run",
             "method_args": {"--data": "x.xlsx", "--y": "y", "--x": "a"},
             "success_criteria": {"cv_rmse_max": 1e9},
             "falsifiable_assumption": "a"},
        ]
    },
}
d = os.path.join(HERE, "out", "proposals")
os.makedirs(d, exist_ok=True)
for name, obj in CASES.items():
    p = os.path.join(d, name)
    json.dump(obj, open(p, "w", encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=1)
    print("  写出 %s（%d 条）" % (name, len(obj["proposals"])))