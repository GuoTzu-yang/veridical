import os
import zlib
import re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = None
for root, dirs, files in os.walk(os.path.join(HERE, "external")):
    for f in files:
        if f == "2026_MCM_Problem_C.pdf":
            p = os.path.join(root, f)
print("  PDF:", p.replace(HERE, ".") if p else "未找到")
if p:
    raw = open(p, "rb").read()
    print("  大小: %d 字节" % len(raw))
    # 尝试提取文本流
    txts = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", raw, re.S):
        blob = m.group(1)
        try:
            d = zlib.decompress(blob)
        except Exception:
            d = blob
        if b"Tj" in d or b"TJ" in d:
            txts.append(d)
    print("  含文本的流: %d" % len(txts))
    out = []
    for d in txts[:12]:
        for m2 in re.finditer(rb"\((?:[^()\\]|\\.)*\)", d):
            s = m2.group(0)[1:-1]
            s = s.replace(b"\\(", b"(").replace(b"\\)", b")").replace(b"\\\\", b"\\")
            try:
                out.append(s.decode("latin-1"))
            except Exception:
                pass
    txt = " ".join(out)
    txt = re.sub(r"\s+", " ", txt)
    print()
    print("  === 题面文本（前 2600 字）===")
    print(txt[:2600])