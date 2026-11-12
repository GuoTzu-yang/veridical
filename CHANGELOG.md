# Changelog

**What this file is.** The project had no version history before it was imported
into git. This changelog reconstructs the rounds that produced the current state,
from the operating rules in `AGENTS.md` and the round-by-round notes in
`HANDOFF.md`. It is written **after the fact**, from those documents and from the
artefacts each round left behind — not from git history, which starts at the
import commit.

**What it is not.** A substitute for real history. Rounds R121–R124 are dated and
evidenced; anything before R121 is summarised from the rules those rounds left
behind, and is marked as such.

---

## Unreleased

Nothing. The repository is at the state of R124.

---

## R124 — The two doors that were missing, and the figure checker

**Trigger.** An external review of the tool paper said the plug-in arm
"replaced a proof with a checkable equation". That was accurate, and it exposed a
structural gap: of 35 gate checks, none asked whether a key derivation was
stated as a proposition and proved.

**Added**

| File | What |
|---|---|
| `tools/quality_doors.py` | `proof` door (proposition environment + non-empty proof ≥ 60 valid chars) and `iterlog` door (round/symptom/diagnosis/fix table, ≥ 3 rows, with a doubt criterion). Bilingual headers. `selftest` uses two constructed samples. |
| `tools/fig_visual.py` | Figure **content** check. `figcheck` only ever looked at DPI/size/background/aspect/vector — it never opened a figure. This one compares matplotlib `set_title` against the LaTeX `\caption` (≥ 0.75 = near-duplicate, ≥ 0.45 = overlapping) and finds orphaned `\label{fig:*}`. |
| `tools/numeric_genre.py` | Classifies every numeric token by genre. With `--json` it uses the frozen table: value present → `computed`, decimal absent → `config`. |
| `tools/handoff.py` | Refreshes the `<!-- AUTO -->` block in `HANDOFF.md` by running the real instruments. |
| `HANDOFF.md` | One-page handover: current state, next steps, five traps. |
| `out/数字类别分布.md` | 23 papers, 9,337 numeric tokens: **computed 47.3%**, config 27.1%, structural 17.6%, time 8.0%. |
| `out/Q2大纲.md` … `out/Q2大纲-v5路B骨架.md` | Five outline revisions for a Q2 submission. |

**Changed**

- `gate.py` grew from 33 to **35** checks; `tab_checks.tex` grew to 35 rows.
- `paper.tex` gained a proposition with a 459-character proof (rounding
  equivalence) and a six-round iteration table.
- `tools/paper_pipeline.py` now runs `make_ab_figs.py` after `make_final_figs`.
  Without this, every pipeline run made fig21–24 stale and `arch_invariants.I12`
  reported "figures older than their data" on every run.

**Fixed (each of these was found by a check, not by reading code)**

| Symptom | Cause | Fix |
|---|---|---|
| `proposition`/`proof` undefined | no `amsthm` | added `\usepackage{amsthm}` + `\newtheorem` |
| 4 LaTeX errors | `[H]` float specifier | added `\usepackage{float}` |
| 34 → 31 → 30 pages | over the 30-page ceiling | margins 2.4→1.6 cm, figures narrowed twice |
| `rules` I008 red | 13 `\section` (threshold is 12) | A/B section demoted to subsection |
| `self_correction` red | the new iteration table was never `\ref`'d in its own section | added the reference and the sentence distinguishing process from autopsy |
| `arch_invariants.I12` red, twice | figures repainted but data not re-collected | `make_ab_figs` moved into the pipeline |
| `verify` 198/199 | `1448` (the CRLF byte delta) unregistered | registered as `derived.iterlog_crlf_bytes` |
| `fig_visual` reported sim 0.00 for all 24 | it matched scripts to figures by script file name | map `savefig` output paths instead |
| `fig_visual` then produced 4 false positives | every title compared against every caption | restrict to the owning script's titles |
| `numeric_genre` scanned 22 papers, not 23 | it walked `out/runs/*`, which has 22 directories while `runs.json` has 23 entries | drive the walk from `runs.json` |

**Measured, not claimed**

```
fence_acceptance   拦住 11 / 漏检 0 / 误报 0 / 放行 1   (12/12 = 100%, Wilson 95% CI 75.7–100%)
fence_mutation     假测试 0 / 4
verify             199/199 (all tokens); gate numbers 43/43 (decimals only)
run_all            ALL PASS
gate               35 checks: hard 10 OK / 0 FAIL; soft 17 OK / 2 FAIL / 1 WARN / 5 N/A
```

**Honest deficit recorded this round.** Of the 35 checks, only **4** have a
constructed defect plus mutation coverage (`numbers`, `figures`, `redteam`,
`stamp`). The other 31 are criteria implementations with no independent sample.
This is written into `out/Q2大纲-v4判决.md` and is not glossed over.

---

## R123 — The title must land on disk, the gates must have thresholds

**Trigger.** Two user instructions: "constrain the LLM to actually read the
problem, no guessing, no skipping", and "everything we check by hand should
become a rule".

**Added**

| File | What |
|---|---|
| `gate.chk_prompt` (33rd check) | (A) `题目.md` on disk and ≥ 200 chars; (B) ≥ 40 chars verbatim overlap between the restatement and the problem statement; (C) every numbered sub-question answered |
| `gate.chk_significance` | an interval or error term, and it must not be the variable's own domain |
| `gate.chk_figures` floor | ≥ 6 figures, not just a quality score |
| `gate.chk_refs` floor | ≥ 10 bibliography entries, each cited |
| `tools/paper_pipeline.py` | the ten-step fixed chain, so nobody has to remember the order |
| `tools/paper_hygiene.py` | CRLF count, self-referential quantities, missing `declaration.json` |
| `tools/bootstrap_ci.py` | 23-problem bootstrap, seed 20261112, 10,000 resamples |
| `tools/prompt_fidelity.py` | `--seed` writes the problem *title* only (9–52 chars, not the statement) |
| `tools/grade.py` | the 23-criterion rubric, `--selftest` with a bad and a good sample |
| `tools/redteam_orchestrate.py` | `auto` / `prompts` / `collect`; prints board count and batch plan |

**Fixed**

- `redteam.py` read `out/final` regardless of the path argument. Same bug in
  `triage_findings.py`.
- Role column width hard-coded at 26, so long names overflowed and read as
  `memo-to-the-producersmemo-to-the-producers`.
- `redteam.py` required a review-level `resolved` even when findings carried a
  `disposition`. Cleared both in `selftest` — 28/28.
- `chk_significance` did not accept `\%` inside intervals.
- `grade.py` A5 false positives on negation ("We do not assume unlimited
  bandwidth", "从物理上杜绝了无限带宽的伪假设") — sentence-level negation test.
- `grade.py` A2 did not match `大 $M$ 法` — fixed to `大\s*\$?\s*[Mm]`.
- `grade.py` `_tex()` only looked for `paper.tex`; the control arm uses `main.tex`.
- Three fabricated examples in the heat-sink paragraph (`2019`, `12`, `0.05`)
  replaced with verbatim-verified values.

**Rules added to `AGENTS.md`**: the problem statement must be on disk; look up the
method before implementing it (mutation testing, multiversion programming,
metamorphic testing); examples must be verified word by word; per-deliverable
floors.

---

## R122 — Seven roles hid five unreviewed sections

**Trigger.** `redteam.py`'s `SPEC` listed 7 boards while `paper.tex` had 12
sections. Five sections had never had a reviewer, and `gate` still reported
"seven boards, seven roles, 13 findings, all closed".

**Changed**

- The board count is now parsed from `\section`, never hard-coded.
- `redteam.py selftest` pins the ratio with minimal papers of 4, 12, 20 and 21
  sections.
- Roles are one per board and may not repeat.

**Why this is in the changelog at all.** It is the clearest instance of the
failure mode this project is about: a summary that looked green because the
metric and the object disagreed.

---

## R121 — Boards, not a fixed number

`redteam.py` gained `roster` (reads `argv[2]`), adaptive column widths, slug
de-collision, and stopped requiring `resolved` when a disposition is present.

---

## Before R121 (summarised, not dated)

The corpus, the kernel, and the first two devices: `mmkit.py` (23 subcommands),
`mm.py`/`engine.py`, `verify.py`/`falsify.py`/`lanes.py`, `gate.py`, and the
23-problem `runs.json`. The rules in `AGENTS.md` from this period are retained
verbatim in that file; they are not reconstructed here because there is no
artefact that dates them.

---

## How to read the numbers in this file

Every measured figure above was produced by a command in this repository and can
be re-run:

```powershell
$py = "<python>"
& $py tests\run_all.py
& $py gate.py out/final
& $py tools\fence_acceptance.py
& $py tools\fence_mutation.py
& $py tools\numeric_genre.py --json
& $py tools\handoff.py --dry
```

Where a number is an estimate or a recollection rather than a measurement, it is
marked. Rounds before R121 are the only such case.
