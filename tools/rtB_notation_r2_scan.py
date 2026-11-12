# -*- coding: utf-8 -*-
"""notation-auditor (role: notation-auditor) probe 1: raw facts about math usage.

Read-only over out/final/paper.tex. Prints:
  (a) the Notation table rows as written,
  (b) every math-mode occurrence of each table symbol with line numbers,
  (c) frequency + first line of every standalone math identifier, flagging
      identifiers that the table never defines,
  (d) "where ... is" style definitional sentences,
  (e) unit/dimension words attached to each symbol in the Notes column and
      in body lines that mention the symbol's quantity in words.
No edits to paper.tex or any .py.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "out" / "final" / "paper.tex"
TABLE_LO, TABLE_HI = 255, 278


def load():
    return PAPER.read_text(encoding="utf-8").splitlines()


def math_spans(lines):
    out = []
    in_disp = False
    for i, raw in enumerate(lines, 1):
        if "\\[" in raw:
            in_disp = True
        if in_disp:
            out.append((i, raw))
            if "\\]" in raw:
                in_disp = False
            continue
        for m in re.finditer(r"(?<!\\)\$([^$]{1,600}?)(?<!\\)\$", raw):
            out.append((i, m.group(0)))
        if re.match(r"\s*\\begin\{(equation|align|gather|multline)\*?\}", raw):
            out.append((i, raw))
    return out


ROW = re.compile(r"^\$(?P<sym>[^$]+)\$\s*&\s*(?P<meaning>[^&]*?)&(?P<notes>.*?)(\\\\)?\s*$")


def table_rows(lines):
    rows = []
    for i in range(TABLE_LO - 1, min(TABLE_HI, len(lines))):
        m = ROW.match(lines[i].strip())
        if m:
            rows.append(
                {
                    "line": i + 1,
                    "symbol": m.group("sym").strip(),
                    "meaning": m.group("meaning").strip(),
                    "notes": m.group("notes").strip(),
                }
            )
    return rows


def hits(lines, sym):
    """Math spans containing sym as a standalone identifier."""
    rx = re.compile(r"(?<![A-Za-z\\])" + re.escape(sym) + r"(?![A-Za-z])")
    seen = []
    for ln, span in math_spans(lines):
        if rx.search(span):
            seen.append((ln, lines[ln - 1].strip(), span))
    return seen


def identifiers(lines):
    freq, first, lines_at = {}, {}, {}
    for ln, span in math_spans(lines):
        for m in re.finditer(r"(?<!\\)([A-Za-z])(?![A-Za-z])", span):
            k = m.group(1)
            freq[k] = freq.get(k, 0) + 1
            first.setdefault(k, ln)
            lines_at.setdefault(k, []).append(ln)
    return freq, first, lines_at


def main():
    lines = load()
    rows = table_rows(lines)
    print("=== (a) notation table ===")
    for r in rows:
        print(f"L{r['line']}: ${r['symbol']}$ | meaning={r['meaning']!r} | notes={r['notes']!r}")
    print(f"table rows parsed: {len(rows)}  file lines: {len(lines)}")

    print("\n=== (b) per-symbol occurrences ===")
    for r in rows:
        sym = r["symbol"]
        hs = hits(lines, sym)
        early = [h for h in hs if h[0] < TABLE_LO]
        late = [h for h in hs if h[0] > TABLE_HI]
        print(f"\n--- ${sym}$ total={len(hs)} before_table={len(early)} after_table={len(late)}")
        for ln, ctx, form in early:
            print(f"  EARLY L{ln} [{form}] :: {ctx[:180]}")
        if late:
            print(f"  first_after_table L{late[0][0]}")
        for ln, ctx, form in late[:10]:
            print(f"  L{ln} [{form}] :: {ctx[:180]}")

    print("\n=== (c) math identifiers, frequency desc ===")
    freq, first, lines_at = identifiers(lines)
    tsyms = {r["symbol"] for r in rows}
    for k, v in sorted(freq.items(), key=lambda kv: -kv[1]):
        print(f"  {k}: n={v} first=L{first[k]} in_table={k in tsyms}")

    print("\n=== (c2) identifiers absent from table, n>=3 ===")
    for k, v in sorted(freq.items(), key=lambda kv: -kv[1]):
        if k not in tsyms and v >= 3:
            print(f"  {k}: n={v} first=L{first[k]} lines={lines_at[k][:15]}")

    print("\n=== (d) definitional sentences ===")
    for i, raw in enumerate(lines, 1):
        if re.search(r"\bwhere\b[^.]{0,80}\b(is|are|denotes|means)\b", raw) or re.search(
            r"\b(denote|denotes|we write|we call|written)\b", raw
        ):
            print(f"  L{i}: {raw.strip()[:190]}")

    print("\n=== (e) unit vocabulary ===")
    for r in rows:
        u = re.findall(r"\b(tokens?|rows?|ratio|level|set|digest|classes?|length|per|sub-range)\b", r["notes"])
        print(f"  ${r['symbol']}$: {u}")
    print("\n  body lines containing quantity words:")
    for i, raw in enumerate(lines, 1):
        if re.search(r"\b(window|rows?|tokens?|per scope|tracing rate|digest)\b", raw, re.I):
            print(f"  L{i}: {raw.strip()[:190]}")

    json.dump(
        {"rows": rows, "freq": freq, "first": first},
        open(ROOT / "tools" / "rtB_notation_r2_facts.json", "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=1,
    )
    print("\n[wrote] tools/rtB_notation_r2_facts.json")


if __name__ == "__main__":
    main()
