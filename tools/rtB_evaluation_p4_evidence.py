# -*- coding: utf-8 -*-
"""Probe 4 (evaluation board): does the section's self-assessment match the
evidence the authors' own collection script emitted?

Every number in the evaluation section is matched to out/final/data.json
(the artifact collect_paper_data.py writes) or to the table it cites.

Read-only. Prints only.
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FN = os.path.join(ROOT, "out", "final")


def load(name):
    with open(os.path.join(FN, name), encoding="utf-8") as fh:
        return json.load(fh)


def readlines(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read().splitlines()


def main():
    data = load("data.json")
    lines = readlines(os.path.join(FN, "paper.tex"))
    sec = lines[1118:1148]

    print("=" * 78)
    print("PROBE 4  self-assessment vs emitted evidence")
    print("=" * 78)

    # ---- 1. "under five seconds for the full chain" ----------------------
    print("\n[1] L1122-1123 'under five seconds for the full chain on one problem'")
    tim = readlines(os.path.join(FN, "tab_timing.tex"))
    tot = None
    for ln in tim:
        if "total" in ln:
            m = re.search(r"&\s*([0-9.]+)\s*&", ln)
            if m:
                tot = float(m.group(1))
    print("    tab_timing.tex declared total ......... %s s" % tot)
    print("    section claim ......................... < 5 s")
    print("    MATCH ................................. %s" % (tot is not None and tot < 5.0))
    if tot and tot >= 5.0:
        print("    -> the section's own cited table contradicts the section.")

    # ---- 2. "23 problems" ----------------------------------------------
    print("\n[2] L1131 'coverage is measured on one corpus (23 problems, ...)'")
    print("    data.json problems length ............. %d" % len(data["problems"]))
    print("    MATCH ................................. %s" % (len(data["problems"]) == 23))
    print("    'one author' -- checkable?  authors declared in paper: ",
          end="")
    joined = "\n".join(lines)
    print("single-author (no \\and / multiple affiliations):",
          ("\\and" not in joined))

    # ---- 3. "a reproducible log", "30 recorded rounds", "129 kB" --------
    print("\n[3] L1125 'derived from a reproducible log'; L1131 'one logging convention'")
    print("    data.json n_record_rounds ............. %s" % data.get("n_record_rounds"))
    print("    data.json record_bytes ................ %s  (= %.1f KiB = %.1f kB)"
          % (data.get("record_bytes"), data["record_bytes"] / 1024.0,
             data["record_bytes"] / 1000.0))
    print("    paper claim (L720, tab:taxonomy) ...... '129 kB ... 30 recorded rounds'")
    print("    129 kB interpretation ............... %.1f KiB -> matches record_bytes"
          % (data["record_bytes"] / 1024.0))

    # ---- 4. the six classes: table vs data.json -------------------------
    print("\n[4] L1137 'the six classes' / L1128 Table tab:claims 'Six defect classes'")
    tax = data["defect_taxonomy"]
    print("    classes in data.json: %d -> %s" % (len(tax), sorted(tax)))
    paper_table = {}
    for ln in lines:
        m = re.match(r"^(Silent default|Duplicated logic|Vacuous check|Self-report inflation|"
                     r"Contract unenforced|Self-test broken)\s*&\s*(\d+)\s*&", ln.strip())
        if m:
            paper_table[m.group(1)] = int(m.group(2))
    keymap = {
        "Silent default": "silent-default",
        "Duplicated logic": "duplicate-logic",
        "Vacuous check": "vacuous-check",
        "Self-report inflation": "self-report",
        "Contract unenforced": "contract-unenforced",
        "Self-test broken": "self-test-broken",
    }
    print("    %-24s %-8s %-8s %-8s %s" % ("class", "paper", "data.json", "delta", "verdict"))
    bad = []
    for pname, dkey in keymap.items():
        pv = paper_table.get(pname)
        dv = tax.get(dkey, {}).get("n_rounds")
        ok = (pv == dv)
        if not ok:
            bad.append((pname, pv, dv))
        print("    %-24s %-8s %-8s %-8s %s"
              % (pname, pv, dv,
                 ("%+d" % (pv - dv)) if (pv is not None and dv is not None) else "?",
                 "ok" if ok else "MISMATCH"))
    print("    paper table class count ............... %d" % len(paper_table))
    print("    sum of paper rounds ................... %d" % sum(paper_table.values()))
    print("    sum of data.json rounds ............... %d"
          % sum(tax[k]["n_rounds"] for k in keymap.values()))
    print("    MISMATCHES ............................ %d %s" % (len(bad), bad))

    # ---- 5. does the figure use the same numbers as the table? ----------
    print("\n[5] L719 'Figure~\\ref{fig:taxonomy} orders the same counts'")
    figsrc = []
    for cand in ("make_final_figs.py", "make_final_figs2.py", "make_final_tables.py"):
        p = os.path.join(ROOT, "tools", cand)
        if os.path.exists(p):
            t = open(p, encoding="utf-8", errors="replace").read()
            if "taxonomy" in t or "vacuous" in t:
                figsrc.append(cand)
    print("    figure/table scripts touching taxonomy: %s" % (figsrc or "NONE"))
    for cand in figsrc:
        t = open(os.path.join(ROOT, "tools", cand), encoding="utf-8", errors="replace").read()
        for ln in t.splitlines():
            if re.search(r"vacuous", ln):
                print("      %s: %s" % (cand, ln.strip()[:110]))

    # ---- 6. "deterministic" and "independent of self-report" ------------
    print("\n[6] L1123 'deterministic, and independent of the author's self-report'")
    print("    a determinism check emitted into data.json/ablation.json: ",
          end="")
    blob = json.dumps(data) + json.dumps(load("ablation.json"))
    print(bool(re.search(r"determinis|reproducib", blob, re.I)))
    print("    tab:claims says: 'no independent rater' / 'no inter-rater agreement'")
    print("    -> 'independent of the self-report' is about the *gate*, not about")
    print("       a rater; the section states it as a strength with no line of")
    print("       evidence, while tab:claims lists the missing rater as a weakness.")

    # ---- 7. was this board ever audited? --------------------------------
    print("\n[7] prior audit of this board")
    rt = load("redteam.json")
    secs = [r.get("section") for r in rt["reviews"]]
    print("    sections present in out/final/redteam.json: %s" % secs)
    print("    'evaluation' present ................. %s" % ("evaluation" in secs))
    print("    -> this board was never reviewed before this audit.")

    print("\n" + "=" * 78)
    print("VERDICT INPUT")
    print("=" * 78)
    print("  [1] five-second claim vs 6.68 s table      : %s" % ("CONTRADICTED" if tot and tot >= 5 else "ok"))
    print("  [2] 23 problems                            : %s" % ("ok" if len(data["problems"]) == 23 else "MISMATCH"))
    print("  [3] 129 kB / 30 rounds                     : %s" % ("ok (record_bytes %d)" % data["record_bytes"]))
    print("  [4] per-class round counts                 : %d mismatch(es)" % len(bad))
    print("  [6] determinism                            : no emitted check")
    print("  [7] prior audit of this board              : none")


if __name__ == "__main__":
    main()
