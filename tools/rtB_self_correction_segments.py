# -*- coding: utf-8 -*-
"""Read-only probe 1: segment completeness of section 'What was wrong' (L864-1000).

Parses paper.tex by \\subsection and checks which of the four required parts
(Wrong / How found / Change / Why this is right) are present, plus the word
count of each part. Prints only; writes nothing.
"""
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEX = os.path.join(ROOT, "out", "final", "paper.tex")

with open(TEX, "r", encoding="utf-8") as f:
    lines = f.read().split("\n")

start, end = 864, 1000          # 1-based inclusive
block = lines[start - 1:end]

# collect subsection boundaries inside the block
subs = []
for i, ln in enumerate(block):
    m = re.match(r"\\subsection\{(.+?)\}", ln)
    if m:
        subs.append((i, m.group(1)))

print("block lines:", start, "-", end, " len:", len(block))
print("subsections found:", len(subs))
for i, t in subs:
    print("  L%d  %s" % (start + i, t))

PARTS = ["Wrong.", "How found.", "Change.", "Why this is right."]

for idx, (i, title) in enumerate(subs):
    j = subs[idx + 1][0] if idx + 1 < len(subs) else len(block)
    body = "\n".join(block[i:j])
    # strip trailing \subsection line itself and any "draft" markers
    print("=" * 78)
    print("CASE:", title)
    print("  span L%d-L%d, %d chars" % (start + i, start + j - 1, len(body)))
    found = {}
    for p in PARTS:
        m = re.search(re.escape("\\emph{" + p + "}"), body)
        found[p] = (m.start() if m else -1)
    print("  parts present:", {p: (pos >= 0) for p, pos in found.items()})
    # text of each part up to the next part marker
    order = sorted([(pos, p) for p, pos in found.items() if pos >= 0])
    for k, (pos, p) in enumerate(order):
        nxt = order[k + 1][0] if k + 1 < len(order) else len(body)
        seg = body[pos:nxt].strip()
        seg = re.sub(r"\s+", " ", seg)
        print("  --- %s  (%d chars)" % (p, len(seg)))
        print("      " + seg[:600])
