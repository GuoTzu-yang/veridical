# -*- coding: utf-8 -*-
"""rtB deployment board - probe 3: is the failure playbook executable?

Read-only. For every row of tab:playbook it checks whether the "First response"
cell names something that exists on disk (a command, a flag, an artifact),
and whether a failure mode documented in the same section has a row at all.
"""
import io
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.join(ROOT, "out", "final", "paper.tex")


def rd(p):
    return io.open(p, encoding="utf-8", errors="replace").read()


def main():
    lines = rd(PAPER).splitlines()
    sec = lines[1000:1118]
    txt = "\n".join(sec)

    print("=== A. playbook table rows (L1088-L1109) ===")
    body = lines[1093:1104]  # rows between midrule and bottomrule
    rows = []
    cur = []
    for ln in body:
        cur.append(ln)
        if ln.rstrip().endswith("\\\\"):
            rows.append(" ".join(cur))
            cur = []
    for i, r in enumerate(rows, start=1):
        cells = [c.strip() for c in r.replace("\\\\", "").split("&")]
        print("  row %d: %d cells" % (i, len(cells)))
        for j, c in enumerate(cells):
            print("      [%d] %s" % (j, c))

    print("\n=== B. does each 'First response' name a runnable thing? ===")
    schema = json.load(io.open(os.path.join(ROOT, "schema.json"), encoding="utf-8"))
    cmds = sorted(schema["commands"].keys())
    print("  schema subcommands: %s" % cmds)
    paper = rd(PAPER)
    for word in ("profile", "profiler"):
        print("  paper contains %-9r: %d occurrence(s)" % (word, paper.count(word)))
    for i, ln in enumerate(lines, start=1):
        if "profiler" in ln:
            print("     L%d: %s" % (i, ln.strip()))
    # is 'profile' ever given as a command with the entry point?
    print("  paper gives 'mmkit.py profile' or ' profile --': %s"
          % bool(re.search(r"profile\s+--|mmkit\.py\s+profile", paper)))

    print("\n=== C. row 4 flag exists? ===")
    gate = rd(os.path.join(ROOT, "gate.py"))
    print("  '--stamp' in gate.py: %s" % ("--stamp" in gate))
    for i, ln in enumerate(gate.splitlines(), start=1):
        if "--stamp" in ln:
            print("     gate.py L%d: %s" % (i, ln.strip()[:120]))

    print("\n=== D. row 3 ('not applicable'): is there an artifact to inspect? ===")
    for word in ("N/A", "not applicable", "n/a"):
        hits = [(i, ln.strip()) for i, ln in enumerate(gate.splitlines(), start=1) if word in ln]
        print("  gate.py %-14r occurrences: %d" % (word, len(hits)))
        for h in hits[:6]:
            print("     gate.py L%d: %s" % (h[0], h[1][:120]))
    print("  playbook row 3 text:")
    for ln in sec:
        if "not applicable" in ln:
            print("     " + ln.strip())

    print("\n=== E. failure modes documented in THIS section but absent from the playbook ===")
    documented = []
    for idx, ln in enumerate(sec, start=1001):
        if "silently resolved" in ln or "silent default" in ln:
            documented.append((idx, ln.strip()))
    for d in documented:
        print("  documented L%d: %s" % d)
    print("  playbook rows are: %s" % [r.replace("\\\\", "").split("&")[0].strip() for r in rows])
    print("  is there a row for 'missing attachment / resolver picked another problem'? %s"
          % any("attachment" in r or "resolver" in r or "another problem" in r for r in rows))

    print("\n=== F. row 5 ('running out of time') executability ===")
    for ln in sec:
        if "Running out of time" in ln or "smaller claim" in ln:
            print("  " + ln.strip())


if __name__ == "__main__":
    main()
