import io
import re

p = r"C:\Users\21246\Documents\deepseek-harness\default-workspace\aidc2026\big\main.tex"
t = io.open(p, encoding="utf-8", errors="replace").read()

lines = t.split("\n")
print("文件 %d 行 / %d 字符" % (len(lines), len(t)))
print()

depth = {"section": 0, "subsection": 0}
for i, ln in enumerate(lines, 1):
    m = re.match(r"\s*\\(section|subsection|subsubsection)\{(.+?)\}\s*$", ln)
    if m:
        kind, title = m.group(1), m.group(2)
        if kind == "section":
            depth["section"] += 1
            depth["subsection"] = 0
            print("L%-5d %2d. %s" % (i, depth["section"], title))
        elif kind == "subsection":
            depth["subsection"] += 1
            print("L%-5d      %d.%d %s" % (i, depth["section"], depth["subsection"], title))
        else:
            print("L%-5d          - %s" % (i, title))

print()
# 统计各类环境/元素
print("=== 元素统计 ===")
for name, pat in [
    ("figure 环境", r"\\begin\{figure"),
    ("table 环境", r"\\begin\{table"),
    ("tabular", r"\\begin\{tabular"),
    ("proposition", r"\\begin\{proposition"),
    ("proof", r"\\begin\{proof"),
    ("\\code{}", r"\\code\{"),
    ("\\cite", r"\\cite\{"),
    ("\\ref", r"\\ref\{"),
    ("\\label", r"\\label\{"),
]:
    print("  %-16s %d" % (name, len(re.findall(pat, t))))

# 参考文献
m = re.search(r"\\begin\{thebibliography\}(.*?)\\end\{thebibliography\}", t, re.S)
if m:
    print("  参考文献条目    %d" % len(re.findall(r"\\bibitem", m.group(1))))
else:
    print("  参考文献        无 thebibliography（可能用 bibtex）")
