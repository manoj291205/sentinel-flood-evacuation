# Submission checklist (for the user)

Venue: **Deployable AI Workshop at AAAI-27** (details and alternatives in [VENUE.md](VENUE.md)).
Deadline: **20 Nov 2026, 23:59 AoE = 21 Nov 2026, 17:29 IST**. Plan to submit by **Thu 19 Nov 2026 IST** to leave
a day for portal problems.

## 0. Gate: nothing below happens until this is true
- [ ] You have **lifted the confidentiality rules in chat** (P0 filed, or the patent abandoned for good) and that is
      recorded in `docs/patent-roadmap/STATUS.md`. The paper discloses the full gate mechanism (keyed futures, joint
      arrival-time indicator, fail-closed certifier, certificates, migration). An OpenReview submission can become
      **publicly visible** (workshops often open accepted, and sometimes all, papers), so treat submitting as public
      disclosure. If P0 is not filed by about 13 Nov 2026, skip this deadline and use ISCRAM 2027 (31 Dec 2026).
- [ ] If the patent is still alive: the provisional is filed **before** the submission date (disclosure first would
      cost novelty outside any grace period).

## 1. Account
- [ ] OpenReview profile for every author. **New profiles without an institutional email can take up to two weeks to
      be moderated**, so create them by **6 Nov 2026**.
- [ ] Profiles list current affiliation, past affiliations and a DBLP link where one exists (used for conflicts).

## 2. Author list and order
- [ ] Decide the authors and their order (typically: the student who built and evaluated the system first,
      supervisor last). Everyone listed must have contributed and must approve the final text.
- [ ] Everyone listed agrees to the submission and to presenting if accepted (check whether the workshop requires
      in-person presentation in Montréal, 22–23 Feb 2027; visa lead times for Canada can be long).
- [ ] The submission PDF stays anonymous ("Anonymous Submission"); names go only into the OpenReview form.

## 3. Conflicts of interest
- [ ] Enter conflicts in OpenReview: same institution, advisors/advisees, co-authors in the last few years,
      close collaborators, family. Check the workshop organisers and programme committee for any of these.

## 4. Copyright and licence
- [ ] The workshop is **non-archival** (no proceedings), so no AAAI copyright transfer is expected at submission.
      Confirm with the organisers whether any licence or consent-to-publish form is needed for the camera-ready
      (20 Dec 2026) or for posting on the workshop site.
- [ ] Road data are OpenStreetMap (ODbL): keep the attribution in the paper.
- [ ] Check the university's rules on publishing work done for a course (and whether the course report, submitted
      28 Oct 2026, must be cited or declared).

## 5. No dual submission
- [ ] The same paper is **not** under review anywhere else while it is under review here (project rule, stricter than
      this workshop's own policy).
- [ ] ISCRAM 2027 (CoRe, 31 Dec 2026) only after this workshop's decision (2 Dec 2026), and only if ISCRAM accepts work
      already presented at a non-archival workshop; check its policy then.
- [ ] The course report is not a publication, but say so if the organisers ask.

## 6. Before uploading the PDF
- [ ] Download the AAAI-27 author kit (https://aaai.org/authorkit27/); copy `aaai2027.sty` and `aaai2027.bst` next to
      `docs/paper/paper.tex`; check the `\usepackage[submission]{aaai2027}` option and `\pdfinfo` template version
      against the kit's anonymous-submission example.
- [ ] From the repository root: `python scripts/paper_figures.py --check` (must print `OK`), then in `docs/paper/`:
      `pdflatex paper`, `bibtex paper`, `pdflatex paper`, `pdflatex paper` (needs TeX Live or MiKTeX with
      `pgfplots`; **the draft has not been compiled yet** because no LaTeX is installed on this laptop).
- [ ] Main text ≤ **7 pages** (references and appendix do not count). If over: move the Supporting checks paragraph
      and Figure 2 to the appendix first.
- [ ] Every entry marked `VERIFY` in `docs/paper/refs.bib` checked against the actual paper or patent (authors, title,
      venue, pages); remove anything you cannot verify.
- [ ] Anonymity: no names, affiliations, acknowledgements, repository URLs, project name or identifying file paths in
      the PDF, its metadata (File → Properties) or any supplementary material.
- [ ] Results unchanged: every number comes from `docs/paper/generated/numbers.tex`
      (trace: `generated/NUMBERS_TRACE.md`). The D-27 statements stay as written (Bars 2 and 4 pass, Bars 1 and 3
      fail, no outcome-effect claim).
- [ ] Check the AAAI-27 / workshop policy on generative-AI use and disclose as it requires: the draft was written with
      an AI assistant, and the claim-support challenge pairs were written with LLM assistance (already stated in
      Limitations).
- [ ] Decide what code or data to release (none is promised in the draft) and whether a supplement is needed.
- [ ] PDF under 50 MB, fonts embedded.

## 7. Deadline in your time zone (IST, UTC+05:30)
| Event | AoE (UTC−12) | IST |
|---|---|---|
| Paper deadline | 20 Nov 2026 23:59 | **21 Nov 2026 17:29** |
| Notification | 2 Dec 2026 | 2–3 Dec 2026 |
| Camera-ready | 20 Dec 2026 23:59 (if AoE) | 21 Dec 2026 17:29 |
| Workshop | 22–23 Feb 2027, Montréal | — |
Re-check all dates on https://dai-workshop.github.io/ on the day you submit.
