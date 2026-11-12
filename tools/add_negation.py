import json, os, ast
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 1) 给规则加 negation_guard 标记
RP = os.path.join(HERE, "kb", "ai_rules.json")
d = json.load(open(RP, encoding="utf-8"))
n = 0
for r in d["rules"]:
    if r["id"] == "claim-evidence-proximity":
        r["negation_guard"] = True
        r["guard_note"] = (
            "实测两处命中都是否定/限定语境：'these checks DO NOT prove'、"
            "'where that guarantee stops'。这两种恰恰是诚实表达，"
            "不该被当成强主张。命中位置前 40 字符内出现否定词就跳过。")
        n += 1
json.dump(d, open(RP, "w", encoding="utf-8", newline="\n"),
          ensure_ascii=False, indent=1)
print("  marked %d rule(s)" % n)

# 2) check_wg_rules 里加否定语境跳过
P = os.path.join(HERE, "aitaste.py")
s = open(P, encoding="utf-8").read()
if "negation_guard" not in s:
    OLD = """        ms = cre.findall(t)
        if not ms:
            continue
        n = min(len(ms), r.get("maxHits", 99))"""
    NEW = """        ms = cre.findall(t)
        if not ms:
            continue
        # 否定语境不算强主张。
        # 实测 claim-evidence-proximity 的两处命中分别是
        # "these checks **do not** prove" 和 "where that guarantee stops"，
        # 两条都是诚实表达，规则只看关键词就会把它们当缺陷。
        if r.get("negation_guard"):
            _NEG = ("not ", "cannot ", "never ", "no ", "none ",
                    "does not", "do not", "did not", "fail to",
                    "cannot be", "not a ")
            _kept = 0
            for m in cre.finditer(t):
                pre = t[max(0, m.start() - 40):m.start()].lower()
                if any(w in pre for w in _NEG):
                    continue
                _kept += 1
            if _kept == 0:
                continue
            n = min(_kept, r.get("maxHits", 99))
        else:
            n = min(len(ms), r.get("maxHits", 99))"""
    assert OLD in s, "no anchor"
    s = s.replace(OLD, NEW, 1)
    ast.parse(s)
    compile(s, P, "exec")
    open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("  negation_guard wired")