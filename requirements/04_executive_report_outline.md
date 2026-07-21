# SAMI Analysis — Executive Report Outline

Detailed outline and content description for the executive report. Audience: MMC Executive Director first (reads 2 pages), programme/MEAL/content teams second (read everything). Length: **14–18 pages** main body + annex. Every figure is pulled from the notebooks (same numbers, same colors); the report contains **no figure that doesn't exist in a notebook**.

**Writing rules:** every section heading is a finding, not a topic. Every figure gets an assertion-evidence title, a one-line caption with n + window, and a "so what" sentence in the surrounding prose. No method names in the main body (no "KMeans," no "embeddings" — say "we grouped users by what their conversations are about"; mechanics live in the annex). Verbatim quotes in Spanish with English translation in the caption.

---

## Page 1 — Executive summary *(the only page guaranteed to be read)*

- Three-sentence context: what SAMI is, the data analysed (918 users, 2,993 messages, 25 Mar – 2 Jul 2026, plus 78 survey responses), and what this report is for.
- **5 headline findings** (one bold line + one supporting sentence each — final wording must come from the actual results, these are the targets):
  1. SAMI reaches a settled population, not people in transit — 88% intend to stay in Colombia.
  2. One need dominates: regularising documentation (~52% of everything users ask).
  3. Demand differs by city — border towns and settlement cities need different content.
  4. Reach is growing but resolution lags: a third of users never ask a question, 13% keep re-asking, and tone signals distress in specific needs/places.
  5. The conversations reveal needs the bot isn't built for — including transport/logistics and requests for a human.
- **5 recommendations** (one line each, cross-referenced to §6).
- One small figure permitted: the priority matrix, if it lands cleanly at reduced size; otherwise none.

## Page 2 — How to read this report / data & confidence
- Half page: sources, window, and the three honesty statements (MEAL = 7.5% of users → indicative; self-reported profile fields; 14-week window). A "confidence" legend used throughout: ● robust / ◐ indicative / ○ directional. Every key figure in the report carries one of these marks.
- Half page: canonical numbers table (from doc 01 §7).

---

## Section 1 — Who SAMI reaches *(Act 1, ~3 pages)*

**1.1 "A settled, working-age, Venezuelan audience in five cities"**
- Figures: age distribution (flagged sub-18 band); gender bar; city top-10 + department map.
- Prose: profile in plain language; what the concentration means for coverage (who SAMI is *not* reaching is as important — rural areas, non-Spanish speakers, the departments with zero users on the map).

**1.2 "They are here to stay"**
- Figure: the single-frame migration map (origins → Colombia hub → onward arrows).
- Prose: 88% settlement intent reframes SAMI's job as integration support; onward-movers (US, Argentina, Chile) are a small, distinct segment.

**1.3 Box — "What the data can and can't tell us"**
- The sub-18 protection point raised responsibly: 36 sub-18 self-reports, mostly impossible ages (data noise), but 8 plausible 13–17s on an adults-only service → an intake-validation and safeguarding question for MMC, not a demographic finding.

## Section 2 — What they need *(Act 2, ~3 pages)*

**2.1 "Paperwork first: legal documentation dominates demand"**
- Figures: category mix; institutions vs procedures ranked bars.
- Prose: what "legal documentation" concretely contains (PPT/PEP, cédula de extranjería…); the institutions users must reach = MMC's referral map.

**2.2 "Different cities ask for different things"**
- Figure: category × city composition.
- Prose: the settlement-city vs border-town contrast, with one verbatim quote each; implications for localized content.

**2.3 "Demand over time: growth, spikes and what drives them"**
- Figure: weekly trend by category with annotated spikes.
- Prose: what spiked and when; explicitly state no policy-event correlation is claimed without an event register — and recommend MMC keep one (feeds §6).

## Section 3 — Is SAMI delivering? *(Act 3, ~4 pages)*

**3.1 "The journey from arrival to resolution leaks in the middle"**
- Figure: the funnel (centerpiece).
- Prose: each stage's conversion in plain language; what single-touch users and repeat-askers likely mean; honest alternatives (a zero-question user may have been satisfied by the menu — say so).

**3.2 "Those who answered are mostly positive — but few answered"**
- Figures: usefulness distribution + would-recommend (n and CI visible; ◐ mark).
- Prose: the pulse, its limits, and the survey redesign implication.

**3.3 "The tone of the conversations: a distress signal nobody asked for"**
- Figures: % negative by category; city synthesis map (need + tone).
- Prose: where negative tone concentrates; one carefully chosen quote; validation note in one sentence ("model checked against a human-labeled sample; details in annex").

**3.4 "What users ask that SAMI isn't built to answer"**
- Figures: coverage-gap bar (share of messages outside the official taxonomy, by candidate intent); archetypes summary table (3–5 named profiles: size, needs, quote).
- Prose: each missing intent described in one paragraph with a verbatim example (transport/logistics; human handoff; connectivity). This is the bridge to recommendations.

**3.5 "In their own words"**
- The curated quote panel (6–10 quotes grouped by theme). Half a page, lots of whitespace. Often the most-shared page of the report — treat it as a first-class figure.

## Section 4 — Recommendations *(Act 4, ~2 pages)*

Format per recommendation: **Action (imperative, one line) → Evidence (section refs) → What changes for whom → First step.** Grouped by owner:

- **Programme/coverage:** prioritize by the priority matrix (big + badly served needs; city-specific content); assess unreached geographies.
- **Content/product:** add the named missing intents; define a human-handoff path; localize top-city content.
- **MEAL:** redesign the survey moment/incentive to lift the 7.5% response rate; adopt the funnel + priority matrix as standing KPIs (the dashboard operationalizes both).
- **Data collection:** validate age at intake; one controlled category per conversation at capture; canonical label set; keep an event register to explain demand spikes.
- **Safeguarding:** the sub-18 protocol question.

Close with a 90-day sequence (what to do first) — one small timeline graphic, no Gantt.

## Annex *(not page-limited, but disciplined)*
- A. Method notes in plain-but-precise language: cleaning & canonicalization summary, classification approach + validation (κ, confusion vs `Chat_summary`), clustering method + stability, sentiment validation, bootstrap CIs.
- B. Supplementary figures (anything cut by the figure budgets that reviewers asked for).
- C. Full data dictionary + canonical numbers.
- D. Reproducibility statement (repo, export hash, model versions).

---

## Figure inventory (single source: notebooks)

| # | Figure | Source | Confidence mark |
|---|---|---|---|
| F1 | Priority matrix | NB2 §6 | ◐ |
| F2 | Age distribution (flagged) | NB1 | ● |
| F3 | City top-10 + department map | NB1 | ● |
| F4 | Migration single-frame map | NB1 | ● |
| F5 | Category mix | NB2 | ● |
| F6 | Institutions & procedures | NB2 | ● |
| F7 | Category × city | NB2 | ● (cells n≥20) |
| F8 | Weekly demand trend | NB2 | ● |
| F9 | Funnel | NB2 | ● |
| F10 | Usefulness + recommend | NB2 | ◐ |
| F11 | Negative tone by category | NB3 | ◐ |
| F12 | City need + tone map | NB3 | ◐ |
| F13 | Coverage-gap bar | NB3 | ◐ |
| F14 | Archetypes table | NB3 | ○/◐ per stability |
| F15 | Quote panel | NB3 | ● (verbatim) |

15 figures total in the main body. That is the ceiling.

## Production checklist
- [ ] Every number in prose regenerated from the reconciliation table (no hand-typed stats).
- [ ] Headings read as a coherent story when read alone (test: read only the headings top to bottom).
- [ ] Confidence marks present on F1, F10–F14.
- [ ] Quotes anonymized (no names, phones, or uniquely identifying details).
- [ ] Executive summary reviewed by someone who read nothing else — do the 5 findings stand alone?
- [ ] Same palette/hex as notebooks and dashboard; same category names everywhere.
- [ ] PDF export: links work, figures legible at 100% and printed grayscale.
