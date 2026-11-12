# 探针4：主张有没有超出语料/对象范围而没说明边界
import io, json, os, time
root = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
F = os.path.join(root, "out", "final")
tex = io.open(os.path.join(F, "paper.tex"), encoding="utf-8").read()
lines = tex.splitlines()

def t(p):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(p)))

print("### A. 工件与成稿的时间/大小关系（采集脚本「读仓库状态」读的是哪一版）")
for n in ("paper.tex", "data.json", "data2.json", "deel.json"):
    p = os.path.join(F, n)
    if os.path.exists(p):
        print(f"  {n:<16} {os.path.getsize(p):>8} B  {t(p)}")
d2 = json.load(io.open(os.path.join(F, "data2.json"), encoding="utf-8"))
print("  data2.paper_bytes =", d2["paper_bytes"], " 成稿实际 =", os.path.getsize(os.path.join(F, "paper.tex")))
print("  data2.paper_words =", d2["paper_words"])
print("  data2.sections 条数 =", len(d2["sections"]))

print()
print("### B. 论文有没有引用这个「关于自己的」计数")
for i, ln in enumerate(lines, 1):
    if "7862" in ln or "7{,}862" in ln or "paper_words" in ln:
        print(f"  L{i}: {ln.strip()[:180]}")
print("  '7862' 出现次数:", tex.count("7862"))

print()
print("### C. 本节把自己限定在哪一层（逐句抄出边界声明）")
for i, ln in enumerate(lines[1200:1255], 1201):
    low = ln.lower()
    if any(k in low for k in ("corpus", "one author", "one corpus", "not claim",
                              "different object", "outside", "generalise", "generalize",
                              "measured separately", "two different")):
        print(f"  L{i}: {ln.strip()[:200]}")

print()
print("### D. 全称量词扫一遍：本节 + 声明表里「every/all/nothing else」出现在哪")
import re
for i, ln in enumerate(lines[1165:1272], 1166):
    if re.search(r"\bevery\b|\bEvery\b|\ball \d|\bnothing else\b|\bno [a-z]+ at all\b", ln):
        print(f"  L{i}: {ln.strip()[:200]}")