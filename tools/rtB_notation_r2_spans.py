# -*- coding: utf-8 -*-
"""notation-auditor probe 1 (v2): enumerate EVERY math span in paper.tex.

v1 regex mis-detected display math because `\\\\[` row-spacing looked like `\\[`,
which set a sticky in_display flag and swallowed the rest of the file. v2:
  * inline spans only, per line, with escaped \\$ respected,
  * display math detected by (?<!\\\\)\\\\\\[ and \\\\\\],
  * equation/align environments listed separately.
Prints the full span inventory (19-ish spans) so every claim about symbol use
can be checked against a literal line.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "out" / "final" / "paper.tex"
TABLE_LO, TABLE_HI = 255, 278


def main():
    lines = PAPER.read_text(encoding="utf-8").splitlines()
    spans = []
    for i, raw in enumerate(lines, 1):
        # inline $...$ pairs within one line, escaped \$ excluded
        for m in re.finditer(r"(?<!\\)\$((?:[^$\\]|\\.)*?)(?<!\\)\$", raw):
            spans.append((i, "inline", m.group(0)))
        if re.search(r"(?<!\\)\\\[", raw) or re.search(r"(?<!\\)\\\]", raw):
            spans.append((i, "display-marker", raw.strip()))
        if re.match(r"\s*\\begin\{(equation|align|gather|multline|eqnarray)\*?\}", raw):
            spans.append((i, "env", raw.strip()))
    print(f"total $ chars: {sum(l.count('$') for l in lines)}   spans found: {len(spans)}")
    for ln, kind, s in spans:
        print(f"  L{ln} [{kind}] {s}")
    json.dump(
        [[ln, kind, s] for ln, kind, s in spans],
        open(ROOT / "tools" / "rtB_notation_r2_spans.json", "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=1,
    )


if __name__ == "__main__":
    main()
