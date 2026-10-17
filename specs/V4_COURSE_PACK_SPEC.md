# V4_COURSE_PACK_SPEC — Phase 36: course submission pack (drafts)

Lane X · branch `lane-x/m36-course` (from `origin/main`; start after 34A is pushed, it does not need 34A merged) ·
acceptance `tests/test_p36_course_pack.py` · contract `claims_policy.json` · Lead reviews every file before anything
leaves the repository. The pack is for a 3-credit course; the student (the user) submits it, not an agent.

## 1. Goal
Drafts of everything the course needs, written from the repository's frozen results only, honest about what failed,
and safe to submit before the patent filing: report, poster layout, 3-minute video script + shot list, 30-question viva
bank, user guide, contribution-log template, references, and a numbers ledger that traces every result to a file.

## 2. Disclosure rule (P0 is not filed; the user has not yet decided whether to file the gate at all)
`docs/course/DISCLOSURE.md` line 1 is `Disclosure level: RESTRICTED` — the only level an agent may write. At RESTRICTED:
- The gate is described **only** with this approved-for-drafting paragraph (verbatim or shorter, nothing added):
  "Before any dispatch is executed, Sentinel checks it against many sampled hazard futures and allows it only when a
  statistical lower bound on its success clears a fixed threshold; otherwise it holds and escalates to a human
  (fail-closed). Every decision gets a hash-chained certificate that anyone can replay bit-for-bit."
- None of `claims_policy.json` → `restricted_terms_until_disclosure` appears (word match, case-insensitive) in any file
  except `DISCLOSURE.md` and `NUMBERS.md`. Phase 27 is reported only as: pre-registered; the safety bar (Bar 4) passed;
  the outcome bar (Bar 1) failed with R = 21.4 %; a decision-level comparison passed (details withheld until filing);
  the variance bar (Bar 3) failed.
- `DISCLOSURE.md` also lists what is withheld and states: "Nothing in this folder is submitted, posted or shown outside
  the project until the user approves the text. The level changes to FULL only when the user records it in STATUS.md
  (after P0 is filed, or if the user decides not to file and releases the mechanism)."
At FULL (only after the STATUS decision log contains `Disclosure level FULL approved by the user`), Lead re-plans the
mechanism sections; no agent switches the level.

## 3. Honesty rules (all files)
- **D-27:** no outcome-effect claim (no banned pattern of `claims_policy.json`). `REPORT.md` says in words
  "no outcome-effect claim" and explains why (Bar 1: the gate dispatched far fewer groups; R = 21.4 % < 95 %). Any file
  that quotes a Phase 27 failure rate also quotes R.
- Claim support: **14D is the evaluation of record** (`T2_VERIFIER_USEFUL`, user-approved for T2); **14C failed**
  (macro-F1 and span-integrity conditions) and is reported as failed with its reasons; **14B superseded** (never scored).
  Any file that names 14C also says "failed"; any file that names 14B says "superseded".
- Rule tiers: NDMA-R01 and NDMA-R02 are **T1** (the 14D verifier answered PARTIALLY_SUPPORTED; T2 needs SUPPORTED);
  no rule is T2. A line naming a rule and T2 must also name T1.
- Simulated hazards on real Fort Kochi roads; not operationally validated (the honesty banner wording).
- V3 results (Phase 10 planners, PPO, Phase 13 retrieval) and limitations are reported as already recorded in
  `V3_POLICY_EVALUATION.md`, `V3_RETRIEVAL_EVALUATION.md` and `V3_TRAINING_RESULT.md` — summarise, never re-derive.
- No invented number: every decimal or percentage in the outward-facing files appears in `NUMBERS.md` (§5).

## 4. Files (`docs/course/`, Lane X)
| File | Content |
|---|---|
| `README.md` | index of the pack; how the user exports the poster PDF and records the video; the disclosure line |
| `DISCLOSURE.md` | §2 |
| `REPORT.md` | headings exactly `## Problem`, `## Literature`, `## Method`, `## Experiments`, `## Results`, `## Limitations`, `## Ethics and safety`, `## Future work` (no numbering in headings); ~4,000–6,000 words; citations `[n]` into `REFERENCES.md` |
| `POSTER.md` | A1 portrait (594 × 841 mm): panel grid with sizes in mm, title block, per-panel text (≤ 120 words each) and which console screenshot or chart goes where; the user exports the PDF |
| `VIDEO_SHOT_LIST.md` | 3-minute script: table `| Time | Shot | Screen | Voice-over |`, times `m:ss–m:ss` contiguous from `0:00`, ending ≤ `3:00`; the core shot screen-records **Run demo** (recorded run of the real engine) |
| `VIVA_QA.md` | exactly 30 entries `### Q<n>. <question> [topic: <topic>]` each followed by a paragraph starting `**Answer:**`; topics must include every one of: `problem`, `data`, `road-graph`, `hazard-model`, `planners`, `reinforcement-learning`, `retrieval`, `claim-support`, `rule-tiers`, `gate`, `evaluation`, `limitations`, `ethics`, `reproducibility`, `hardware`, `future-work` |
| `USER_GUIDE.md` | start the console (`scripts/dev.ps1`, mock mode), the five pages (Overview, Live Operations, Decisions & Certificates, Evidence & Results, System & Hardware) and what each shows |
| `CONTRIBUTION_LOG.md` | a template the student completes (line `To be completed by the student.`), table per milestone, and a section `## Use of AI assistance` left for the student to fill — agents never write the student's personal claims |
| `REFERENCES.md` | numbered references `[n]`; NDMA guidelines, OSM, libraries and methods actually used |
| `NUMBERS.md` | §5 |

## 5. Numbers ledger (`NUMBERS.md`)
One table `| Written | File | JSON pointer | Format |`. Each row: `Written` exactly as it appears in the text; `File` under
`data/eval_results/`, `data/eval_v3/`, `data/constraints_v4/` or `data/demo_v4/`; the pointer resolves; formatting the
value with `Format` gives `Written` — formats `percent1` (`30.1 %`), `percent2`, `fixed3`, `fixed2`, `integer`, `ms0`
(`1059 ms`), `text`. A row with `File` `-` and Format `literal` is allowed only for non-results (thresholds, counts of
pages, versions) and needs a reason in the `JSON pointer` column; Lead reviews each one. Every token matching
`\d+\.\d+` or `\d+(\.\d+)? %` in `REPORT.md`, `POSTER.md`, `VIDEO_SHOT_LIST.md`, `VIVA_QA.md` and `USER_GUIDE.md`
(heading lines excluded) must equal some `Written`.

## 6. Acceptance (`tests/test_p36_course_pack.py`, milestone `P36`) and review
Files and headings per §4; 30 viva entries with every required topic; video ≤ 3:00; poster A1 dimensions; contribution
template lines; disclosure level RESTRICTED with no restricted term (or FULL only with the STATUS record); no banned
outcome pattern; "no outcome-effect claim" in the report; R beside any Phase 27 failure rate; 14C/14B/14D/T2 wording;
every `NUMBERS.md` row resolves and every number in the text is in the ledger. Lead review checklist (WC review):
accuracy against the result files, tone, and that nothing reveals more than §2 allows.
Out of scope: the PDF export, recording the video, submitting anything, any code change. Lane X has no Runner: run the
test after each file.

## Amendments
- 2026-10-17 (Lead): the patent is ON HOLD (user; P0 optional). This changes nothing in §2: the pack stays at RESTRICTED until the user records `Disclosure level FULL approved by the user` in STATUS.md.
