import re
t = open("out/runs/age_struct/paper.tex", encoding="utf-8").read()
print("  'reference date' 出现的上下文（前 5 处）：")
for m in list(re.finditer(r"[Rr]eference date", t))[:5]:
    s = t[max(0, m.start() - 100):m.start() + 70].replace("\n", " ")
    print("    ...%s..." % s[-150:])
print()
print("  含 'Reference date' 的列名前缀：")
for m in set(re.findall(r"[A-Za-z]*(?:Reference date)[A-Za-z ]*", t)):
    print("    %r" % m[:60])