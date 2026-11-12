import re
t = open("out/runs/age_struct/paper.tex", encoding="utf-8").read()
print("  tex 里以 'not supported the sign' 开头的句子（前 3 个）：")
n = 0
for m in re.finditer(r"not supported the sign", t, re.I):
    s = t[max(0, m.start() - 130):m.start() + 170].replace("\n", " ")
    print("    ...%s..." % s)
    n += 1
    if n >= 3:
        break
print()
print("  出现总数:", len(re.findall(r"not supported the sign", t, re.I)))