import re
t = open("out/lang_zh/paper.tex", encoding="utf-8").read()
secs = re.findall(r"\\section\*?\{([^}]*)\}", t)
print("  中文版 %d 个章节:" % len(secs))
for x in secs:
    print("    " + x)
print()
from pypdf import PdfReader
r = PdfReader("out/lang_zh/paper.pdf")
t1 = r.pages[0].extract_text() or ""
print("  PDF %d 页；第1页中文字符 %d 个"
      % (len(r.pages), len(re.findall(r"[\u4e00-\u9fff]", t1))))
print("  第1页前 100 字: " + t1[:100].replace("\n", " "))