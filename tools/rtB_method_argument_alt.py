# -*- coding: utf-8 -*-
"""Red-team probe (board: method_argument, role: alternative-auditor).

READ-ONLY. Prints only. Never writes to paper.tex or any source file.

Four probes:
  P1 every method paired with a rejected alternative?
  P2 are the rejection reasons falsifiable?
  P3 is implementation convenience sold as methodological superiority?
  P4 are costs given as measured values rather than adjectives?
"""
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out", "final")
PAPER = os.path.join(OUT, "paper.tex")

SEC_FIRST = r"\section{Method: model building, and why these choices}"
SEC_END = r"\section{Validation}"


def rd(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def line_of(text, needle):
    """1-based line number of the first line containing needle verbatim, else None."""
    for i, line in enumerate(text.split("\n"), 1):
        if needle in line:
            return i
    return None


def hr(title):
    print("")
    print("=" * 78)
    print(title)
    print("=" * 78)


def main():
    paper = rd(PAPER)
    lines = paper.split("\n")

    i0 = next(i for i, l in enumerate(lines) if SEC_FIRST in l)
    i1 = next(i for i, l in enumerate(lines) if SEC_END in l)
    print("board span: lines %d-%d (%d lines)" % (i0 + 1, i1, i1 - i0))
    body = "\n".join(lines[i0:i1])

    # =====================================================================
    hr("P1  every method paired with a rejected alternative?")
    # =====================================================================
    universal = "Every mechanism below displaced an alternative"
    print("universal claim, line %s:" % line_of(paper, universal))
    print("  " + [l for l in lines if universal in l][0].strip())
    print("\nsecond instance of the same claim:")
    for m in re.finditer(r"what would change our mind", paper):
        ln = paper[:m.start()].count("\n") + 1
        print("  line %d | %s" % (ln, lines[ln - 1].strip()[:130]))

    print("\nalternative-introducing phrases inside the board:")
    for pat in [r"reject", r"instead of", r"rather than", r"displaced", r"not by\b"]:
        for m in re.finditer(pat, body, re.I):
            ln = i0 + 1 + body[:m.start()].count("\n")
            ctx = body[max(0, m.start() - 70):m.start() + 70].replace("\n", " ")
            print("  %-12s line=%d ...%s..." % (pat, ln, ctx))

    print("\nthe six table rows (Mechanism | Rejected alternative | Why):")
    t0 = next(i for i, l in enumerate(lines) if "Mechanism & Rejected alternative" in l)
    t1 = next(i for i, l in enumerate(lines) if "label{tab:methods}" in l)
    for i in range(t0 + 1, t1):
        s = lines[i].strip()
        if s and not s.startswith(("\\midrule", "\\bottomrule", "\\end{tabular}")):
            print("  L%d: %s" % (i + 1, s))

    print("\nfalsifier inventory:")
    print("  'Would change'      in paper.tex = %d" % len(re.findall(r"Would change", paper)))
    print("  'Would change if'   in paper.tex = %d" % len(re.findall(r"Would change if", paper)))
    print("  'would change our mind' in paper.tex = %d"
          % len(re.findall(r"would change our mind", paper)))

    print("\nnon-row methods in the board (do they name a rejected alternative?):")
    for name, anchor in [
        ("Baseline model construction", "the same generation path with its provenance artifact deleted"),
        ("Baseline defended as non-straw-man", "It is not a straw man"),
        ("Comparison case selection", "The hand-built competition report is the comparison case"),
        ("Solution procedure division of labour", "is deliberately outside it"),
        ("Gate composition (two tiers)", "29 checks, 12 hard"),
        ("Construction over search", "by construction rather than"),
        ("Context load: no window enlargement", "We do not attempt to fix"),
    ]:
        ln = line_of(paper, anchor)
        print("  %-40s line=%-5s in_board=%-5s" % (name, ln, ln is not None and i0 < ln - 1 < i1))

    # =====================================================================
    hr("P2  are the rejection reasons falsifiable?")
    # =====================================================================
    print("search for falsifier language anywhere in the board:")
    for pat in [r"would change", r"would abandon", r"would revise", r"would stop",
                r"refut", r"if .{0,30}exceeded", r"we would"]:
        hits = list(re.finditer(pat, body, re.I))
        print("  %-24s hits=%d" % (pat, len(hits)))
        for m in hits[:3]:
            ln = i0 + 1 + body[:m.start()].count("\n")
            print("      L%d ...%s..." % (ln, body[max(0, m.start() - 70):m.start() + 80].replace("\n", " ")))

    print("\nrow 1 falsifier, verbatim (the only one):")
    for i, l in enumerate(lines):
        if "Would change if" in l:
            print("  L%d: %s" % (i + 1, l.strip()))
            print("  L%d: %s" % (i + 2, lines[i + 1].strip()))

    print("\noperability of that falsifier needs a 'writing cost' number:")
    print("  'writing cost' in paper.tex      = %d" % paper.count("writing cost"))
    for name in sorted(os.listdir(OUT)):
        p = os.path.join(OUT, name)
        if not os.path.isfile(p) or os.path.splitext(name)[1].lower() not in (".tex", ".json", ".md"):
            continue
        try:
            s = rd(p)
        except (UnicodeDecodeError, OSError):
            continue
        if "writing cost" in s:
            print("  'writing cost' also in: %s" % name)
    print("  paper's own position on prose-writing cost:")
    for i, l in enumerate(lines):
        if "Prose writing is" in l or "is not measured anywhere in this paper" in l:
            print("    L%d: %s" % (i + 1, l.strip()))

    # =====================================================================
    hr("P3  is implementation convenience sold as superiority?")
    # =====================================================================
    for anchor in ["by construction rather than", "not a fitted object, which is why the paper reports",
                   "is deliberately outside it", "the tool never writes the"]:
        print("  anchor line=%-5s | %s" % (line_of(paper, anchor), anchor))
    print("\nfull paragraph, L301-306:")
    for i in range(300, 306):
        print("  L%d: %s" % (i + 1, lines[i]))
    print("\nfull paragraph, L413-419:")
    for i in range(412, 419):
        print("  L%d: %s" % (i + 1, lines[i]))
    print("\n'which is why' / 'because it is easier' style connectors inside the board:")
    for pat in [r"which is why", r"is why the paper", r"therefore", r"so that we", r"easier"]:
        for m in re.finditer(pat, body, re.I):
            ln = i0 + 1 + body[:m.start()].count("\n")
            print("  %-14s L%d ...%s..." % (pat, ln, body[max(0, m.start() - 70):m.start() + 90].replace("\n", " ")))

    # =====================================================================
    hr("P4  costs: measured values or adjectives?")
    # =====================================================================
    print("adjective / vague-quantifier cost forms inside the board:")
    for a in ["handful", "expensive", "cheap", "negligible", "trivial", "a few", "modest",
              "nothing here is", "small enough", "plenty"]:
        for m in re.finditer(re.escape(a), body, re.I):
            ln = i0 + 1 + body[:m.start()].count("\n")
            print("  '%s' L%d ...%s..." % (a, ln, body[max(0, m.start() - 85):m.start() + 85].replace("\n", " ")))

    print("\nmeasured numbers stated inside the board:")
    for pat in [r"0\.12", r"\b11\b", r"\b357\b", r"\b15161\b", r"\b713\b", r"\b39\b", r"1\.6", r"29 checks"]:
        print("  %-10s -> %d" % (pat, len(re.findall(pat, body))))

    fz = os.path.join(OUT, "冻结数字.json")
    fztxt = rd(fz)
    fzd = json.loads(fztxt)
    items = fzd["items"]
    print("\nfrozen table: %d items, unique paths=%d" % (len(items), len({it["path"] for it in items})))
    print("  string '0.12' present in frozen table JSON: %s" % ("0.12" in fztxt))
    print("  context.* entries:")
    for it in items:
        if it["path"].startswith("context."):
            print("    %s = %s" % (it["path"], it["value"]))

    d2 = json.loads(rd(os.path.join(OUT, "data2.json")))
    print("\n  data2 runtimes (the only measured per-command seconds):")
    for r in d2["runtimes"]:
        print("    %-12s %.2f s" % (r["cmd"], r["seconds"]))
    tim = rd(os.path.join(OUT, "tab_timing.tex"))
    print("  tab_timing.tex, trace/gate rows:")
    for l in tim.split("\n"):
        if "trace" in l or "gate" in l:
            print("    " + l.strip())

    cm = json.loads(rd(os.path.join(OUT, "context_metrics.json")))
    ctx = rd(os.path.join(OUT, "tab_context.tex"))
    print("\n  context_metrics.json: paper_tokens=%s n_frozen=%s n_distinct_all=%s median_load=%s"
          % (cm["paper_tokens"], cm["n_frozen"], cm["n_distinct_all"], cm["median_load"]))
    print("  tab_context.tex whole-paper / frozen rows:")
    for l in ctx.split("\n"):
        if "whole paper" in l or "frozen table" in l:
            print("    " + l.strip())
    print("  board prose (L376): %s" % lines[375].strip())
    withs = sorted(s["distinct"] for s in cm["sections"] if s["distinct"] > 0)
    n = len(withs)
    med = (withs[n // 2 - 1] + withs[n // 2]) / 2.0 if n % 2 == 0 else withs[n // 2]
    print("  loads of the %d sections quoting a number: %s" % (n, withs))
    print("  arithmetic median = %s ; context_metrics median_load = %s" % (med, cm["median_load"]))

    # =====================================================================
    hr("EVIDENCE MARKER SELF-CHECK (every marker cited in the deliverable)")
    # =====================================================================
    markers = [
        (PAPER, "Every mechanism below displaced an alternative"),
        (PAPER, "It is not a straw man"),
        (PAPER, "The hand-built competition report is the comparison case"),
        (PAPER, "is deliberately outside it"),
        (PAPER, "29 checks, 12 hard"),
        (PAPER, "Would change if"),
        (PAPER, "would change our mind"),
        (PAPER, "not a fitted object, which is why the paper reports"),
        (PAPER, "measured at 0.12"),
        (PAPER, "is not measured anywhere in this paper"),
        (PAPER, "handful of tokens"),
        (PAPER, "nothing here is"),
        (PAPER, "frozen table has 713 entries"),
        (os.path.join(OUT, "tab_context.tex"), "frozen table, all items"),
        (os.path.join(OUT, "tab_context.tex"), "15304"),
    ]
    ok = True
    for path, mk in markers:
        txt = rd(path)
        ln = line_of(txt, mk)
        rel = os.path.relpath(path, ROOT).replace("\\", "/")
        print("  %-28s %-52s -> line %s" % (rel, mk[:52], ln))
        if ln is None:
            ok = False
    print("\nALL CITED MARKERS VERBATIM ON ONE LINE: %s" % ok)
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
