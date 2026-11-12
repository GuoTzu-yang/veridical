# -*- coding: utf-8 -*-
"""notation-auditor probe 2 (deliverable form): symbol table x first body occurrence.

Read-only. Builds the cross-reference the board asks for:
  symbol | table meaning | table line | first body-math occurrence | body wording
and flags, per row, whether the body ever uses the symbol at all.

Source of truth: out/final/paper.tex math spans only (text-mode initials such as
"N.~A. Lazar" are not symbol uses), plus the included tab_*.tex files, because
the notation caption speaks about "this paper".
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FINAL = ROOT / "out" / "final"
PAPER = FINAL / "paper.tex"
TABLE_LO, TABLE_HI = 255, 278


def math_spans_in(text_lines):
    out = []
    for i, raw in enumerate(text_lines, 1):
        for m in re.finditer(r"(?<!\\)\$((?:[^$\\]|\\.)*?)(?<!\\)\$", raw):
            out.append((i, m.group(0), raw.strip()))
    return out


def main():
    plines = PAPER.read_text(encoding="utf-8").splitlines()
    tabfiles = {}
    for f in sorted(FINAL.glob("tab_*.tex")):
        tabfiles[f.name] = f.read_text(encoding="utf-8").splitlines()

    # table rows (symbol cells)
    rows = []
    for i in range(TABLE_LO - 1, min(TABLE_HI, len(plines))):
        m = re.match(r"^\$(?P<s>[^$]+)\$\s*&\s*(?P<m>[^&]*?)&(?P<n>.*?)\\\\?\s*$", plines[i].strip())
        if m:
            rows.append((i + 1, m.group("s").strip(), m.group("m").strip(), m.group("n").strip()))

    spans_paper = math_spans_in(plines)
    spans_tabs = {n: math_spans_in(L) for n, L in tabfiles.items()}

    print("| 符号 | 表内含义 | 表行 | 正文(含 tab_*.tex)首次出现 | 正文用词 |")
    print("|---|---|---|---|---|")
    for ln, sym, meaning, notes in rows:
        pat = re.compile(r"(?<![A-Za-z\\])" + re.escape(sym) + r"(?![A-Za-z])")
        body = [
            (L, raw)
            for L, span, raw in spans_paper
            if L > TABLE_HI and pat.search(span)
        ]
        tabhits = [
            (name, L, raw)
            for name, spans in spans_tabs.items()
            for L, span, raw in spans
            if pat.search(span)
        ]
        where = (
            f"paper.tex L{body[0][0]}" if body else (f"{tabhits[0][0]} L{tabhits[0][1]}" if tabhits else "无")
        )
        word = body[0][1][:70] if body else (tabhits[0][2][:70] if tabhits else "—")
        print(f"| ${sym}$ | {meaning} | L{ln} | {where} | {word} |")

    print("\n正文有、表里没有的数学符号：")
    for L, span, raw in spans_paper:
        if L > TABLE_LO and L < TABLE_HI:
            continue
        inner = span.strip("$")
        if re.fullmatch(r"[0-9.]+|\\times", inner):
            continue
        print(f"  paper.tex L{L}: {span}   <-- {raw[:90]}")
    for name, spans in spans_tabs.items():
        for L, span, raw in spans:
            print(f"  {name} L{L}: {span}   <-- {raw[:90]}")

    out = {
        "rows": [{"line": ln, "sym": s, "meaning": m, "notes": n} for ln, s, m, n in rows],
    }
    (ROOT / "tools" / "rtB_notation_r2_xref.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print("\n[wrote] tools/rtB_notation_r2_xref.json")


if __name__ == "__main__":
    main()
