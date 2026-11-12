# 探针1：每条主张是否都有证据指针 —— 只读 paper.tex 与工件清单
import io, json, os, re
root = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\model1-arch"
tex = io.open(os.path.join(root, "out", "final", "paper.tex"), encoding="utf-8").read()
lines = tex.splitlines()

print("### A. claims 表六行的三列（L1166-L1199）")
seg = "\n".join(lines[1165:1199])
rows = [r for r in seg.split("\\\\") if "&" in r]
print("行数:", len(rows))
for i, r in enumerate(rows, 1):
    cells = [c.strip().replace("\n", " ") for c in r.split("&")]
    print(f"  [{i}] Claim={cells[0][:60]!r}")
    print(f"      Evidence={cells[1][:70]!r}")
    print(f"      NotSupported={cells[2][:70]!r}")
    has_ptr = bool(re.search(r"\\(ref|S?ection)|Table~|Section~|ledger|log", cells[1]))
    print(f"      指针存在={has_ptr}  第三列非空={bool(cells[2])}")

print()
print("### B. 复现清单六步（L1209-L1225）里有没有生成冻结表的脚本")
seg2 = lines[1208:1225]
for i, ln in enumerate(seg2, 1209):
    print(f"  {i}: {ln}")
cmds = re.findall(r"tools/[A-Za-z0-9_\\]+\.py|gate\.py", "\n".join(seg2))
print("清单里出现的脚本:", [c.replace("\\_", "_") for c in cmds])
fr = [c for c in cmds if "freeze" in c.replace("\\", "")]
print("清单里与 freeze/冻结表 有关的脚本:", fr)
print("tools/ 下确实存在 freeze_paper_numbers.py:",
      os.path.exists(os.path.join(root, "tools", "freeze_paper_numbers.py")))
print("out/final 下确实存在冻结表 冻结数字.json:",
      os.path.exists(os.path.join(root, "out", "final", "冻结数字.json")))

print()
print("### C. 论文里点名了冻结表的文件名吗")
print("  出现 '冻结数字' 次数:", tex.count("冻结数字"))
print("  出现 'freeze_paper_numbers' 次数:", tex.count("freeze_paper_numbers"))
print("  出现 'frozen table' 次数:", tex.count("frozen table"))
n292 = [i + 1 for i, ln in enumerate(lines) if "frozen table built from the measurement artifacts" in ln]
print("  'frozen table built from the measurement artifacts' 所在行:", n292)
for i in n292:
    print("   ", i, lines[i - 1].strip()[:230])

print()
print("### D. 探针1要的一句：单一 JSON 工件 vs 两个采集脚本")
for i, ln in enumerate(lines, 1):
    if "one collection script" in ln or "collect\\_paper\\_data2.py" in ln or "out/final/data.json" in ln:
        print(f"  {i}: {ln.strip()[:200]}")
print("  out/final/data.json 存在:", os.path.exists(os.path.join(root,"out","final","data.json")))
print("  out/final/data2.json 存在:", os.path.exists(os.path.join(root,"out","final","data2.json")))