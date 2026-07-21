# SAMI Analysis — Storytelling & Analysis Scope

**Audience of this document:** analyst implementing the redo.
**Audience of the deliverable:** MMC Executive Director + programme, MEAL and content teams. Data-literate consumers, not data scientists. They need to make decisions about services, coverage, content and priorities — not admire methods.

---

## 1. The core problem with the current version

The current notebooks are not wrong — they are **unprioritized**. Every method that fits the data was applied, so the reader receives ~40 figures with equal visual weight and no hierarchy of importance. The result is paralysis by analysis: the three or four findings that should drive decisions are buried among radial charts, 3D projections and wordcloud grids.

The redo is not "do less analysis." It is: **every analysis must exist to support one named claim in one narrative, and everything else moves to an annex or is deleted.** Rigor stays; ornament goes.

---

## 2. The story in one sentence

> **918 migrants — settled, working-age, overwhelmingly Venezuelan, concentrated in five cities — used SAMI to ask for one thing above all (regularising their documents); the bot reaches them but does not always resolve them, and the conversations tell us exactly which services, content and intents to build next.**

Everything in the deliverable serves this sentence. If a chart doesn't advance it, it doesn't ship.

---

## 3. Narrative arc — four acts

The arc is progressive: each act answers one question, earns the reader's trust, and sets up the next. Each act ends with a "so what" the Executive Director can act on.

### Act 1 — Who is asking? *(the input and the audience)*
- **Question:** What data do we have, can we trust it, and who is SAMI actually reaching?
- **Evidence:** two sources (bot responses log: 947 records / 918 users / 2,993 messages, 25 Mar – 2 Jul 2026; MEAL survey: 78 responses, 7.5% response rate). Completeness profile. Demographic and geographic profile. Migration timeline and intent.
- **Headline insight target:** SAMI's audience is not "migrants in transit." It is a **settled population**: ~96% Venezuelan, median age 33, 88% intend to stay in Colombia, concentrated in Medellín, Bogotá, Barranquilla, Cúcuta and Santa Marta. This single fact reframes what the service should be: **integration support, not route information.**
- **So what:** programme design should assume settlement (documentation, health, employment), and coverage should be read against the five-city concentration.
- **Trust move:** state the limits up front, once, plainly — MEAL is 7.5% of users (indicative, not representative); ages are self-reported (36 sub-18 records flagged as unreliable, kept but never read as a cohort); 14-week window. Saying this early buys credibility for every claim that follows.

### Act 2 — What do they need? *(demand)*
- **Question:** What do users ask for, where, and how does it move over time?
- **Evidence:** the 7-category demand mix (legal documentation ≈52% of messages, humanitarian assistance ≈25%, then employment and health); demand mix by city (border/transit towns vs settlement cities read differently); weekly demand trend; institutions and procedures users name in their own words (dictionary extraction: Migración Colombia, PPT/PEP paperwork, EPS, SISBÉN…).
- **Headline insight target:** demand is **one dominant need plus a long tail** — paperwork regularisation dwarfs everything, but the *mix shifts by geography*, which is the actionable part (what Ipiales needs is not what Medellín needs).
- **So what:** a content and partnership priority list per city; the institutions users must reach are the referral map MMC should maintain.

### Act 3 — Does SAMI deliver? *(experience and gaps)*
- **Question:** Are users getting what they came for — and what is the bot missing?
- **Evidence (converging signals, presented as one argument, not four separate analyses):**
  1. **Engagement depth:** median 3 messages; ~35% of users ask zero questions; 13% are repeat/high-volume askers (proxy for unresolved needs).
  2. **Satisfaction pulse:** MEAL ratings + would-recommend, always with n and the 7.5% caveat attached.
  3. **Tone:** 16% of messages carry negative sentiment — an unsolicited distress signal, concentrated in specific categories/cities.
  4. **Coverage gaps:** clustering + LLM reading of conversations surfaces needs the 7-category taxonomy has no slot for (transport/movement logistics; "let me talk to a human"; unmet local-service requests visible verbatim in MEAL free text).
- **Headline insight target:** the bot reaches people but **resolution is the weak link** — and we can name the specific missing intents.
- **So what:** a concrete list of new intents/content, a human-handoff decision, and a survey redesign (the 7.5% response rate is itself a finding).

### Act 4 — What should MMC do? *(recommendations)*
- Not a new analysis — a synthesis. 5–7 recommendations, each traceable to evidence in Acts 1–3, each with an owner-shaped framing (programme / content / MEAL / data collection). Includes the data-quality recommendations (validate age at intake, controlled category at capture, one canonical label set) and the protection flag (possible minors reaching an adults-only bot — raise it, don't analyse it).

---

## 4. Mapping to the three notebooks

The three-notebook structure survives, with sharper mandates:

| Notebook | Act | Mandate | Budget |
|---|---|---|---|
| **NB1 — The input & the audience** | Act 1 | Descriptive EDA done with authority: source reliability + audience profile. One variable at a time, no cross-cuts. | ≤ 9 figures |
| **NB2 — Demand, behaviour & experience** | Acts 2 + 3 (quantitative) | Relationships, time, demand, engagement, satisfaction. Every cross-cut carries n and a significance/effect-size read where claims are made. | ≤ 12 figures |
| **NB3 — What the text says (NLP/LLM)** | Act 3 (qualitative/semantic) | Emergent needs, tone, and voices. NLP exists to find what the taxonomy misses — not to demonstrate NLP. | ≤ 8 figures |

Figure budgets are hard caps. Anything above the cap goes to an annex section explicitly marked "Annex — supporting evidence" or is cut.

---

## 5. Analytical principles (non-negotiable)

1. **Assertion-evidence titles.** Every figure title states the finding, not the topic. Not "Age distribution of users" but "A working-age audience: half of users are 26–41." The subtitle carries the metric definition and n.
2. **One message per chart.** If a chart needs a paragraph to explain what to look at, redesign it.
3. **Claims scale with evidence.** MEAL-based claims (n=78) are always "indicative." Cross-cuts with any cell n<20 either aggregate up or explicitly display the small-n warning. No causal language anywhere — "is associated with," never "drives."
4. **Reach ≠ satisfaction.** Keep the current notebooks' discipline: growth curves and satisfaction trends never merge into one "success" line.
5. **Uncertainty shown, not hidden.** Bootstrap CIs on the MEAL mean rating; stability checks on clusters; a validation sample for the sentiment model (see doc 02).
6. **Spanish data, English display.** Values stay in Spanish; only chart text is translated. User quotes are shown verbatim in Spanish — they are testimony.
7. **PII is radioactive.** Raw WhatsApp numbers currently appear in notebook outputs. Pseudonymize at load (salted hash), and no raw phone number ever renders in any output, export or dashboard. This is a hard quality gate.

---

## 6. Keep / Cut / Add (vs the current notebooks)

**Keep (it works):**
- The brand palette system and single-cell theming; the English-display convention.
- Canonical city/department mapping and the `*_other` consolidation logic (move to a shared module — see doc 02).
- The data-quality narrative (sub-18 flag, expected missingness, MEAL response-rate framing).
- The single-frame migration map (origin fill + stay-hub + onward arrows) — the best figure in the set.
- The institutions vs procedures split; the reach-vs-satisfaction separation; the repeat-asker analysis.

**Cut or demote to annex:**
- Radial "race track" gender chart → simple horizontal bar. Novel geometry costs cognitive load and adds nothing.
- 3D interactive PCA scatter → cut. The 2D map (one, tinted by cluster with category overlaid or side-by-side) is enough; 15.8% explained variance in 3 components does not justify a 3D toy.
- Month-by-month and per-city wordcloud grids (§9) → replace with one "distinctive terms per slice" table or small-multiple bar of top discriminative terms. Wordclouds at most once (MEAL voices), if at all.
- TF-IDF vs embeddings comparison → annex. One primary representation in the main line.
- Age × destination and similar thin cross-cuts (top-5 destination cells are n≤6) → cut or aggregate.
- Duplicate treemaps (messages by city AND category mix by city) → one view of geography × demand.

**Add (the insight upgrades):**
- **A needs-resolution funnel** as the spine of Act 3: arrived → asked ≥1 question → got answer → didn't repeat-ask → surveyed → satisfied. One figure that unifies engagement, abandonment and satisfaction.
- **A priority matrix** closing Act 3: category × (volume, % negative sentiment, % repeat-askers, satisfaction) → which needs are big AND badly served. This is the figure the Executive Director will screenshot.
- **LLM-assisted classification with validation** replacing "KMeans + eyeball the terms" as the primary gap-finder (KMeans stays as discovery input; see doc 02 §NB3).
- **Data-driven k + stability check** for clustering rather than forcing k=7.
- **Named archetypes** (3–5, e.g. "settling family regularising papers," "new arrival in humanitarian need," "worker seeking formalisation") with size, profile, dominant needs and a verbatim quote each — this is how clusters become communicable to a non-technical audience.

---

## 7. Canonical numbers (single source of truth)

All documents, notebooks, dashboard and report must agree on these definitions:

| Metric | Definition | Value (2 Jul 2026 export) |
|---|---|---|
| Users | unique phone hashes in responses log | 918 |
| Records | rows in responses log after cleaning | 947 |
| Messages | parsed user messages (spine) | 2,993 |
| Users with text | users with ≥1 parsed message | 800 |
| MEAL responses | rows in MEAL export | 78 (69 unique users) |
| MEAL response rate | MEAL users / total users | 7.5% |
| Analysis window | first to last timestamp | 25 Mar – 2 Jul 2026 |
| Dominant demand | % messages = legal documentation | ~52% |
| Negative tone | % messages classified negative | ~16% (pending validation) |
| Repeat-askers | users ≥p90 volume or repeated near-identical question | ~13% |

Any export refresh re-generates this table programmatically (doc 02). Numbers in prose are never typed by hand twice.
