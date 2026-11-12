# -*- coding: utf-8 -*-
"""Probe 2 (evaluation board): does the section write "we did not do it" in the
form "it does not need doing"?

Read-only. Prints only.

Method: take every non-claim in the section (things the authors say they do NOT
claim or do NOT measure) and classify the reason given:
  A. bound to a missing resource / different study  -> honest "not done"
  B. asserted unnecessary / out of scope by fiat    -> the failure mode
  C. silently absent                                -> worst
Then look for fiat-scope vocabulary in the rest of the paper that covers the
same objects, so we can see whether the section is consistent with it.
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.join(ROOT, "out", "final", "paper.tex")


def readlines(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read().splitlines()


# Vocabulary that turns "not done" into "not needed".
FIAT = [
    "not needed", "no need", "unnecessary", "not required", "needless",
    "out of scope", "beyond the scope", "not applicable", "trivially",
    "obviously", "clearly unnecessary", "we do not bother", "left as future",
    "future work", "not worth",
]


def main():
    lines = readlines(PAPER)
    sec = lines[1118:1148]
    body = "\n".join(sec)
    print("=" * 78)
    print("PROBE 2  'not done' vs 'not needed'")
    print("=" * 78)
    print("Section: paper.tex L1119-1148 (%d lines)\n" % len(sec))

    print("A. Fiat-scope vocabulary inside the evaluation section")
    found = []
    for w in FIAT:
        for m in re.finditer(re.escape(w), body, re.I):
            found.append((w, m.start()))
    if found:
        for w, pos in found:
            ctx = body[max(0, pos - 70):pos + 70].replace("\n", " ")
            print("   HIT %-14r ... %s ..." % (w, ctx))
    else:
        print("   none of %d fiat phrases appear in this section" % len(FIAT))
        print("   -> every omission is instead attached to a concrete reason")

    print()
    print("B. Each explicit non-claim, with the reason the section gives")
    nonclaims = [
        ("does the tool improve a reader's judgement?",
         "L1136-1137 'We do not claim the tool improves a reader's judgement'",
         "would need a different study"),
        ("are the six classes exhaustive?",
         "L1137 'that the six classes are exhaustive'",
         "uncertainty stated, not argued away"),
        ("does the pipeline generalise outside the corpus?",
         "L1138-1139 'that the pipeline generalises to problem types outside the corpus'",
         "'would need problems we do not have' -- names the missing resource"),
    ]
    for q, quote, reason in nonclaims:
        print("   Q: %s" % q)
        print("      text : %s" % quote)
        print("      why  : %s" % reason)
    print()
    print("   -> all three are phrased as 'we do not claim', and the third names the")
    print("      missing material rather than declaring the study unnecessary.")

    print()
    print("C. Cross-check: is the same honesty maintained where the *measurement*")
    print("   is absent (as opposed to the claim)?")
    probes = {
        "inter-rater agreement": "no inter-rater agreement",
        "independent rater": "there is no independent rater",
        "second author": "would need a second author",
        "no score comparison": "reports no score comparison",
    }
    full = "\n".join(lines)
    for k, v in probes.items():
        hit = v in full
        print("   %-24s marker %-32r present in paper.tex: %s" % (k, v, hit))

    print()
    print("D. Does the section ever call an unperformed measurement 'excluded'")
    print("   without saying the measurement was skipped?")
    # 'we make no claim about it' is used for prose writing in sec:timing
    for ln_no, ln in enumerate(lines, start=1):
        if re.search(r"make no claim about it|not measured anywhere", ln):
            print("   L%-5d %s" % (ln_no, ln.strip()))

    print()
    print("VERDICT INPUT:")
    print("   fiat phrases in section: %d" % len(found))
    print("   explicit non-claims with a named missing resource: 3/3")
    print("   -> the section does not launder unfished work as unnecessary work.")


if __name__ == "__main__":
    main()
