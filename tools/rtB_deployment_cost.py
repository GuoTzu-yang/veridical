# -*- coding: utf-8 -*-
"""rtB deployment board - probe 4: does the cost section separate machine time
from editorial time, and is the separation backed by numbers?

Read-only.
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.join(ROOT, "out", "final", "paper.tex")


def rd(p):
    return io.open(p, encoding="utf-8", errors="replace").read()


def main():
    lines = rd(PAPER).splitlines()
    sec = lines[1000:1118]

    print("=== A. the cost subsection as written (L1111-L1117) ===")
    for i in range(1110, 1117):
        print("  L%d: %s" % (i + 1, lines[i]))

    print("\n=== B. is machine time quantified? ===")
    for i, ln in enumerate(sec, start=1001):
        if re.search(r"\d+\.\d+\\,s|\d+\.\d+\s*s\b|seconds", ln):
            print("  L%d: %s" % (i, ln.strip()))

    print("\n=== C. is editorial time quantified anywhere in the section? ===")
    pat = re.compile(r"\b(hour|minute|day|days|week|round|rounds)\b", re.I)
    hits = [(i, ln.strip()) for i, ln in enumerate(sec, start=1001) if pat.search(ln)]
    for h in hits:
        print("  L%d: %s" % h)
    print("  any numeral attached to editorial time? %s"
          % bool(re.search(r"\d+\s*(hour|minute|day)", "\n".join(sec), re.I)))

    print("\n=== D. the paper's own statement about measuring prose time ===")
    for i, ln in enumerate(lines, start=1):
        if "not measured" in ln or "excluded" in ln:
            print("  L%d: %s" % (i, ln.strip()))

    print("\n=== E. 'no service dependency' vs mode 2 'a service to run' ===")
    for i, ln in enumerate(sec, start=1001):
        if "service" in ln:
            print("  L%d: %s" % (i, ln.strip()))

    print("\n=== F. is the chain really one process with no service? ===")
    for f in ("mmkit.py", "gate.py", "mcp_server.py"):
        p = os.path.join(ROOT, f)
        print("  %-14s exists=%s bytes=%s" % (f, os.path.exists(p), os.path.getsize(p) if os.path.exists(p) else "-"))
    mcp = rd(os.path.join(ROOT, "mcp_server.py"))
    print("  mcp_server.py is a long-running stdio service: %s"
          % ("while" in mcp or "readline" in mcp))
    print("  it exposes: %s"
          % re.findall(r'"name"\s*:\s*"(model1_[a-z_]+)"', mcp)[:12])

    print("\n=== G. the dominance claim: which side is measured? ===")
    print("  claim text: 'The dominant cost is editorial'")
    print("  machine side measured: 6.68 s total (frozen meta.timing_total)")
    print("  editorial side measured: %s"
          % ("no number anywhere in the section" if not re.search(r"\d+\s*(hour|minute|day)", "\n".join(sec), re.I) else "see C"))


if __name__ == "__main__":
    main()
