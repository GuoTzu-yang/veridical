# -*- coding: utf-8 -*-
"""rtB deployment board - probe 2: is the time budget the measured seconds?

Read-only. Compares three independent copies of the same measurement:
  A) the Deployment section prose (paper.tex L1001-L1118)
  B) out/final/tab_timing.tex (the paper's own timing table, sec:timing)
  C) out/final/冻结数字.json meta.step_1..9 / meta.timing_total (frozen table)
  D) out/final/data2.json runtimes[] (the raw measurement artifact)
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = os.path.join(ROOT, "out", "final", "paper.tex")
TAB = os.path.join(ROOT, "out", "final", "tab_timing.tex")
FROZEN = os.path.join(ROOT, "out", "final", "冻结数字.json")
DATA2 = os.path.join(ROOT, "out", "final", "data2.json")


def rd(p):
    return io.open(p, encoding="utf-8").read()


def main():
    paper = rd(PAPER).splitlines()
    sec = "\n".join(paper[1000:1118])

    print("=== A. Deployment-section numbers (L1001-L1118) ===")
    # numbers of the form <x.y> s inside the timing paragraph
    para = "\n".join(paper[1034:1040])
    print("  paragraph L1035-1040:")
    for ln in paper[1034:1040]:
        print("    " + ln)
    sec_nums = [float(x) for x in re.findall(r"(\d+\.\d+)\\,s", sec)]
    print("  seconds found in whole section: %s" % sec_nums)
    print("  count=%d sum=%.2f" % (len(sec_nums), sum(sec_nums)))
    # the timing paragraph alone (L1035-L1040) excludes the 2.3 s stamp figure
    para_nums = [float(x) for x in re.findall(r"(\d+\.\d+)\\,s", para)]
    print("  timing-paragraph seconds: %s  count=%d sum=%.2f"
          % (para_nums, len(para_nums), sum(para_nums)))
    sec_nums = para_nums

    print("\n=== B. tab_timing.tex rows ===")
    tab_txt = rd(TAB)
    rows = []
    for ln in tab_txt.splitlines():
        m = re.match(r"^\s*(\d)\s*&\s*(.+?)\s*&\s*(\d+\.\d+)\s*&\s*(\d)\s*\\\\", ln)
        if m:
            rows.append((int(m.group(1)), m.group(2), float(m.group(3)), int(m.group(4))))
    for r in rows:
        print("    step %d  %-34s %5.2f s  exit=%d" % r)
    print("  n_rows=%d sum=%.2f" % (len(rows), sum(r[2] for r in rows)))
    mtot = re.search(r"total, wall clock\}\s*&\s*(\d+\.\d+)", tab_txt)
    print("  stated total in table: %s" % (mtot.group(1) if mtot else None))

    print("\n=== C. frozen table meta.step_* / meta.timing_total ===")
    fz = rd(FROZEN)
    steps = {}
    for m in re.finditer(r'"path":\s*"meta\.step_(\d)"\s*,\s*"value":\s*([0-9.]+)', fz):
        steps[int(m.group(1))] = float(m.group(2))
    tot = re.search(r'"path":\s*"meta\.timing_total"\s*,\s*"value":\s*([0-9.]+)', fz)
    for k in sorted(steps):
        print("    meta.step_%d = %.2f" % (k, steps[k]))
    print("  n_steps=%d sum=%.2f  meta.timing_total=%s"
          % (len(steps), sum(steps.values()), tot.group(1) if tot else None))

    print("\n=== D. data2.json runtimes (raw measurement artifact) ===")
    d2 = rd(DATA2)
    block = re.search(r'"runtimes"\s*:\s*\[(.*?)\]', d2, re.S)
    runs = []
    if block:
        for m in re.finditer(r'"cmd":\s*"([^"]+)"\s*,\s*"seconds":\s*([0-9.]+)', block.group(1)):
            runs.append((m.group(1), float(m.group(2))))
    for c, s in runs:
        print("    %-12s %5.2f" % (c, s))
    print("  n=%d sum=%.2f" % (len(runs), sum(s for _c, s in runs)))

    print("\n=== E. verdict arithmetic ===")
    for label, val in (("deployment section list", sum(sec_nums)),
                       ("tab_timing stated total", float(mtot.group(1)) if mtot else -1),
                       ("frozen meta.timing_total", float(tot.group(1)) if tot else -1),
                       ("data2 raw sum", sum(s for _c, s in runs))):
        print("    %-28s %.2f  -> 'under six seconds'? %s" % (label, val, val < 6.0))
    for claim in ("costs under six seconds", "under five seconds"):
        for i, ln in enumerate(paper, start=1):
            if claim in ln:
                print("    claim %-26r at L%d: %s" % (claim, i, ln.strip()))

    print("\n=== F. per-step trace against the frozen table ===")
    # map: deployment wording -> frozen step index by position in the sentence
    order = [1, 2, 3, 5, 6, 7, 8, 9]  # step 4 (outline) is missing from the prose
    labels = ["detecting the problem type", "structure horse race", "correlation hints",
              "one figure", "tracing", "counterexample search", "eight-channel vote", "gate"]
    for lab, idx, got in zip(labels, order, sec_nums):
        want = steps.get(idx)
        flag = "OK" if want is not None and abs(want - got) < 1e-9 else "MISMATCH"
        print("    %-30s prose=%.2f  frozen.step_%d=%.2f  %s" % (lab, got, idx, want, flag))
    print("    step 4 (frozen %.2f s) mentioned in section? %s"
          % (steps.get(4, -1), any("outline" in ln or "rewrite point" in ln for ln in paper[1000:1118])))
    print("    section still says 'nine commands'? %s"
          % any("nine commands" in ln for ln in paper[1000:1118]))

    print("\n=== G. the 2.3 s stamp claim (mode 3) ===")
    for i, ln in enumerate(paper, start=1):
        if "2.3" in ln:
            print("    L%d: %s" % (i, ln.strip()))
    hits = [m.start() for m in re.finditer(r"2\.3", fz)]
    print("    '2.3' occurrences in frozen table: %d" % len(hits))
    for h in hits:
        seg = fz[max(0, h - 220):h + 30]
        path = re.findall(r'"path":\s*"([^"]+)"', seg)
        print("      nearest path: %s" % (path[-1] if path else "?"))
    print("    any measured stamp/build second in frozen table? %s"
          % bool(re.search(r'"path":\s*"[^"]*stamp[^"]*"[^}]*"value"', fz)))
    print("    gate seconds stated twice in one section: 2.3 (mode table) vs 2.57 (timing para)")


if __name__ == "__main__":
    main()
