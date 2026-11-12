import json, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RP = os.path.join(HERE, "kb", "ai_rules.json")
d = json.load(open(RP, encoding="utf-8"))

# 按英文学术写作的实际密度设阈值（本文 7,623 词）
SET = {
    "rather-than-heavy": (30, "每千词 8.5 次；正常 2-4 次。30 对应约 4/千词。"),
    "hedge-density-en": (40, "每千词 1.3 次；正常 5-10 次。这条不该触发。"),
    "llm-buzzword-en": (10, "术语白名单已经挡掉 robust/leverage，余下按 10 计。"),
    "llm-verb-noun-overuse": (5, "同上。"),
    "limitations-across-sections": (3, "1 处不算分散；3 处以上才提示。"),
    "claim-evidence-proximity": (3, "否定与限定语境已挡；余下按 3 计。"),
    "em-dash-density": (3, "整篇 1 个破折号不算风格问题。"),
}
for r in d["rules"]:
    if r["id"] in SET:
        cap, why = SET[r["id"]]
        r["maxHits"] = cap
        r["threshold_note"] = why

json.dump(d, open(RP, "w", encoding="utf-8", newline="\n"),
          ensure_ascii=False, indent=1)
print("  set %d thresholds" % len(SET))