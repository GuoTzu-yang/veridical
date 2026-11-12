# 探针2：每条主张是否写明「哪里没支撑」 —— 只读
import io, json, os, re
root = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
tex = io.open(os.path.join(root, "out", "final", "paper.tex"), encoding="utf-8").read()
lines = tex.splitlines()

print("### A. 本节（L1201-L1271）里的全称句，逐句看有没有配套的「没支撑」")
seg = lines[1200:1271]
pat = re.compile(r"\bEvery\b|\bevery\b|\bno [a-z]+ at all\b|\bnone was\b|\bnothing else\b")
hits = []
for i, ln in enumerate(seg, 1201):
    if pat.search(ln):
        hits.append((i, ln.strip()))
for i, ln in hits:
    print(f"  L{i}: {ln[:210]}")
print("  全称句计数:", len(hits))

print()
print("### B. 这些全称句周边有没有「局限/未支撑/不支持」的字样")
for i, _ln in hits:
    win = "\n".join(lines[max(0, i - 4):i + 4])
    has = any(k in win for k in ("Not supported", "not supported", "weak", "Weak",
                                 "limitation", "Limitation", "does not claim",
                                 "caveat", "cannot"))
    print(f"  L{i}: 邻域有「未支撑/局限」字样={has}")

print()
print("### C. 本节自己声明的「两件不同的对象」边界写了什么")
for i, ln in enumerate(lines[1226:1233], 1227):
    print(f"  {i}: {ln.strip()[:200]}")

print()
print("### D. 密度图图注的量化主张，背后工件是不是空的")
cap = "\n".join(lines[1255:1263])
print("  图注原文:")
for i, ln in enumerate(lines[1255:1263], 1256):
    print(f"    {i}: {ln}")
d2 = json.load(io.open(os.path.join(root, "out", "final", "data2.json"), encoding="utf-8"))
print("  data2.json['sections'] =", json.dumps(d2["sections"], ensure_ascii=False),
      " len =", len(d2["sections"]))
print("  data2.json['paper_words'] =", d2["paper_words"])
src = io.open(os.path.join(root, "tools", "make_final_figs2.py"), encoding="utf-8").read()
print("  画图脚本对空 sections 的处理:",
      [l.strip() for l in src.splitlines() if "if not S" in l])
import os as _o
fp = os.path.join(root, "out", "final", "fig", "fig16_sections.pdf")
print("  fig16_sections.pdf 存在:", _o.path.exists(fp),
      "大小:", _o.path.getsize(fp) if _o.path.exists(fp) else None)
import time
print("  fig16_sections.pdf 时间:", time.strftime("%Y-%m-%d %H:%M:%S",
      time.localtime(_o.path.getmtime(fp))))
print("  paper.tex 时间:", time.strftime("%Y-%m-%d %H:%M:%S",
      time.localtime(_o.path.getmtime(os.path.join(root,"out","final","paper.tex")))))
print("  data2.json 时间:", time.strftime("%Y-%m-%d %H:%M:%S",
      time.localtime(_o.path.getmtime(os.path.join(root,"out","final","data2.json")))))