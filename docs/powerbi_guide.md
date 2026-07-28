# Building `mmc_dashboard.pbix` — a click-by-click manual

**Who this is for.** Someone who has never opened Power BI. No step says "just add a card" —
every step says which icon to click, what you should see happen, and how to check it worked
before moving on.

**What this builds.** The dashboard specified in
[`requirements/03_dashboard_requirements.md`](../requirements/03_dashboard_requirements.md):
3 tabs, 12 visuals, 4 KPI numbers per tab, a hidden "About the data" page, and a refresh
button that updates everything with no rebuilding.

**What this does *not* do.** Nothing here cleans, classifies or calculates data. All of that
already happened in Python (`run_pipeline.py` → the `exports/` folder). Power BI only loads
those CSV files, links them together, adds them up, and draws them. If a number needs new
logic, it goes in the pipeline, not here.

**Column-by-column data reference:** [`exports/_schema.md`](../exports/_schema.md).

> ### The one rule you must not break
> The sentiment ("tone") model only weakly agreed with human labels — kappa = 0.604, below the
> 0.7 bar we set for publishable numbers. So anything tone-derived may be used to **put things
> in order** (this category is the most negative), but its **number must never appear on
> screen**. Steps affected are marked ⚠️. The data file `meta_run.csv` carries
> `tone_gate_passed = false` as a permanent reminder.

**Before you build anything, read [Appendix A](#appendix-a--five-things-doc-03-asks-for-that-cannot-be-built-literally).**
Five items in doc 03 cannot be built exactly as written against the data we actually ship.
Appendix A says what to build instead and why. The `% Negative Tone` KPI is the big one — it
is forbidden by the rule above.

> ### Four more rules — the v2 questionnaire migration
> The chatbot platform was replaced in July 2026 and the registration survey was rewritten.
> Every export now carries **two cohorts** in the same tables, distinguished by
> `dim_user[instrument_version]` (`v1` / `v2`). Four things break silently if you don't know
> this:
>
> 1. **`fact_meal[no_usefulness_reason]` must always be filtered on `fact_meal[reason_is_valid]`
>    = true.** The v2 survey's skip logic misfired and showed the "why wasn't it useful"
>    question to satisfied respondents too, so the raw column is mostly noise — only **31** of
>    the answers are analytically usable at `fact_meal`'s user grain.
> 2. **Any nationality visual must be sliced by `instrument_version`.** The v1 survey ended the
>    conversation for respondents who said they were Colombian, so v1 and v2 measure
>    different populations — pooling them reads as a change in who arrived, when it's really a
>    change in who was allowed to finish the survey.
> 3. **`agg_registration_funnel` is split by cohort and must never be summed across cohorts.**
>    v1's rows are 100% complete by construction — the legacy platform never tracked partial
>    attempts — so a pooled completion rate is meaningless. Read the two rows separately: v1 is
>    99.9%, v2 is 89.2%.
> 4. **`agg_language` counts users who *ever* used a language**, not a language a user is
>    assigned to. A multilingual user appears in more than one row, so the `n_users` column
>    deliberately does not sum to the total user count — don't build a percentage of total from
>    it without checking for double-counting first.

> ### The house style — settled at the 2026-07-27 design review
>
> Francisco reviewed the draft dashboard visual by visual. These apply to **every tab**; build
> them once and copy-paste the formatting rather than re-deciding per visual. Nothing here is
> a matter of taste any more.
>
> | | Rule |
> |---|---|
> | **Filters** | Every multi-select filter is a **dropdown**, never a loose list. Date filters are **calendar pickers only** — delete the slider (delete, don't hide). Filter *titles* are grey and a size smaller than the chart titles; the text inside a dropdown must not be larger than the title above it. |
> | **Filter rail** | Give the rail its own light-green background so it reads as a different surface from the canvas. Roughly **1/7 of the page width** — narrower looks starved. Shared filters appear in the same order on every tab. |
> | **KPI cards** | Each card sits in a box with a **discreet border and a soft shadow**. On a white canvas an unboxed card looks like it is floating. |
> | **Spacing** | More margin between plots, and more space between a chart's title and its plot area. Four large visuals per page have room to breathe — use it. |
> | **Chart chrome** | **Delete sub-titles and footnotes inside charts** (`n = 154 active users` and friends). That is what tooltips are for, and the space is worth more. Drop the colour legend wherever the axis already names the categories. |
> | **Titles** | Plain and descriptive. No poetry — "Where SAMI reaches and where it doesn't" became "Users by city". Also stop naming charts after the requirement document; name them after what the reader sees. |
> | **Bars** | **Vertical**, not horizontal, wherever a horizontal bar chart would sit directly under another one — two stacked horizontal charts read as the same chart twice. |
> | **Tables** | No grey row banding. Bold or enlarge the header row instead, and colour the **values** conditionally — that is the instant-read format for a dense table. |
> | **Interactivity** | Every visual **and every KPI card** responds to the slicers *and* to clicks on other charts. The KPI cards were deliberately frozen in an earlier draft of this guide — **that is reversed**, see Part 7.2. |
>
> **Deliberately dropped, do not reopen:** Colombian department shapefiles (Part 7.3), word
> clouds (deferred to a later page), and anything tone-derived with a number attached.

> ### `unclassified` now displays as **"Suggestion"**
>
> The platform's own message categorisation is presented as a *suggestion*, not ground truth.
> From the July 2026 platform change the summary field became free prose carrying no category
> label at all, so that bucket now holds two populations: users who registered and never
> chatted, and everyone whose summary carries no label. It is **21.8% of users** and it will
> grow — that is expected, not a data quality failure.
>
> The **key** is still `unclassified`, so every relationship, filter and measure you already
> wrote keeps working; only `dim_category[category_en]` changed. It keeps its grey `#b7b7b7`.
> Do not filter it out of category charts without saying so in the subtitle — it is the second
> largest bucket, and hiding it would silently inflate every other category's share.

---

## Contents

| Part | What you do | Time |
|---|---|---|
| [0](#part-0--power-bi-in-ten-minutes-read-this-first) | **Learn the screen and the 8 gestures** — read this first | 10 min |
| [1](#part-1--what-you-need-installed) | Install Power BI Desktop | 15 min |
| [2](#part-2--apply-the-theme) | Load the colour theme | 5 min |
| [3](#part-3--load-the-data-power-query) | `DataFolder` parameter, 19 tables, calendar | 40 min |
| [4](#part-4--the-model-relationships-sorting-hiding) | Relationships, sort orders, hiding fields | 25 min |
| [5](#part-5--the-measures) | Write all the calculations | 40 min |
| [6](#part-6--set-up-the-canvas-and-the-slicer-rail) | Page size, grid, filters down the left side | 25 min |
| [7](#part-7--tab-1--who-is-sami-reaching) | Tab 1 — 4 KPIs + 4 visuals | 60 min |
| [8](#part-8--tab-2--what-do-they-need) | Tab 2 — 4 KPIs + 4 visuals | 60 min |
| [9](#part-9--tab-3--is-it-working) | Tab 3 — 4 KPIs + 4 visuals | 75 min |
| [10](#part-10--the-hidden-about-page) | About page + ⓘ buttons | 30 min |
| [11](#part-11--interactions-dynamic-titles-accessibility) | Interactions, dynamic subtitles, alt text | 40 min |
| [12](#part-12--save-refresh-runbook-acceptance-tests) | Save, refresh runbook, acceptance tests, **is the data anonymised?** | 30 min |
| [A](#appendix-a--five-things-doc-03-asks-for-that-cannot-be-built-literally) | Deviations from doc 03 | — |
| [B](#appendix-b--charts-that-did-not-make-the-twelve) | Charts deliberately left out | — |

> ### 📍 If you already followed the earlier version of this guide
> You said you got as far as **loading the data and making the relationships**. That means
> Parts 1, 2, 3 and 4.1 are done. Do this:
>
> 1. Read **[Part 0](#part-0--power-bi-in-ten-minutes-read-this-first)** anyway — it is the
>    vocabulary everything below uses. Ten minutes, and the rest of the guide stops being
>    cryptic.
> 2. Run the **[checkpoint at the end of Part 4.1](#-checkpoint-is-your-existing-work-correct)**
>    to confirm what you built is right.
> 3. Then continue from **[Part 4.2](#42-tell-power-bi-which-table-is-the-calendar)**.

---

## Part 0 — Power BI in ten minutes (read this first)

Everything below this point is written in the vocabulary of this section. If a later step
says "open the Format pane and search for *Callout value*", this is where you learn what that
means.

### 0.1 The four regions of the screen

Open Power BI Desktop and you are looking at four things:

```
┌────────────────────────────────────────────────────────────────────────┐
│  File   Home   Insert   Modeling   View   Optimize   Help   ← RIBBON   │
├──┬──────────────────────────────────────────┬──────────┬───────────────┤
│  │                                          │ Filters  │  Data         │
│V │                                          ├──────────┤  ┌──────────┐ │
│I │                                          │ Visuali- │  │dim_user  │ │
│E │            THE CANVAS                    │ zations  │  │fact_msg  │ │
│W │       (your report page)                 │          │  │dim_city  │ │
│S │                                          │ ▣ ▤ ▥ ▦  │  │ ...      │ │
│  │                                          │ ▧ ▨ ▩ …  │  └──────────┘ │
│  │                                          │          │               │
├──┴──────────────────────────────────────────┴──────────┴───────────────┤
│  Page 1  |  +                                        ← PAGE TABS       │
└────────────────────────────────────────────────────────────────────────┘
```

**1. The ribbon (top).** Tabs of buttons: *File, Home, Insert, Modeling, View, Help*. When
this guide writes **Home → Transform data**, it means: click the word *Home* in the ribbon,
then click the button labelled *Transform data*.

**2. The view switcher (far left, three icons stacked vertically).** These switch what the
middle of the screen shows:

| Icon | Name | What it's for |
|---|---|---|
| 📊 chart bars (top) | **Report view** | Drawing the dashboard. You'll be here most of the time. |
| ▦ grid (middle) | **Table view** | Looking at raw rows, like a spreadsheet. Rarely needed. |
| ⧉ joined boxes (bottom) | **Model view** | Drawing lines between tables. Used once, in Part 4. |

**3. The panes (right side).** Three stacked panels:

- **Data pane** (rightmost) — the list of your tables. Click the ▸ arrow next to a table name
  to expand it and see its columns. This guide calls a column-inside-a-table a **field**, and
  writes it as `table[column]` — so `dim_user[city_canon]` means "expand `dim_user`, find the
  column `city_canon`".
- **Visualizations pane** (middle) — the grid of little chart icons, plus everything about
  the currently selected chart. It has **three sub-tabs**, shown as icons at its top:
  - **Build** (a bar-chart icon) — where you drag fields in.
  - **Format** (a **paint roller** icon) — every appearance setting. Hundreds of them.
  - **Analytics** (a **magnifying glass**) — reference lines. Used once, in Part 9.3.
- **Filters pane** (leftmost of the three) — filters that apply to one visual, one page, or
  everything.

If a pane is missing: **View ribbon → tick its checkbox**. If a pane is collapsed to a thin
strip, click the `»` arrow to expand it.

**4. Page tabs (bottom).** One tab per page of the report, like Excel sheet tabs. You'll end
up with four: three visible tabs plus one hidden About page.

### 0.2 Words this guide uses

| Word | What it means |
|---|---|
| **Visual** | Any chart, map, table, card or slicer on the canvas. A box you can select, move and resize. |
| **Field** | One column of one table, e.g. `dim_user[age_range]`. |
| **Field well** | A labelled drop-box in the Build pane — *X-axis*, *Y-axis*, *Legend*, *Values*. You drag fields into these. |
| **Measure** | A calculation you write once and reuse, e.g. `Users = COUNTROWS(dim_user)`. It recomputes for whatever is on screen. Shown in the Data pane with a **calculator icon** (Σ-ish), never a plain column icon. |
| **Card** | The visual type that shows one big number. Its icon in the Visualizations pane looks like **123**. |
| **Slicer** | The visual type readers click to filter — a list of cities, a date range. Icon looks like a **funnel over a list**. |
| **DAX** | The formula language for measures. Looks like Excel formulas with more brackets. |
| **Power Query / M** | The separate window and language used only for *loading* data. Part 3 only. |
| **Cross-highlighting** | Default Power BI behaviour: clicking a bar in one chart dims the unrelated parts of every other chart. |

### 0.3 The eight gestures you will repeat all day

Learn these once. Every later step is a combination of them.

---

**① Add a visual to the page**

1. Click an **empty part of the canvas** (so nothing else is selected).
2. In the **Visualizations pane**, click the icon for the chart type you want.
3. An empty grey placeholder box appears on the canvas.

> **If instead your existing chart changed type** — you had a chart selected when you clicked.
> Press **Ctrl+Z**, click empty canvas, try again. This is the single most common beginner
> mistake.

---

**② Put a field into a visual**

1. Select the visual (single click on it).
2. Make sure the **Visualizations pane is on the Build sub-tab** (bar-chart icon at its top).
   You'll see labelled empty boxes: *X-axis*, *Y-axis*, *Legend*, etc.
3. From the **Data pane**, drag the field name and **drop it onto the labelled box**.

Dragging is fussy. The reliable alternative: click the visual, then in the Data pane just
**tick the checkbox** next to the field — Power BI puts it in the most likely well, and you
can drag it between wells afterwards.

---

**③ Change how a field is summarised**

By default Power BI sums numbers. Often you don't want that (latitude, for example, must
never be summed).

1. In the **Build** pane, find the field sitting in its well.
2. Hover it — a small **▾ arrow** appears on its right. Click it.
3. Choose from the menu: *Don't summarize*, *Sum*, *Average*, *Count*, …

---

**④ Format a visual (the paint roller)**

1. Select the visual.
2. Click the **paint roller icon** at the top of the Visualizations pane.
3. You now see two sub-tabs: **Visual** (settings specific to this chart type) and **General**
   (title, background, border, size & position — same for every visual).
4. **Use the search box at the top of the Format pane.** There are hundreds of settings in
   collapsed accordions; scrolling for them is misery. When this guide says
   *Format → **Data labels** → On*, the fastest route is: paint roller → type `data labels`
   in the search box → flip the toggle that appears.

This guide always writes formatting as **Format → *Setting name* → value**. Search for the
setting name.

---

**⑤ Position and size a visual exactly**

Dragging with the mouse will never give you an aligned dashboard. Every visual in this guide
comes with exact numbers. To apply them:

1. Select the visual.
2. **Format → General → Properties → Size and position.**
3. Type the four numbers: **Horizontal (X)**, **Vertical (Y)**, **Width**, **Height** — all in
   pixels, measured from the top-left corner of the canvas.

Do this for every object. It takes 15 seconds and the result looks designed rather than
assembled.

---

**⑥ The "…" menu (More options)**

Hover a visual: a row of small icons appears at its **top-right corner**. The **…** is *More
options*. That's where **Sort axis** lives — used constantly in this guide.

To sort a bar chart by its values: **… → Sort axis → *[the measure name]* → Sort descending**.

---

**⑦ The `fx` button (make a setting come from the data)**

Some format settings have a tiny **`fx`** button next to them. Clicking it means "don't use a
fixed value here — read it from a field or measure". This is how chart colours come from the
pipeline's palette instead of being hand-picked, and how subtitles show live numbers.

Clicking `fx` opens a dialog with a **Format style** dropdown. The two used in this guide:

- **Field value** — use the literal value in a field (a hex colour, a sentence of text).
- **Gradient** — shade from one colour to another based on a number.

---

**⑧ Undo, and saving**

- **Ctrl+Z** undoes almost anything, including in Power Query.
- **Ctrl+S** saves. Do it after finishing every Part. Power BI can and does crash.
- If a visual goes irretrievably wrong: select it and press **Delete**, then rebuild it. It's
  usually faster than debugging.

---

### 0.4 How to read every "build a visual" block below

Each of the 12 visuals is written in the same shape:

> **What it answers** — the question a reader has.
> **Position** — X / Y / Width / Height for gesture ⑤.
> **Build** — numbered clicks.
> **Format** — appearance settings for gesture ④.
> **✅ How to know it worked** — what you should be seeing.

If your screen doesn't match "How to know it worked", stop and fix it there. Errors compound.

---

## Part 1 — What you need installed

- **A Windows PC.** Power BI Desktop is Windows-only; there is no Mac version.
- **Power BI Desktop**, free, no account needed to build or view locally:
  - **Microsoft Store** → search "Power BI Desktop" → **Get**. (Easiest; auto-updates.)
  - Or download from `https://aka.ms/pbidesktopstore`.
- **The `exports/` folder**, freshly generated. Open PowerShell in the repo folder and run:
  ```powershell
  .venv\Scripts\python.exe run_pipeline.py
  ```
  It should finish without errors and `exports/` should contain 21 `.csv` files (fewer with
  `--skip-nlp`, which drops `dim_cluster` and the `nlp_*` tables) plus `_manifest.csv` and
  `_schema.md` — check `_manifest.csv` for the authoritative current list and row counts.

  > **⚠️ `--skip-nlp` does not delete the NLP tables it skips — it leaves the previous run's
  > files sitting on disk.** `_manifest.csv` lists only what the run actually wrote, so the
  > tell is a file that isn't in the manifest. At the time of writing, `dim_cluster` and the
  > five `nlp_*` files in `exports/` are a day older than everything else and come from a
  > **different data cut**. Power BI will load them without complaint and you will be looking
  > at yesterday's clusters joined to today's users. Before building anything NLP-derived,
  > compare file dates against `_manifest.csv`, or just re-run the pipeline **without**
  > `--skip-nlp` so the whole folder is one coherent export.
- **Note the full path to `exports/`.** Open the folder in File Explorer, click the address
  bar, and copy the text. It looks like:
  `C:\Users\you\Desktop\DIVERSA\chatbot_methodology_mmc\exports`
  You will paste this exactly once, in Part 3.1.

**Do not install any custom visual from AppSource.** Everything in this dashboard uses
visuals that ship with Power BI. Custom visuals break refresh and add governance risk
(doc 03 §8).

### First launch

Open Power BI Desktop. A splash/start screen appears offering "Get data", recent files, etc.
**Close it** with the × in its corner. You are now on a blank Report view — an empty white
canvas with the panes on the right. That's the starting point for everything below.

---

## Part 2 — Apply the theme

The theme sets fonts, backgrounds, gridlines and the default colour order, so you never have
to pick a colour by hand.

1. Click the **View** tab in the ribbon.
2. Find the **Themes** group — a horizontal strip of coloured swatches. Click the small **▾
   arrow** at its right end to open the full dropdown.
3. At the bottom of the dropdown, click **Browse for themes**.
4. Navigate to the repo → `docs` → select [`sami_theme.json`](sami_theme.json) → **Open**.

**✅ How to know it worked:** a toast notification appears at the top saying the theme was
imported successfully. The canvas background and any default text change subtly.

That file is generated from the same palette as `src/sami/theme.py`. Blue/teal means
magnitude, wine means accent, grey means unreliable. **Nothing is red or green** — negative
tone uses wine, never red (doc 03 §5).

**One thing the theme does *not* control: category colours.** The seven official categories
carry their own hex codes in the data itself (`dim_category[color_hex]`). You bind those
per-visual using gesture ⑦ in Part 8.2, so a palette change in the Python pipeline flows into
the report automatically on refresh.

---

## Part 3 — Load the data (Power Query)

Everything in this Part happens in a **separate window** called the Power Query Editor.

**Open it:** ribbon → **Home → Transform data** (click the button itself, not its ▾ arrow).

A new window opens. Its layout: **Queries pane** on the left (a list — currently empty), the
data preview in the middle, and **Query Settings** on the right with a *Name* box and an
*Applied Steps* list.

> **Vocabulary:** a **query** here is one recipe for loading one CSV file. You are going to
> create 20 of them. Each becomes one table in the report.

### 3.1 Create the `DataFolder` parameter

This is a single setting that tells all 20 queries where the CSVs live. Change it once and
the entire report relocates (doc 03 §2.2).

1. In the Power Query window: **Home → Manage Parameters** (▾) **→ New Parameter**.
2. Fill the dialog:
   - **Name:** `DataFolder` — exactly this, capital D, capital F. Every query references it by
     name.
   - **Type:** `Text`
   - **Suggested Values:** `Any value`
   - **Current Value:** paste your full path to `exports`, **with no trailing backslash**.
     ✅ `C:\Users\you\Desktop\DIVERSA\chatbot_methodology_mmc\exports`
     ❌ `C:\Users\you\Desktop\DIVERSA\chatbot_methodology_mmc\exports\`
3. **OK.**

**✅ How to know it worked:** `DataFolder` appears in the Queries pane on the left with a
small parameter icon, and the middle shows your path as its current value.

### 3.2 Create the first query by hand

1. **Home → New Source** (▾) **→ Blank Query.** A query called `Query1` appears in the left
   pane.
2. **Home → Advanced Editor.** A code window opens containing a couple of lines of
   placeholder text.
3. **Select all of it (Ctrl+A) and delete it.** Paste this in its place:

```m
let
    Source    = Csv.Document(
                    File.Contents(DataFolder & "\dim_user.csv"),
                    [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
                 ),
    Headers   = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected  = Table.SelectColumns(
                    Headers,
                    {"user_id", "instrument_version", "gender_clean", "age_num", "age_flag",
                     "age_range", "minors",
                     "city_canon", "department", "nationality_canon",
                     "away_duration_canon", "away_duration_order",
                     "city_duration_canon", "city_duration_order",
                     "dominant_category", "destination_country",
                     "n_questions", "n_msgs_user", "has_text", "first_seen",
                     "session_minutes",
                     "is_repeat_asker", "intends_to_stay", "cluster_id",
                     "language", "registration_status", "attempts", "is_returning",
                     "safety_alert", "escalation_status"},
                    MissingField.Error
                 ),
    Typed     = Table.TransformColumnTypes(
                    Selected,
                    {{"user_id", type text}, {"instrument_version", type text},
                     {"gender_clean", type text}, {"age_num", type number},
                     {"age_flag", type text}, {"age_range", type text}, {"minors", type text},
                     {"city_canon", type text}, {"department", type text},
                     {"nationality_canon", type text},
                     {"away_duration_canon", type text}, {"away_duration_order", Int64.Type},
                     {"city_duration_canon", type text}, {"city_duration_order", Int64.Type},
                     {"dominant_category", type text}, {"destination_country", type text},
                     {"n_questions", type number}, {"n_msgs_user", Int64.Type},
                     {"has_text", type logical}, {"first_seen", type datetime},
                     {"session_minutes", type number},
                     {"is_repeat_asker", type logical}, {"intends_to_stay", type logical},
                     {"cluster_id", Int64.Type}, {"language", type text},
                     {"registration_status", type text}, {"attempts", Int64.Type},
                     {"is_returning", type text}, {"safety_alert", type text},
                     {"escalation_status", type text}}
                 )
in
    Typed
```

> ### ⚠️ If you already built this query, you must edit it — `session_minutes` is new
>
> `Table.SelectColumns` picks **by name**, so a column the pipeline adds is silently *ignored*
> until you list it. Reopen **Home → Transform data → `dim_user` → Advanced Editor** and add
> `"session_minutes"` to the `Table.SelectColumns` list and
> `{"session_minutes", type number}` to `Table.TransformColumnTypes`, exactly as shown above.
> Without this edit the KPI2 card in Part 7 has nothing to bind to, and the field simply won't
> appear in the Data pane. **This is the only query the 2026-07-28 checkpoint changed** — every
> other block in §3.3 is unchanged.

**New since the v2 migration:** `instrument_version` (`v1` / `v2` — see the cohort warning box at
the top of this guide), `language`, `registration_status`, `attempts`, `is_returning`,
`safety_alert`, `escalation_status`, and `session_minutes` (KPI2 — see the coverage warning in
Part 5.1). The `safety_alert` / `escalation_status` pair is populated for only a handful of users
(5 in the July run) and carry free-text incident notes — treat them as a drill-down detail, not
a KPI. `is_returning` and `registration_status` are raw pass-through text from the platform
export, not a closed Yes/No set — check the actual values in Table view before building a
slicer on them.

4. Check the bottom-left of the Advanced Editor says **"No syntax errors have been detected."**
   Click **Done**.
5. In the **Query Settings** pane on the right, click the **Name** box and change `Query1` to
   `dim_user`. Press Enter.

**✅ How to know it worked:** the middle of the window shows a table of user data — columns
`user_id`, `gender_clean`, `age_num` and so on, roughly 917 rows. Accented characters like
"Medellín" render correctly.

**If you see a yellow "Information is required about data privacy" bar** — click it, choose
**Ignore Privacy Levels checks for this file**, Save. It's local CSVs; there is nothing to
leak.

**Why this M code and not the point-and-click importer** — three things make it the *contract*
version:

- `Encoding = 65001` is UTF-8, so "Medellín" and "útil" aren't mangled into "MedellÃ­n".
- `Table.SelectColumns(..., MissingField.Error)` picks columns **by name**. Extra new columns
  from the pipeline are ignored, but a **renamed or deleted** column makes the refresh fail
  loudly. That's deliberate: the schema is a contract (doc 03 §2.3).
- Explicit types mean no guessing and no locale surprises with decimal points.

### 3.3 Repeat for the other 20 tables

**The fast route (do this 20 times):**

1. **Home → New Source (▾) → Blank Query.**
2. **Home → Advanced Editor.**
3. **Ctrl+A**, delete, and paste the whole code block for that table from
   [§3.3.1 below](#331-the-twenty-queries-copy-paste-each-one-whole). Check it says
   *"No syntax errors have been detected."* → **Done**.
4. In **Query Settings → Name**, type the query name (it must match the CSV filename exactly,
   without `.csv`). Press Enter.

The queries are already written out in full — you never have to edit one by hand. The table
below is just the summary of what each contains; skip to §3.3.1 to build. "Non-text types"
means everything else in that query is `type text`.

| Query name (= CSV filename) | Columns to list in `Table.SelectColumns` | Columns that are *not* text |
|---|---|---|
| `fact_message` | `message_id, user_id, ts, city_canon, dominant_category, seq, n_msgs_user, sentiment_label, cluster_id` | `message_id, seq, n_msgs_user, cluster_id` → `Int64.Type`; `ts` → `type datetime` |
| `fact_meal` | `user_id, ts, usefulness_rating, rating_num, would_recommend, recommendation_text, discovery_channel, no_usefulness_reason, reason_is_valid` | `rating_num` → `Int64.Type`; `ts` → `type datetime`; `reason_is_valid` → `type logical` |
| `dim_category` | `category_key, category_es, category_en, color_hex, display_order` | `display_order` → `Int64.Type` |
| `dim_city` | `city_canon, department, lat, lon` | `lat, lon` → `type number` |
| `dim_cluster` | `cluster_id, name, n_users, n_messages, median_age, top_categories` | `cluster_id, n_users, n_messages` → `Int64.Type`; `median_age` → `type number` |
| `agg_weekly_category` | `week, category, n` | `week` → `type date`; `n` → `Int64.Type` |
| `agg_daily_volume` | `day, n` | `day` → `type date`; `n` → `Int64.Type` |
| `agg_weekly_rating` | `week, mean_rating, n` | `week` → `type date`; `mean_rating` → `type number`; `n` → `Int64.Type` |
| `agg_funnel` | `stage_order, stage, n, conversion_from_prev` | `stage_order, n` → `Int64.Type`; `conversion_from_prev` → `type number` |
| `agg_registration_funnel` | `instrument_version, stage_order, stage, n, pct_of_started` | `stage_order, n` → `Int64.Type`; `pct_of_started` → `type number` |
| `agg_language` | `language, instrument_version, n_users` | `n_users` → `Int64.Type` |
| `agg_priority_matrix` | `category, messages, users, pct_repeat, mean_rating, meal_n, rating_is_fallback, pct_negative, n_axes, unmet_need` | `messages, users, meal_n, n_axes` → `Int64.Type`; `pct_repeat, pct_negative, mean_rating, unmet_need` → `type number`; `rating_is_fallback` → `type logical` |
| `agg_entities_by_kind` | `kind, entity, n` | `n` → `Int64.Type` |
| `nlp_emergent_themes` | `theme, slug, n_messages, n_users` | `n_messages, n_users` → `Int64.Type` |
| `nlp_umap` | `user_id, x, y, cluster_id` | `x, y` → `type number`; `cluster_id` → `Int64.Type` |
| `nlp_cluster_terms` | `cluster_id, rank, term, weight` | `cluster_id, rank` → `Int64.Type`; `weight` → `type number` |
| `nlp_tone_confusion` | `human_label, model_label, n` | `n` → `Int64.Type` |
| `nlp_voices` | `cluster_id, name, message` | `cluster_id` → `Int64.Type` |
| `meta_run` | `key, value` | none — all text, deliberately (the values are mixed types) |
| `parity_check` | `metric, exported_value, reconciliation_value, match` | `exported_value, reconciliation_value` → `type number`; `match` → `type logical` |

**Do not create queries for** `_manifest.csv` (checksums) or `_schema.md` (documentation).

#### 3.3.1 The twenty queries (copy-paste each one whole)

Every block below is complete and self-contained: paste it into a blank query's Advanced
Editor, click Done, and name the query as shown in the heading. Nothing needs editing.

> **Why every block ends with `, "en-US"`.** That third argument to
> `Table.TransformColumnTypes` is the *culture* used to read numbers and dates. Python writes
> `0.128` and `2026-05-05`; a Windows machine set to Spanish would otherwise try to read the
> dot as a thousands separator and either fail or silently produce 128. Pinning the culture
> makes the load identical on every machine. (`dim_user` in §3.2 works without it because
> Power BI falls back to the file's own locale metadata, but pin it there too if that query
> ever throws type errors.)

---

**`fact_message`**

```m
let
    Source    = Csv.Document(
                    File.Contents(DataFolder & "\fact_message.csv"),
                    [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
                 ),
    Headers   = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected  = Table.SelectColumns(
                    Headers,
                    {"message_id", "user_id", "ts", "city_canon", "dominant_category",
                     "seq", "n_msgs_user", "sentiment_label", "cluster_id"},
                    MissingField.Error
                 ),
    Typed     = Table.TransformColumnTypes(
                    Selected,
                    {{"message_id", type text}, {"user_id", type text},
                     {"ts", type datetime}, {"city_canon", type text},
                     {"dominant_category", type text}, {"seq", Int64.Type},
                     {"n_msgs_user", Int64.Type}, {"sentiment_label", type text},
                     {"cluster_id", Int64.Type}},
                    "en-US"
                 )
in
    Typed
```

> **`message_id` is a content hash now, not a row number.** It used to be `Table.TransformColumnTypes(..., {"message_id", Int64.Type}, ...)` — a stable numeric index into the sorted message spine. The v2 migration replaced it with a short hex digest of the message content, so a re-sort (e.g. a bigger export) can never silently reassign an id to a different message the way a positional index could. Type it as `type text`, not `Int64.Type` — the old numeric typing will error on the new values.

---

**`fact_meal`**

```m
let
    Source    = Csv.Document(
                    File.Contents(DataFolder & "\fact_meal.csv"),
                    [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
                 ),
    Headers   = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected  = Table.SelectColumns(
                    Headers,
                    {"user_id", "ts", "usefulness_rating", "rating_num", "would_recommend",
                     "recommendation_text", "discovery_channel",
                     "no_usefulness_reason", "reason_is_valid"},
                    MissingField.Error
                 ),
    Typed     = Table.TransformColumnTypes(
                    Selected,
                    {{"user_id", type text}, {"ts", type datetime},
                     {"usefulness_rating", type text}, {"rating_num", Int64.Type},
                     {"would_recommend", type text}, {"recommendation_text", type text},
                     {"discovery_channel", type text}, {"no_usefulness_reason", type text},
                     {"reason_is_valid", type logical}},
                    "en-US"
                 )
in
    Typed
```

> ⚠️ **`no_usefulness_reason` must always be filtered on `reason_is_valid = true`.** V2's
> "why wasn't it useful" question has broken skip logic — it fired for satisfied respondents
> too, so most of the raw text is a satisfied user answering a question that shouldn't have
> been asked. At `fact_meal`'s user grain, only **31** of the rows have `reason_is_valid = true`
> and are analytically usable; the rest must never be counted or quoted. Every visual, table,
> or word cloud built on this column needs a page/visual filter `reason_is_valid = true`, not
> just a caption saying so.

---

**`dim_category`**

```m
let
    Source    = Csv.Document(
                    File.Contents(DataFolder & "\dim_category.csv"),
                    [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
                 ),
    Headers   = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected  = Table.SelectColumns(
                    Headers,
                    {"category_key", "category_es", "category_en", "color_hex",
                     "display_order"},
                    MissingField.Error
                 ),
    Typed     = Table.TransformColumnTypes(
                    Selected,
                    {{"category_key", type text}, {"category_es", type text},
                     {"category_en", type text}, {"color_hex", type text},
                     {"display_order", Int64.Type}},
                    "en-US"
                 )
in
    Typed
```

---

**`dim_city`**

```m
let
    Source    = Csv.Document(
                    File.Contents(DataFolder & "\dim_city.csv"),
                    [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
                 ),
    Headers   = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected  = Table.SelectColumns(
                    Headers,
                    {"city_canon", "department", "lat", "lon"},
                    MissingField.Error
                 ),
    Typed     = Table.TransformColumnTypes(
                    Selected,
                    {{"city_canon", type text}, {"department", type text},
                     {"lat", type number}, {"lon", type number}},
                    "en-US"
                 )
in
    Typed
```

---

**`dim_cluster`**

```m
let
    Source    = Csv.Document(
                    File.Contents(DataFolder & "\dim_cluster.csv"),
                    [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
                 ),
    Headers   = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected  = Table.SelectColumns(
                    Headers,
                    {"cluster_id", "name", "n_users", "n_messages", "median_age",
                     "top_categories"},
                    MissingField.Error
                 ),
    Typed     = Table.TransformColumnTypes(
                    Selected,
                    {{"cluster_id", Int64.Type}, {"name", type text},
                     {"n_users", Int64.Type}, {"n_messages", Int64.Type},
                     {"median_age", type number}, {"top_categories", type text}},
                    "en-US"
                 )
in
    Typed
```

---

**`agg_weekly_category`**

```m
let
    Source    = Csv.Document(
                    File.Contents(DataFolder & "\agg_weekly_category.csv"),
                    [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
                 ),
    Headers   = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected  = Table.SelectColumns(
                    Headers,
                    {"week", "category", "n"},
                    MissingField.Error
                 ),
    Typed     = Table.TransformColumnTypes(
                    Selected,
                    {{"week", type date}, {"category", type text}, {"n", Int64.Type}},
                    "en-US"
                 )
in
    Typed
```

---

**`agg_daily_volume`**

```m
let
    Source    = Csv.Document(
                    File.Contents(DataFolder & "\agg_daily_volume.csv"),
                    [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
                 ),
    Headers   = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected  = Table.SelectColumns(
                    Headers,
                    {"day", "n"},
                    MissingField.Error
                 ),
    Typed     = Table.TransformColumnTypes(
                    Selected,
                    {{"day", type date}, {"n", Int64.Type}},
                    "en-US"
                 )
in
    Typed
```

---

**`agg_weekly_rating`**

```m
let
    Source    = Csv.Document(
                    File.Contents(DataFolder & "\agg_weekly_rating.csv"),
                    [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
                 ),
    Headers   = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected  = Table.SelectColumns(
                    Headers,
                    {"week", "mean_rating", "n"},
                    MissingField.Error
                 ),
    Typed     = Table.TransformColumnTypes(
                    Selected,
                    {{"week", type date}, {"mean_rating", type number}, {"n", Int64.Type}},
                    "en-US"
                 )
in
    Typed
```

> Weeks with no MEAL responses have an **empty** `mean_rating` — it becomes `null`, which is
> correct. Do not replace those nulls with 0; a zero would be drawn as a rating of zero.

---

**`agg_funnel`**

```m
let
    Source    = Csv.Document(
                    File.Contents(DataFolder & "\agg_funnel.csv"),
                    [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
                 ),
    Headers   = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected  = Table.SelectColumns(
                    Headers,
                    {"stage_order", "stage", "n", "conversion_from_prev"},
                    MissingField.Error
                 ),
    Typed     = Table.TransformColumnTypes(
                    Selected,
                    {{"stage_order", Int64.Type}, {"stage", type text},
                     {"n", Int64.Type}, {"conversion_from_prev", type number}},
                    "en-US"
                 )
in
    Typed
```

> `agg_funnel` is the **usage** funnel (asked a question → got a response → …), unrelated to
> `agg_registration_funnel` below, which is about whether people finished *signing up*. Don't
> confuse the two when picking which one a "funnel" visual should bind to.

---

**`agg_registration_funnel`** — new in the v2 migration

```m
let
    Source    = Csv.Document(
                    File.Contents(DataFolder & "\agg_registration_funnel.csv"),
                    [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
                 ),
    Headers   = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected  = Table.SelectColumns(
                    Headers,
                    {"instrument_version", "stage_order", "stage", "n", "pct_of_started"},
                    MissingField.Error
                 ),
    Typed     = Table.TransformColumnTypes(
                    Selected,
                    {{"instrument_version", type text}, {"stage_order", Int64.Type},
                     {"stage", type text}, {"n", Int64.Type},
                     {"pct_of_started", type number}},
                    "en-US"
                 )
in
    Typed
```

> ⚠️ **Never sum this table across `instrument_version`.** v1's rows are **100% complete by
> construction** — the legacy platform never recorded a partial registration attempt, so every
> migrated row looks like a finished one. Pooling v1 with v2 dilutes a real drop-off signal to
> nothing: v1 reads **99.9%** complete, v2 reads **89.2%** complete. Always slice or split this
> visual by `instrument_version` — put it on the axis/legend, never filter it away. `stage`
> values are `registration started / registration completed / abandoned / in progress / other`;
> sort by `stage_order`.

---

**`agg_language`** — new in the v2 migration

```m
let
    Source    = Csv.Document(
                    File.Contents(DataFolder & "\agg_language.csv"),
                    [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
                 ),
    Headers   = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected  = Table.SelectColumns(
                    Headers,
                    {"language", "instrument_version", "n_users"},
                    MissingField.Error
                 ),
    Typed     = Table.TransformColumnTypes(
                    Selected,
                    {{"language", type text}, {"instrument_version", type text},
                     {"n_users", Int64.Type}},
                    "en-US"
                 )
in
    Typed
```

> ⚠️ **`n_users` counts users who *ever* used a language, not users assigned to one.** A
> multilingual user who wrote in both Spanish and English contributes to both rows, so
> `SUM(agg_language[n_users])` **does not equal** the user total in `dim_user` — that's
> deliberate multilingual semantics, not a bug to "fix" with a distinct-count workaround. Don't
> build a "% of users by language" card from this table without checking for double-counting
> first; it's fine for a bar of "users who used each language", not for a pie that should sum
> to 100%.

---

**`agg_priority_matrix`**

```m
let
    Source    = Csv.Document(
                    File.Contents(DataFolder & "\agg_priority_matrix.csv"),
                    [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
                 ),
    Headers   = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected  = Table.SelectColumns(
                    Headers,
                    {"category", "messages", "users", "pct_repeat", "mean_rating",
                     "meal_n", "rating_is_fallback", "pct_negative", "n_axes",
                     "unmet_need"},
                    MissingField.Error
                 ),
    Typed     = Table.TransformColumnTypes(
                    Selected,
                    {{"category", type text}, {"messages", Int64.Type},
                     {"users", Int64.Type}, {"pct_repeat", type number},
                     {"mean_rating", type number}, {"meal_n", Int64.Type},
                     {"rating_is_fallback", type logical}, {"pct_negative", type number},
                     {"n_axes", Int64.Type}, {"unmet_need", type number}},
                    "en-US"
                 )
in
    Typed
```

> ⚠️ `pct_negative` is tone-derived. It loads because `unmet_need` is computed from it, but it
> must never be placed on a visual — see the rule at the top of this guide.

---

**`agg_entities_by_kind`**

```m
let
    Source    = Csv.Document(
                    File.Contents(DataFolder & "\agg_entities_by_kind.csv"),
                    [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
                 ),
    Headers   = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected  = Table.SelectColumns(
                    Headers,
                    {"kind", "entity", "n"},
                    MissingField.Error
                 ),
    Typed     = Table.TransformColumnTypes(
                    Selected,
                    {{"kind", type text}, {"entity", type text}, {"n", Int64.Type}},
                    "en-US"
                 )
in
    Typed
```

---

**`nlp_emergent_themes`**

```m
let
    Source    = Csv.Document(
                    File.Contents(DataFolder & "\nlp_emergent_themes.csv"),
                    [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
                 ),
    Headers   = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected  = Table.SelectColumns(
                    Headers,
                    {"theme", "slug", "n_messages", "n_users"},
                    MissingField.Error
                 ),
    Typed     = Table.TransformColumnTypes(
                    Selected,
                    {{"theme", type text}, {"slug", type text},
                     {"n_messages", Int64.Type}, {"n_users", Int64.Type}},
                    "en-US"
                 )
in
    Typed
```

---

**`nlp_umap`**

```m
let
    Source    = Csv.Document(
                    File.Contents(DataFolder & "\nlp_umap.csv"),
                    [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
                 ),
    Headers   = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected  = Table.SelectColumns(
                    Headers,
                    {"user_id", "x", "y", "cluster_id"},
                    MissingField.Error
                 ),
    Typed     = Table.TransformColumnTypes(
                    Selected,
                    {{"user_id", type text}, {"x", type number}, {"y", type number},
                     {"cluster_id", Int64.Type}},
                    "en-US"
                 )
in
    Typed
```

---

**`nlp_cluster_terms`**

```m
let
    Source    = Csv.Document(
                    File.Contents(DataFolder & "\nlp_cluster_terms.csv"),
                    [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
                 ),
    Headers   = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected  = Table.SelectColumns(
                    Headers,
                    {"cluster_id", "rank", "term", "weight"},
                    MissingField.Error
                 ),
    Typed     = Table.TransformColumnTypes(
                    Selected,
                    {{"cluster_id", Int64.Type}, {"rank", Int64.Type},
                     {"term", type text}, {"weight", type number}},
                    "en-US"
                 )
in
    Typed
```

---

**`nlp_tone_confusion`**

```m
let
    Source    = Csv.Document(
                    File.Contents(DataFolder & "\nlp_tone_confusion.csv"),
                    [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
                 ),
    Headers   = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected  = Table.SelectColumns(
                    Headers,
                    {"human_label", "model_label", "n"},
                    MissingField.Error
                 ),
    Typed     = Table.TransformColumnTypes(
                    Selected,
                    {{"human_label", type text}, {"model_label", type text},
                     {"n", Int64.Type}},
                    "en-US"
                 )
in
    Typed
```

---

**`nlp_voices`**

```m
let
    Source    = Csv.Document(
                    File.Contents(DataFolder & "\nlp_voices.csv"),
                    [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
                 ),
    Headers   = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected  = Table.SelectColumns(
                    Headers,
                    {"cluster_id", "name", "message"},
                    MissingField.Error
                 ),
    Typed     = Table.TransformColumnTypes(
                    Selected,
                    {{"cluster_id", Int64.Type}, {"name", type text},
                     {"message", type text}},
                    "en-US"
                 )
in
    Typed
```

---

**`meta_run`**

```m
let
    Source    = Csv.Document(
                    File.Contents(DataFolder & "\meta_run.csv"),
                    [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
                 ),
    Headers   = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected  = Table.SelectColumns(
                    Headers,
                    {"key", "value"},
                    MissingField.Error
                 ),
    Typed     = Table.TransformColumnTypes(
                    Selected,
                    {{"key", type text}, {"value", type text}}
                 )
in
    Typed
```

> Both columns stay **text** on purpose — `value` holds dates, counts, filenames and `True`/
> `False` in the same column, so any other type would break half the rows. The Part 5 measures
> (`Export Date`, `Tone Gate Banner`) convert what they need with `DATEVALUE`.

---

**`parity_check`**

```m
let
    Source    = Csv.Document(
                    File.Contents(DataFolder & "\parity_check.csv"),
                    [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
                 ),
    Headers   = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected  = Table.SelectColumns(
                    Headers,
                    {"metric", "exported_value", "reconciliation_value", "match"},
                    MissingField.Error
                 ),
    Typed     = Table.TransformColumnTypes(
                    Selected,
                    {{"metric", type text}, {"exported_value", type number},
                     {"reconciliation_value", type number}, {"match", type logical}},
                    "en-US"
                 )
in
    Typed
```

---

**✅ How to know Part 3.3 worked:** the Queries pane lists **21 queries plus the `DataFolder`
parameter** — 19 from the pre-v2-migration table set plus `agg_registration_funnel` and
`agg_language`. Click each in turn and confirm the preview shows rows, not a yellow or red
error banner. The row-count figures quoted through the rest of this guide (e.g. `fact_message`
2,991, `dim_user` 917) are from the run this guide was originally written against, before the
July 2026 platform migration; a fresh `run_pipeline.py` run against the current exports
produces materially larger numbers (`dim_user` 1,392, `fact_message` 4,663+ once NLP is
included) — use `exports/_manifest.csv` for the row counts of whatever export you're actually
loading, not the numbers printed here.

**⚠️ Booleans are the one real gotcha.** `has_text`, `is_repeat_asker`, `intends_to_stay`,
`match` and `rating_is_fallback` are written by Python as the literal strings `True`/`False`.
`type logical` normally converts them. If one stubbornly stays text (you'll see it left-aligned
with an `ABC` header icon rather than centred with a checkbox), **leave it as text** and later
write its DAX comparison as `= "True"` instead of `= TRUE()`.

**If you ran the pipeline with `--skip-nlp`:** `dim_cluster` and every `nlp_*` file don't
exist, and those queries will show a red error. Always build against a full run.

### 3.4 The calendar table

Every dashboard with a date filter needs a dedicated date table. Power Query builds it, so it
grows automatically when a future export covers a longer period (doc 03 §2.1).

**New Source → Blank Query → Advanced Editor**, paste this, **Done**, rename to `dim_date`:

```m
let
    MinTs      = List.Min(fact_message[ts]),
    MaxTs      = List.Max(fact_message[ts]),
    StartDate  = Date.StartOfWeek(Date.From(MinTs), Day.Monday),
    EndDate    = Date.EndOfWeek(Date.From(MaxTs), Day.Monday),
    DayCount   = Duration.Days(EndDate - StartDate) + 1,
    Dates      = List.Dates(StartDate, DayCount, #duration(1, 0, 0, 0)),
    AsTable    = Table.FromList(Dates, Splitter.SplitByNothing(), {"Date"}),
    Typed      = Table.TransformColumnTypes(AsTable, {{"Date", type date}}),
    WithParts  = Table.AddColumn(Typed, "Year", each Date.Year([Date]), Int64.Type),
    WithMonth  = Table.AddColumn(WithParts, "Month no", each Date.Month([Date]), Int64.Type),
    WithMName  = Table.AddColumn(WithMonth, "Month", each Date.ToText([Date], "MMM yyyy", "en-GB"), type text),
    WithWeek   = Table.AddColumn(WithMName, "Week start", each Date.StartOfWeek([Date], Day.Monday), type date),
    WithLabel  = Table.AddColumn(WithWeek, "Date label", each Date.ToText([Date], "dd MMM yyyy", "en-GB"), type text)
in
    WithLabel
```

**✅ How to know it worked:** a table of one row per day, with columns `Date`, `Year`,
`Month no`, `Month`, `Week start`, `Date label`. The `Date label` column reads like
"25 Mar 2026" — the format doc 03 §5 requires.

### 3.5 Load everything into the report

**Home → Close & Apply** (the leftmost button, with the ▾; click the button itself).

The Power Query window closes and a progress dialog counts through the tables. First load
takes about 30 seconds.

**✅ How to know it worked:** you're back in Report view, and the **Data pane** on the right
lists **22 tables**: your 21 CSV queries plus `dim_date`. No table has a warning triangle.

**Press Ctrl+S now** and save as `mmc_dashboard.pbix` in the repo root.

---

## Part 4 — The model: relationships, sorting, hiding

Switch to **Model view** — the third icon down in the view switcher on the far left (the one
that looks like joined boxes).

You'll see your 22 tables as draggable boxes. Power BI may have auto-detected some
relationships and drawn lines between them. **Delete every line it drew** before you start:
click a line to select it (it turns bold), press **Delete**, confirm. Auto-detection guesses
wrong often enough that a clean start is faster than an audit.

### 4.1 Draw the eight relationships

A relationship links two tables through a shared column, so filtering one filters the other.

**To create one:** drag the **first** field listed below **onto** the second field, then in
the dialog that appears accept the defaults — **Cardinality: One to many (1:*)**,
**Cross-filter direction: Single** — and click **OK**.

| Drag this (the "one" side) | Onto this (the "many" side) | Why |
|---|---|---|
| `dim_user[user_id]` | `fact_message[user_id]` | messages belong to users |
| `dim_user[user_id]` | `fact_meal[user_id]` | survey responses belong to users |
| `dim_user[user_id]` | `nlp_umap[user_id]` | one scatter point per user |
| `dim_city[city_canon]` | `dim_user[city_canon]` | map coordinates + the city slicer |
| `dim_category[category_key]` | `fact_message[dominant_category]` | category labels & colours |
| `dim_cluster[cluster_id]` | `dim_user[cluster_id]` | archetypes |
| `dim_date[Date]` | `fact_message[ts]` | date slicer over messages |
| `dim_date[Date]` | `fact_meal[ts]` | date slicer over survey responses |

**Two rules, enforced by doc 03 §3:**

- **Every relationship stays single-direction.** If the dialog offers cross-filter **Both**,
  say no. Bidirectional filters create ambiguity that silently corrupts numbers.
- **If Power BI warns about ambiguity or an inactive relationship**, you've created a
  duplicate path. Click the extra line and press Delete.

**If the `dim_date → fact_*` drag is refused:** Power BI is usually happy relating a date
column to a datetime column — it compares the date part and ignores the time. If yours isn't,
the fix is to give each fact table its own date-only column and relate on *that*. Full recipe
in [4.1a](#41a--fallback-give-the-fact-tables-a-date-only-column) below; skip it if your eight
lines drew fine.

#### 4.1a — Fallback: give the fact tables a date-only column

**Symptom:** the drag produces *"You can't create a relationship between these two columns
because one of the columns must have unique values"*, or the dialog opens with a red banner
about mismatched data types, or the line draws but every date-sliced visual comes back blank.

The cause is always the same: `dim_date[Date]` is `type date`, `fact_message[ts]` is
`type datetime`, and the datetime column carries a time component (`2025-03-14 09:41:00`),
so no row in it ever equals a bare date. Stripping the time makes the two columns comparable.

**Step 1 — reopen Power Query.** Ribbon → **Home → Transform data**. The editor opens on
whatever query you touched last.

**Step 2 — edit `fact_message`.** Click `fact_message` in the **Queries** list on the left,
then **Home → Advanced Editor**. You'll see the query you pasted in Part 3, ending:

```m
                    "en-US"
                 )
in
    Typed
```

Change those last three lines to add one step. Note the comma after the closing `)` of
`Typed` — that's the part people miss:

```m
                    "en-US"
                 ),
    WithDate  = Table.AddColumn(Typed, "date", each Date.From([ts]), type date)
in
    WithDate
```

`Date.From` throws away the time and returns a true date value; the trailing `type date` tells
Power Query the new column's type up front, so you don't have to set it afterwards. Click
**Done**.

**Step 3 — do the same to `fact_meal`.** Identical edit, identical last step name. Both fact
tables need it — the two `dim_date` relationships in the table above are separate lines.

**Step 4 — check the preview.** With `fact_meal` selected, look at the rightmost column in the
preview grid. It should be headed `date`, show values like `14/03/2025` with no time, and
carry a **calendar icon** in the header (not the `📅🕐` datetime icon, and definitely not
`ABC`). If it shows `ABC` or errors, your `ts` column never got typed as datetime back in
Part 3 — fix that first, then this step works.

**Step 5 — Home → Close & Apply.** Wait for the refresh to finish.

**Step 6 — redraw the two relationships** in Model view, using the new column as the "many"
side:

| Drag this | Onto this |
|---|---|
| `dim_date[Date]` | `fact_message[date]` |
| `dim_date[Date]` | `fact_meal[date]` |

Same defaults as before: **One to many (1:\*)**, **Cross-filter: Single**.

**Step 7 — hide `date` too.** In §4.4 you already hide `fact_message[ts]` and `fact_meal[ts]`;
add `fact_message[date]` and `fact_meal[date]` to that list. Every visual gets its dates from
`dim_date`, so none of the four should ever be draggable.

**Nothing else changes.** Every measure in Part 6 filters through `dim_date[Date]`, never
through `ts` directly, so `Messages Prev 4 Weeks`, `Date Range Label` and the weekly trend
visuals all keep working untouched.

**✅ How to know it worked:** drop a card on a blank canvas with `[Messages]`, add a slicer on
`dim_date[Date]`, and narrow the range. The card number must drop. If it stays at 2,991 the
relationship isn't filtering — check the line has a `1` at the `dim_date` end and an arrowhead
pointing away from it.

**The tables with no lines are correct.** `agg_funnel`, `agg_priority_matrix`,
`agg_entities_by_kind`, `agg_weekly_category`, `agg_daily_volume`, `agg_weekly_rating`, all
the `nlp_*` tables, `meta_run` and `parity_check` are **standalone** — each already holds
exactly what its visual needs, pre-computed. That's by design, but it has a consequence you
must disclose on screen: **standalone visuals do not respond to the slicers.** See
[Appendix A, D3](#d3--the-standalone-agg-tables-ignore-the-slicers).

#### ✅ Checkpoint: is your existing work correct?

If you built the model from the earlier guide, verify all of this before continuing:

- [ ] The Data pane lists exactly **20 tables**.
- [ ] Model view shows exactly **8 relationship lines**, no more.
- [ ] Every line has a **`1`** at one end and a **`*`** at the other.
- [ ] Every line has **one arrowhead**, pointing from the `1` side to the `*` side. Two
      arrowheads means bidirectional — double-click the line and set Cross-filter to *Single*.
- [ ] No line is **dashed** (dashed = inactive; delete it).
- [ ] Switch to Table view (grid icon), click `dim_user`, and confirm `first_seen` shows dates
      and `age_num` shows numbers, not text.

### 4.2 Tell Power BI which table is the calendar

Without this, time-comparison measures (`Messages Prev 4 Weeks`) return blank.

1. In the **Data pane**, click the table name `dim_date` to select it.
2. Ribbon → **Table tools** tab (it only appears when a table is selected) →
   **Mark as date table** (▾) → **Mark as date table**.
3. In the dialog, **Date column:** `Date`. Click **OK**.

**✅ How to know it worked:** a green tick / validation message, and the `dim_date` table icon
now carries a small calendar badge.

### 4.3 Sort-by columns

Without these, "less than a month" sorts *after* "several years" because it's alphabetical.
Each of these pairs a display column with a hidden number column that defines the real order.

**For each row:** in the **Data pane**, expand the table and **click the column in the left
column below** → ribbon → **Column tools** tab → **Sort by column** (▾) → pick the column in
the right column.

| Sort this column… | …by this column |
|---|---|
| `dim_user[away_duration_canon]` | `dim_user[away_duration_order]` |
| `dim_user[city_duration_canon]` | `dim_user[city_duration_order]` |
| `dim_category[category_en]` | `dim_category[display_order]` |
| `agg_funnel[stage]` | `agg_funnel[stage_order]` |

**✅ How to know it worked:** you won't see anything change yet — it shows up in Part 7.5,
where the settlement bars come out in duration order instead of alphabetical order.

### 4.4 Hide the fields nobody should ever drag onto a canvas

Hiding keeps the Data pane clean and prevents accidents. Hidden fields still work in
relationships and measures.

**For each:** right-click the field in the Data pane → **Hide in report view**.

Hide: every `user_id`, every `message_id`, `dim_category[category_key]`, every `cluster_id`,
every column ending in `_order`, `dim_date[Month no]`, `fact_message[ts]`, `fact_meal[ts]`
(the calendar is the date source now), and `dim_category[color_hex]` (it's bound via `fx`,
never dragged). If you took the §4.1a fallback, hide `fact_message[date]` and `fact_meal[date]`
as well.

**To see hidden fields again** (you'll need this when troubleshooting): right-click anywhere
in the Data pane → **View hidden**.

### 4.5 Create the measures table

All measures will live in one table so the Data pane stays navigable and every calculation is
findable in one place (doc 03 §3).

1. Ribbon → **Home → Enter data**. A tiny spreadsheet dialog opens.
2. Leave the single empty column exactly as it is. In the **Name** box at the bottom, type
   `_Measures`.
3. Click **Load**.

**✅ How to know it worked:** `_Measures` appears in the Data pane. Because its name starts
with an underscore it sorts to the top of the list, which is why we named it that.

4. After you finish Part 5, come back: right-click its `Column1` → **Hide in report view**.
   The table then displays with a calculator icon and floats to the top of the pane.

**Ctrl+S.**

---

## Part 5 — The measures

A measure is a calculation written once and reused everywhere, recalculating itself for
whatever filters are active.

### How to add each of the measures below

1. In the **Data pane**, right-click `_Measures` → **New measure**.
2. A formula bar opens above the canvas containing `Measure = `.
3. **Select all of it and paste** the DAX block from this guide (the block includes the
   measure's name and the `=`). Press **Enter**.
4. The measure appears in `_Measures` with a calculator icon. **Leave it selected** and do
   two more things in the **Measure tools** ribbon tab that has appeared:
   - **Description** — paste the *Description* text given below the code. **This is not
     optional.** These descriptions become the tooltips readers see when they hover a field
     name, and they're copied onto the About page glossary (doc 03 §3, §5).
   - **Format** — set the format given below (e.g. *Percentage* with *0* decimal places, using
     the format dropdown and the decimal-places spinner in that same ribbon tab).

**If you get a red squiggle / error:** most often a smart-quote problem from copy-paste, or a
measure referencing another measure you haven't created yet. Create them in the order given
here and that second problem disappears.

**Tip:** the formula bar can be dragged taller by its bottom edge — worth doing for the longer
measures.

---

### 5.1 Reach and cohort

```DAX
Users = COUNTROWS ( dim_user )
```
**Description:** Distinct people who reached SAMI in the loaded export (917 in the July run).
Responds to city and profile slicers. **Does not respond to the date slicer** — use `Active
Users` for that.
**Format:** Whole number, thousands separator.

```DAX
Active Users =
DISTINCTCOUNT ( fact_message[user_id] )
```
**Description:** Users who sent at least one message inside the selected date range. This is
the date-responsive reach measure; use it in anything drawn on a time axis.
**Format:** Whole number.

```DAX
New Users =
VAR FirstDay = MIN ( dim_date[Date] )
VAR LastDay  = MAX ( dim_date[Date] )
RETURN
    CALCULATE (
        COUNTROWS ( dim_user ),
        FILTER (
            dim_user,
            dim_user[first_seen] >= FirstDay
                && dim_user[first_seen] < LastDay + 1
        )
    )
```
**Description:** Users whose first-ever message falls inside the selected window.
**Format:** Whole number.

```DAX
Avg Session Time =
MEDIANX (
    FILTER ( dim_user, NOT ( ISBLANK ( dim_user[session_minutes] ) ) ),
    dim_user[session_minutes]
)
```
**Description:** KPI2 from the 2026-07-28 checkpoint — how long a user's conversation lasts,
from the record being created to their last message. **Reads ~3.7 minutes.**
**Format:** Decimal number, **1** decimal place. Label the card **"Avg session (min)"** so the
unit is on screen; a bare `3.7` next to `1,392 users` reads as a count.

> ### ⚠️ Two things about this measure that will bite you
>
> **1. It covers 5% of users — use `MEDIANX`, never a hand-rolled average.**
> `session_minutes` is blank for 1,322 of 1,392 users, because the platform only fills
> `Last Message At` for some records and the pipeline only trusts the timestamps written from
> 2026-07-24 onward (the earlier ones sit on a ~2h clock offset that would push this KPI to
> ~44 **hours** — see `exports/_schema.md`). `MEDIANX` over a `FILTER`ed table ignores blanks
> correctly. `DIVIDE(SUM(...), COUNTROWS(dim_user))` would divide by all 1,392 and give you a
> number about twenty times too small. Coverage grows on its own as v2-era records accumulate;
> nothing needs changing when it does.
>
> **2. Median, not mean — deliberately.** The values are raw, with no outlier capping (that was
> the decision). One user's session runs 3.4 days, which drags `AVERAGE` to **146 minutes**. If
> you want the mean visible anyway, put it in the card's tooltip, not the callout —
> `Avg Session Time (mean) = AVERAGE ( dim_user[session_minutes] )`.

```DAX
Cities Covered =
CALCULATE (
    DISTINCTCOUNT ( dim_user[city_canon] ),
    dim_user[city_canon] <> "Other"
)
```
**Description:** Named cities with at least one user. Excludes the "Other" bucket, which has no
location.
**Format:** Whole number.

```DAX
% Intending to Stay =
DIVIDE (
    CALCULATE ( COUNTROWS ( dim_user ), dim_user[intends_to_stay] = TRUE () ),
    COUNTROWS ( dim_user )
)
```
**Description:** Share of users who state no onward destination, or name Colombia.
Self-reported.
**Format:** Percentage, **0** decimal places (doc 03 §5 requires whole percentages).

> If `intends_to_stay` stayed as text in Part 3.3, write `= "True"` instead of `= TRUE()`.
> Same for every boolean comparison below.

### 5.2 Demand

```DAX
Messages = COUNTROWS ( fact_message )
```
**Description:** Messages sent to SAMI in the current selection (2,991 in the July run).
**Format:** Whole number, thousands separator.

```DAX
% Legal Documentation =
DIVIDE (
    CALCULATE ( [Messages], dim_category[category_key] = "legal_documentation" ),
    [Messages]
)
```
**Description:** Share of messages whose dominant category is legal & documentation.
**Format:** Percentage, 0 dp.

```DAX
Median Messages per User =
MEDIANX ( VALUES ( fact_message[user_id] ), CALCULATE ( COUNTROWS ( fact_message ) ) )
```
**Description:** Median messages per **message-sending** user — a median across users, never
an average of averages (doc 03 §3).
**Format:** Decimal, 1 dp.

```DAX
% Zero-question Users =
DIVIDE (
    CALCULATE ( COUNTROWS ( dim_user ), dim_user[has_text] = FALSE () ),
    COUNTROWS ( dim_user )
)
```
**Description:** Users who registered but never sent a message (117 of 917 in the July run).
**Format:** Percentage, 0 dp.

```DAX
% Repeat Askers =
DIVIDE (
    CALCULATE ( COUNTROWS ( dim_user ), dim_user[is_repeat_asker] = TRUE () ),
    COUNTROWS ( dim_user )
)
```
**Description:** Users at or above the 90th percentile of message count — the same definition
as the pipeline's `reconciliation.repeat_askers_pct` (11.9%).
**Format:** Percentage, 0 dp.

```DAX
% Outside Official Taxonomy =
DIVIDE (
    CALCULATE ( [Messages], fact_message[dominant_category] = "unclassified" ),
    [Messages]
)
```
**Description:** Share of messages the 7-category taxonomy could not classify (0.9% in the
July run — the classifier assigns a category almost always, so read the coverage-gaps bar, not
this number, when looking for unnamed needs).
**Format:** Percentage, 1 dp.

```DAX
Top Category This Period =
CONCATENATEX (
    TOPN ( 1, VALUES ( dim_category[category_en] ), [Messages], DESC ),
    dim_category[category_en]
)
```
**Description:** Highest-volume category in the current selection.
**Format:** text — leave as is.

```DAX
Messages Prev 4 Weeks =
VAR FirstDay = MIN ( dim_date[Date] )
RETURN
    CALCULATE ( [Messages], DATESBETWEEN ( dim_date[Date], FirstDay - 28, FirstDay - 1 ) )
```
**Description:** Message volume in the 28 days before the selected window — the comparison
base.
**Format:** Whole number.

```DAX
Δ Messages vs Prev 4 Weeks =
DIVIDE ( [Messages] - [Messages Prev 4 Weeks], [Messages Prev 4 Weeks] )
```
**Description:** Growth against the previous 4 weeks. Blank when there is no prior window.
**Format:** Percentage, 0 dp.

> The `Δ` is a real character — copy the whole block rather than retyping it. If your keyboard
> fights you, rename it `Delta Messages vs Prev 4 Weeks` and use that name consistently
> everywhere below.

```DAX
Fastest-growing Category =
VAR Growth =
    ADDCOLUMNS (
        VALUES ( dim_category[category_en] ),
        "@growth", [Δ Messages vs Prev 4 Weeks]
    )
VAR Ranked = TOPN ( 1, FILTER ( Growth, NOT ISBLANK ( [@growth] ) ), [@growth], DESC )
RETURN
    CONCATENATEX ( Ranked, dim_category[category_en] )
```
**Description:** Category with the largest 4-week growth. Blank early in a window that has no
comparison base.

### 5.3 Experience (the MEAL survey)

```DAX
MEAL n = COUNTROWS ( fact_meal )
```
**Description:** MEAL survey responses in the selection (69 in the July run — indicative, not
representative).
**Format:** Whole number.

```DAX
MEAL Response Rate = DIVIDE ( [MEAL n], [Users] )
```
**Description:** Responses ÷ users, both under the same filters (7.5% overall). 4 of the 69
respondents are not in the user table, so a city-filtered rate is slightly conservative.
**Format:** Percentage, 1 dp.

```DAX
Mean Usefulness = AVERAGE ( fact_meal[rating_num] )
```
**Description:** Mean 1–5 usefulness rating. Always show alongside `MEAL n`.
**Format:** Decimal, **1 dp**.

```DAX
% Would Recommend =
DIVIDE ( CALCULATE ( [MEAL n], fact_meal[would_recommend] = "Yes" ), [MEAL n] )
```
**Description:** Share of MEAL respondents who would recommend SAMI. The gold layer stores
the answer already translated (`Sí` → `Yes`), so the filter matches the English value.
**Format:** Percentage, 0 dp.

### 5.4 Tone — ⚠️ ranking only, never published

```DAX
Negative Tone Index =
DIVIDE (
    CALCULATE ( [Messages], fact_message[sentiment_label] = "negative" ),
    [Messages]
)
```
**Description:** ⚠️ **Directional only, not a rate.** The tone classifier scores κ = 0.604
against human labels, below the 0.7 quotability gate, so this value may put categories in
order but must never be read as a percentage. Its axis is hidden wherever it is drawn.
**Format:** leave as Decimal — you will never display it.

```DAX
Most Negative Category =
CONCATENATEX (
    TOPN ( 1, VALUES ( dim_category[category_en] ), [Negative Tone Index], DESC ),
    dim_category[category_en]
)
```
**Description:** ⚠️ Category with the highest share of negative-tone messages — a **rank**,
shown without its value. This replaces doc 03's "% Negative tone" KPI
([Appendix A, D1](#d1--the--negative-tone-kpi-cannot-be-published)).

### 5.5 Dynamic text

Doc 03 §2.5: **no number and no date is ever typed by hand into this report.** These measures
generate the subtitles, so they update themselves on refresh.

```DAX
Window Subtitle =
"n = " & FORMAT ( [Users], "#,0" ) & " users · "
    & FORMAT ( MIN ( dim_date[Date] ), "dd MMM yyyy" ) & " – "
    & FORMAT ( MAX ( dim_date[Date] ), "dd MMM yyyy" )
```

```DAX
MEAL Subtitle =
"n = " & FORMAT ( [MEAL n], "#,0" ) & " responses ("
    & FORMAT ( [MEAL Response Rate], "0.0%" ) & " of users) · indicative only"
```

```DAX
Export Date =
"Data exported " &
FORMAT (
    DATEVALUE ( LEFT ( LOOKUPVALUE ( meta_run[value], meta_run[key], "generated_at" ), 10 ) ),
    "dd MMM yyyy"
)
```

```DAX
Data Window =
"Messages from "
    & FORMAT ( DATEVALUE ( LEFT ( LOOKUPVALUE ( meta_run[value], meta_run[key], "ts_min" ), 10 ) ), "dd MMM yyyy" )
    & " to "
    & FORMAT ( DATEVALUE ( LEFT ( LOOKUPVALUE ( meta_run[value], meta_run[key], "ts_max" ), 10 ) ), "dd MMM yyyy" )
```

```DAX
Tone Gate Banner =
IF (
    LOOKUPVALUE ( meta_run[value], meta_run[key], "tone_gate_passed" ) = "False",
    "⚠ Tone is directional only — rank order, levels suppressed (κ = "
        & LOOKUPVALUE ( meta_run[value], meta_run[key], "tone_kappa" ) & " < 0.70)",
    "Tone validated for publication"
)
```
This reads the gate **from the data**, so if a future pipeline run passes κ ≥ 0.7 the banner
rewrites itself with no edit here.

```DAX
Schema Check =
VAR V = LOOKUPVALUE ( meta_run[value], meta_run[key], "schema_version" )
RETURN IF ( V = "3", "Schema v3 ✓", "⚠ Unexpected schema version: " & V )
```
The v2 export migration bumped `schema_version` from `"2"` to `"3"` (new tables
`agg_registration_funnel` / `agg_language`; `dim_user` and `fact_meal` gained columns;
`message_id` became a content hash) — this measure must check `"3"` against a current export,
not `"2"`.

```DAX
Empty State =
IF ( ISBLANK ( [Messages] ), "No data for this selection", "" )
```
Used as a card placed *behind* each visual group, so an over-filtered page says something
instead of showing blank rectangles (doc 03 §5).

**Ctrl+S.** You now have a working model with no report yet — the rest is drawing.

---

## Part 6 — Set up the canvas and the slicer rail

Switch to **Report view** (top icon in the view switcher).

### 6.1 Page size and grid

1. Click an **empty part of the canvas** so no visual is selected.
2. In the **Visualizations pane**, click the **paint roller**. Because nothing is selected, it
   now reads **"Format your report page"**.
3. **Canvas settings → Type: 16:9.** That sets 1280 × 720 pixels — the coordinate system every
   position number in this guide uses.
4. Ribbon → **View → Page view → Fit to page**, so the whole canvas is visible at once.
5. Ribbon → **View →** tick **Gridlines** and tick **Snap to grid**.
6. **Rename the page:** double-click the page tab at the bottom, type
   `1 · Who is SAMI reaching?`, press Enter.

### 6.2 The layout grid — memorise these six numbers

Every visual on every tab uses one of six slots. Position everything with gesture ⑤.

```
 x=0        208            744           1264   1280
 ┌──┬────────┬──────────────┬──────────────┐
 │  │ page title           16 │            │  y=16   h=56
 │S ├────────┬──────┬──────┬──────┐        │
 │L │ KPI 1  │KPI 2 │KPI 3 │KPI 4 │        │  y=88   h=96
 │I ├────────┴──────┴──┬───┴──────┘        │
 │C │                  │                   │
 │E │   VISUAL A       │    VISUAL B       │  y=200  h=250
 │R ├──────────────────┼───────────────────┤
 │  │   VISUAL C       │    VISUAL D       │  y=466  h=238
 └──┴──────────────────┴───────────────────┘ y=704
```

| Slot | X | Y | Width | Height |
|---|---|---|---|---|
| Slicer rail (whole left column) | 16 | 16 | 176 | 688 |
| Page title | 208 | 16 | 700 | 56 |
| KPI card 1 | 208 | 88 | 252 | 96 |
| KPI card 2 | 476 | 88 | 252 | 96 |
| KPI card 3 | 744 | 88 | 252 | 96 |
| KPI card 4 | 1012 | 88 | 252 | 96 |
| Visual A (top-left) | 208 | 200 | 520 | 250 |
| Visual B (top-right) | 744 | 200 | 520 | 250 |
| Visual C (bottom-left) | 208 | 466 | 520 | 238 |
| Visual D (bottom-right) | 744 | 466 | 520 | 238 |

Every later step just says "**Position:** Visual A" and you look it up here.

### 6.3 Build the slicer rail

Three objects down the left-hand strip.

**Date slicer**

1. Gesture ① — click empty canvas → **Slicer** icon in the Visualizations pane (a funnel above
   a list).
2. Gesture ② — drag `dim_date[Date]` into the **Field** well.
3. **Format → Slicer settings → Options → Style: `Between`.** You get two date boxes and a
   draggable range bar.
4. **Format → General → Title → On**, text: `Date range`.
5. Gesture ⑤ — **X 16, Y 16, W 176, H 120**.

**City slicer**

1. Empty canvas → **Slicer**.
2. Drag **`dim_city[city_canon]`** into the Field well. Use `dim_city`, **not** `dim_user`, so
   that the slicer and the map on Tab 1 share one source of truth.
3. **Format → Slicer settings → Options → Style: `Vertical list`.**
4. **Format → Slicer settings → Selection →** turn **Multi-select with Ctrl** **off**, so a
   plain click adds to the selection.
5. Title: `City`.
6. **X 16, Y 152, W 176, H 300.**

**Placeholder for the window subtitle**

1. Ribbon → **Insert → Text box**. Leave it empty for now — you'll bind the `Window Subtitle`
   measure to it in Part 11.2.
2. **X 16, Y 470, W 176, H 80.**

**Do not add a category slicer to Tab 1.** Category is a Tab 2 and Tab 3 filter only
(doc 03 §4).

### 6.4 Create the other two pages

1. Right-click the page tab at the bottom → **Duplicate page**. Do this **twice**.
2. Rename the copies (double-click each tab): `2 · What do they need?` and `3 · Is it working?`
3. On each copy, **delete the page title text box** but **keep both slicers** — that's the
   point of duplicating.
4. On pages 2 and 3 only, add a third slicer: empty canvas → **Slicer** → field
   `dim_category[category_en]` → Style **Vertical list** → Title `Category` →
   **X 16, Y 470, W 176, H 234**. (This takes the placeholder's slot on those pages; delete
   the placeholder text box there.)

### 6.5 Sync the slicers across pages

So that one date choice follows the reader through the whole story.

1. Ribbon → **View → Sync slicers.** A new pane opens on the right with a row per page and two
   checkbox columns: **Sync** and **Visible**.
2. Go to page 1, click the **date slicer**. In the Sync slicers pane, tick **Sync** for all
   three pages and **Visible** for all three pages.
3. Click the **city slicer**, do the same.
4. Go to page 2, click the **category slicer**. Tick **Sync** and **Visible** for pages 2 and
   3 only — leave page 1 unticked in both columns.

**✅ How to know it worked:** set the date slicer to a narrow range on page 1, switch to page
3, and see the same range already selected there.

**Ctrl+S.**

---

## Part 7 — Tab 1 — Who is SAMI reaching?

Go to page `1 · Who is SAMI reaching?`.

### 7.1 Page title

Ribbon → **Insert → Text box** → type **Who is SAMI reaching?** → select the text → set size
**20**. **Position:** Page title slot (208, 16, 700, 56).

The tab title is a question; the visuals answer it. That's doc 03 §5's "5-second rule".

### 7.2 The KPI band — four cards across the top

**For each of the four:**

1. Empty canvas → **Card** icon in the Visualizations pane (it looks like **123**).
2. Drag the measure into the **Fields** well.
3. **Format → Callout value → Font size: 32.**
4. **Format → Category label → On** — this shows the label under the number.
5. **Position** from the KPI slots table.

| # | Measure | Label shown | Position |
|---|---|---|---|
| 1 | `Users` | Users reached | 208, 88 |
| 2 | `Avg Session Time` | Avg session (min) | 476, 88 |
| 3 | `Mean Usefulness` | Usefulness rating | 744, 88 |
| 4 | `MEAL n` | Surveys submitted | 1012, 88 |

> ### The four KPIs, and why they're in this order (checkpoint 2026-07-28)
>
> The band tells one sentence left to right: **how many people → how long they stayed → was it
> useful → how many told us.** Don't reorder it and don't swap in a different metric because
> a slot looks empty.
>
> - **`Users`** — active users. There is exactly one conversation per user, so a separate
>   "conversations" KPI would be the same number twice; it was cut for that reason.
> - **`Avg Session Time`** — see the two warnings in Part 5.1. This slot went through three
>   candidates before landing here.
> - **`Mean Usefulness`** — the 1–5 mean. It gets **two** visuals: this number, plus a breakdown
>   of the responses elsewhere on the page. Francisco asked for both explicitly — one says *how
>   good*, the other says *how spread out*. The breakdown keeps the **label** categories
>   (`Muy útil` → `Very useful`, …), not the numeric 1–5 scale; that matches the notebook and
>   avoids implying the scale is an interval measure.
> - **`MEAL n`** — surveys submitted.
>
> **Rejected: average messages per user.** The funnel already answers it and almost no user
> sends more than two messages, so the card would have read "2" forever. Don't reinstate it.

To change the label text under the number: in the **Build** pane, double-click the field name
inside the *Fields* well and type the label.

> ### ⚠️ Reversed at the 2026-07-27 review: leave the KPI cards CONNECTED
>
> An earlier version of this guide told you to set every other visual's interaction to
> **⊘ None** for each card, so the headline numbers never moved. Francisco reviewed that
> behaviour live — clicked the Medellín bubble on the map, saw every chart update while the
> four cards sat frozen — and rejected it. **That is the whole point of the tool**: click a
> city, and the KPI band tells you that city's story.
>
> So: **do nothing here.** Leave the default interactions in place. The cards respond to the
> slicer rail *and* to clicks on any chart.
>
> If you already followed the old instruction, undo it: select each card → ribbon →
> **Format → Edit interactions** → on every other visual click the **▣ (Filter)** icon to
> restore it → click **Edit interactions** again to leave the mode. Check it worked by clicking
> a map bubble: all four numbers must change.
>
> The one thing that stays fixed: the cards must show the **same** measure regardless of which
> chart is highlighted — don't "helpfully" swap a card's measure per selection.

### 7.3 Visual A — Map: users by city

**What it answers:** where is SAMI reaching people, and where isn't it?
**Position:** Visual A (208, 200, 520, 250).

**Build**

1. Empty canvas → **Map** visual (the **globe**). Not *Filled map*, not *ArcGIS Maps*.
2. Drag `dim_city[lat]` into **Latitude**. Then gesture ③: field ▾ → **Don't summarize**.
3. Drag `dim_city[lon]` into **Longitude** → ▾ → **Don't summarize**.
4. Drag the measure `Users` into **Bubble size**.
5. Leave **Legend** empty.
6. Drag `dim_city[city_canon]`, `Users` and `Messages` into **Tooltips**.

> Latitude and longitude **must** be set to *Don't summarize*. If you skip this, Power BI sums
> all 13 latitudes and plots one bubble somewhere in the Arctic.

**Format** — revised at the 2026-07-27 checkpoint

- **Map settings → Style: Grayscale.** (Dark was tried and rejected — it fought the rest of
  the canvas. Grayscale is the decision.)
- **Map settings → Auto zoom: On.** The map must open already centred on the data, not on the
  whole hemisphere.
- **Map settings → Controls → Lasso select: Off**, **Zoom buttons: On but reduced** — they
  render huge at default size. The only controls a reader needs are `+` and `−`.
- **Bubbles → Size: 18**, raised until the default view looks *full*. A sparse map reads as
  "this project has no reach", which is a presentation artifact, not a finding.
- **Data colors →** teal `#009ba4`.
- **General → Title:** `Users by city`. Plain, not poetic — "Where SAMI reaches and where it
  doesn't" was cut at the checkpoint, along with every other editorialising chart title.
- **Tooltip:** city name + `Users`. **Check you have not bound `Users` twice** — dragging both
  the measure and a second copy is easy to do and prints the same number under two labels.
  Do **not** put `lat`/`lon` in the tooltip.

**Footnote:** Insert → Text box directly under the map, 9 pt grey: "Users whose city is 'Other'
(unspecified) are not mapped."

#### 🔵 Putting the number *on* the bubble

This came up at the checkpoint and there is no toggle for it, so here is the whole picture.

**What does not work.** The built-in **Map** visual has no data-label setting for bubbles.
`Category labels` looks like the answer, but it prints whatever text field sits in the
**Location** well — during the review it printed the *category* names, which is why it got
switched back off. There is no way to make it print a measure.

**The workaround: make the label a column, then use it as Location.** `Category labels` will
happily print a string like `Medellín · 214`, so build that string as a **DAX calculated
column** (Modeling ribbon → *New column*, with `dim_city` selected):

```DAX
map_label =
VAR n = COUNTROWS ( RELATEDTABLE ( dim_user ) )
RETURN
    dim_city[city_canon] & " · " & FORMAT ( n + 0, "#,0" )
```

`RELATEDTABLE` follows the `dim_city[city_canon] → dim_user[city_canon]` relationship you drew
in Part 4.1, so it counts the users of *this* row's city. The `n + 0` turns the blank into a
`0` for cities with no users, which would otherwise render as a bare `Leticia ·` with nothing
after it.

Then drag `dim_city[map_label]` into **Location**, and turn **Format → Category labels → On**,
font size 9, colour `#4a4a4a`.

> **The catch, and it is a real one: a calculated column is static.** It is computed once at
> refresh, so these numbers **do not change when a reader clicks a slicer** — filter to one
> city and every remaining bubble still shows its all-time count. The bubble *sizes* update
> correctly; only the printed text lies. That is why the tooltip stayed the default answer at
> the checkpoint. Use `map_label` only if the numbers must be readable in a static screenshot
> or a printed page, and if you do, put "counts are unfiltered totals" in the footnote.

**If you want slicer-accurate numbers on screen**, the honest option is a companion visual, not
a map label: a small horizontal bar chart of `Users` by `city_canon` beside the map, sorted
descending. It responds to every filter, and the map keeps doing the one job a map is good at —
showing *where*.

**✅ How to know it worked:** 13 teal bubbles over Colombia, biggest on the largest cities, the
frame already centred on the country when the page opens. Hovering one shows the city name and
the user count **once**.

Coordinates come from `dim_city` — **Power BI never geocodes by name here** (doc 03 §8). The
map needs an internet connection for the background tiles only; the data is local.

> **Colombian department shapefiles were considered and dropped** (checkpoint 2026-07-27).
> The data is per-city, so a department choropleth would paint huge polygons from a handful of
> city points and imply a coverage the data does not have. An interactive point map beats a
> shapefile here. `dim_city[department]` still ships if you ever need to group by department in
> a *table* — just not on the map. Don't reopen this.

### 7.4 Visual B — Weekly active users

**What it answers:** is reach growing, and when did it spike?
**Position:** Visual B (744, 200, 520, 250).

**Build**

1. Empty canvas → **Line chart**.
2. Drag `dim_date[Week start]` into **X-axis**. Gesture ③: field ▾ → **Don't summarize**.
3. Drag `Active Users` into **Y-axis**.

> **Never use the date hierarchy.** If the X-axis well shows *Date Hierarchy* with Year /
> Quarter / Month / Day nested inside, click its ▾ and pick the plain field name instead.
> The hierarchy adds drill-down arrows this dashboard deliberately doesn't have.

**Format**

- **Lines → Stroke width: 3**, colour teal `#009ba4`.
- **Markers → On.**
- **X axis → Type: Categorical** — so weeks with no data show as gaps rather than being
  interpolated over. Honesty over smoothness.

**Dynamic annotation.** Don't type the peak date — it would be wrong after the next refresh.
Add this measure (Part 5 method) and then set it as the visual's subtitle via
**Format → General → Title → Subtitle → `fx` → Format style: Field value →
`Peak Week Note`**:

```DAX
Peak Week Note =
VAR ByWeek = ADDCOLUMNS ( VALUES ( dim_date[Week start] ), "@u", [Active Users] )
VAR Top1 = TOPN ( 1, ByWeek, [@u], DESC )
RETURN
    "Peak: " & FORMAT ( MAXX ( Top1, [@u] ), "#,0" ) & " active users in the week of "
        & FORMAT ( MAXX ( Top1, dim_date[Week start] ), "dd MMM yyyy" )
```

**✅ How to know it worked:** the subtitle reads something like "Peak: 84 active users in the
week of 12 May 2026", and it changes when you move the date slicer.

> ### 📈 Add messages on a secondary axis (checkpoint 2026-07-27)
>
> Tab 2's old eight-series "messages over time" chart was deleted; **this** chart absorbs it.
> One line for people, one for volume, on one time axis.
>
> 1. Change the visual type from *Line chart* to **Line and clustered column chart**, or keep
>    the line chart and use **Line chart** with two values — either works; the field well you
>    need is **Secondary Y axis**.
> 2. Drag the `Messages` measure into **Secondary Y axis**.
> 3. Colour that line **red**, keeping `Active Users` teal. Two units on one frame need two
>    unmistakably different colours, and red is the accent that survives at 1 px.
> 4. **Confirm the category filter reaches it.** Click a category in the slicer rail: the red
>    line must move. `Messages` counts `fact_message`, which relates to `dim_category` via
>    `dominant_category`, so it should — but check, because this is the exact thing the old
>    chart was doing per-series and the whole point is not to lose it.
>
> **Why this beats the chart it replaces:** eight coloured series on one time axis is
> unreadable. One line plus a category *filter* reaches every one of those eight views, one at
> a time, legibly — and gives back a whole visual slot on Tab 2.
>
> Label both axes, and keep the left axis starting at zero. A dual axis is already asking the
> reader to do work; don't also make them check the baseline.

### 7.5 Visual C — Profile: age × gender

One compact visual instead of four separate demographic charts (doc 03 §4).
**Position:** Visual C (208, 466, 520, 238).

**Build**

1. Empty canvas → **Clustered bar chart** (horizontal bars).
2. **Y-axis:** `dim_user[age_range]`
3. **X-axis:** `Users`
4. **Legend:** `dim_user[gender_clean]`
5. **Filter out the implausible ages:** with the visual selected, open the **Filters pane**
   and drag `dim_user[age_flag]` into the box labelled **"Filters on this visual"**. In the
   list of values that appears, tick **`ok`** only.

**Format**

- **Data colors:** Woman `#009ba4`, Man `#671e42`, everything else grey `#b7b7b7`.
  (Each legend value gets its own colour picker under this setting.)

The legend is a closed English set — `Woman`, `Man`, `Transgender`, `LGBTQ+`,
`Prefer not to say`, `Other` — canonicalized in the gold layer, not in Power BI. The
self-reported variants (`transgenero`, `Soy una mujer trans`) are merged into
**Transgender**; `lgtbQ+` and `Gay` into **LGBTQ+**. Each is 1–2 users, so they read as
hairlines next to Woman/Man — that is honest, don't inflate them.

**Footnote text box:** "35 records with implausible sub-18 ages are excluded; self-reported."

### 7.6 Visual D — Settlement: time in city

The "settled, not in transit" evidence — the finding that changes what MMC should offer.
**Position:** Visual D (744, 466, 520, 238).

**Build**

1. Empty canvas → **Clustered bar chart**.
2. **Y-axis:** `dim_user[city_duration_canon]`
3. **X-axis:** `Users`
4. Gesture ⑥: **… → Sort axis → city_duration_canon → Sort ascending.** Because of the
   sort-by column you set in Part 4.3, this gives real duration order, not alphabetical.

**Format**

- **Data colors → `fx`** (gesture ⑦) → **Format style: Gradient** → **What field should we
  base this on?** `dim_user[city_duration_order]` → **Minimum** colour `#eef6f5`, **Maximum**
  colour `#009ba4`. Longer settled = darker.
- **General → Title:** `Most users have been in their city for months, not days`.

**✅ How to know it worked:** bars run from "less than a month" at the top to the longest
duration at the bottom, getting darker as they go down.

### 7.7 The editorial tile

This is the **only** hand-written content in the entire report (doc 03 §2.5).

Insert → Text box, placed in the remaining space at the bottom-right, headed **"This period in
3 bullets"**, with three hand-written lines of interpretation. Underneath, in small grey type:
"Editorial summary — written by hand, updated each cycle."

Labelling it as editorial is what makes it acceptable: readers can tell which text is
generated and which is a human's judgement.

**Ctrl+S.**

---

## Part 8 — Tab 2 — What do they need?

Go to page `2 · What do they need?`. Add the page title text box: **What do they need?**
(Insert → Text box, 20 pt, position 208/16/700/56.)

### 8.1 KPI band

Same method as 7.2 — four **Card** visuals in the four KPI slots.

| # | Measure | Label | Position |
|---|---|---|---|
| 1 | `Messages` | Messages | 208, 88 |
| 2 | `% Legal Documentation` | Legal & documentation | 476, 88 |
| 3 | `Top Category This Period` | Top category | 744, 88 |
| 4 | `Fastest-growing Category` | Fastest-growing | 1012, 88 |

Cards 3 and 4 show **text**, not numbers. Set their **Callout value → Font size: 18** — a
category name like "Humanitarian assistance" will not fit at 32.

**Leave the interactions alone**, exactly as in 7.2 — the old "set Edit interactions → None"
instruction is withdrawn on every tab.

> ### 📐 Tab 2 was restructured at the 2026-07-27 review — read before building 8.2–8.5
>
> The page now answers **two** questions in one screen: *what are they asking for* and *is the
> service any good*. Four visuals, laid out 2×2:
>
> | | Left column | Right column |
> |---|---|---|
> | **Top** | Bar chart — **institutions**, in green | Donut — **usefulness rating** |
> | **Bottom** | Bar chart — **procedures / trámites**, in red | **Engagement** — vertical bars *or* a treemap |
>
> The two bar charts are the *same analysis run on two fields*, which is why they are colour-
> paired (one green, one red) and stacked in the same column — the pairing is the point.
> Build one, copy it, change the field.
>
> Four changes from what this guide previously described:
>
> 1. **The messages-over-time chart is deleted from this page.** It had eight category series
>    on one time axis and was unreadable. Its content moved to Tab 1, as a red line on a
>    secondary Y axis of the Active Users chart — see the note at the end of Part 7.4. Deleting
>    it is what frees the fourth slot here.
> 2. **City comes out of the matrix table and becomes a global filter.** The category × city
>    matrix (old 8.3) is retired. Cross-tabulating in the table meant the page could only be
>    read one cell at a time; as a filter, city re-cuts all four visuals at once.
> 3. **Category likewise becomes a filter, not an axis**, on the institutions and procedures
>    charts. Three filters over one chart reach three levels of analysis — that is the leverage
>    Francisco wanted, rather than three near-identical bar charts.
> 4. **The donut should cross usefulness rating with `would_recommend`** as a two-ring donut if
>    Power BI will build one from `fact_meal` (outer ring rating, inner ring recommend, colour
>    keyed). If a clean two-ring version fights you, ship the single ring — the rating breakdown
>    is the part that must be there.
>
> **The engagement visual is an open A/B:** build it as vertical bars, build it as a treemap,
> look at both, keep the one that reads better. Few enough categories that either works.

### 8.2 Visual A — Category mix

**Position:** Visual A (208, 200, 520, 250).

**Build**

1. Empty canvas → **Clustered bar chart**.
2. **Y-axis:** `dim_category[category_en]`
3. **X-axis:** `Messages`
4. **… → Sort axis → Messages → Sort descending.**

**Format — the colour binding. This is the step that keeps the report in sync with the
pipeline.**

1. **Format → Data colors →** click the small **`fx`** button (gesture ⑦).
2. **Format style: `Field value`.**
3. **What field should we base this on?** → `dim_category[color_hex]`.
4. **OK.**

Category hues now come from `theme.py` via `dim_category`, so changing the palette in Python
flows into the report on refresh — no hand-picked colours to drift out of date (doc 03 §5).

> `color_hex` is hidden (Part 4.4), but it still appears in the `fx` field picker. If it
> doesn't, right-click in the Data pane → **View hidden**.

**Repeat this `fx` binding on every visual that draws categories: 8.3, 8.4 and 9.5.**

### 8.3 Visual B — Category × city matrix

The localization view — what each city actually asks about — with small-sample suppression.
**Position:** Visual B (744, 200, 520, 250).

First create this measure (Part 5 method):

```DAX
Category Share in City =
VAR CityMessages = CALCULATE ( [Messages], ALL ( dim_category ) )
RETURN
    IF (
        CityMessages < 20,
        "·",
        FORMAT ( DIVIDE ( [Messages], CityMessages ), "0%" )
    )
```
**Description:** Share of a city's messages falling in this category. Cities with fewer than
20 messages show "·" — too few to read as a share.

**Build**

1. Empty canvas → **Matrix** visual (a grid icon).
2. **Rows:** `dim_city[city_canon]`
3. **Columns:** `dim_category[category_en]`
4. **Values:** the `Category Share in City` measure — **not** a raw count.

**Format**

- **Grid → Options → Row padding: 4.**
- **Values → Text size: 10.**

**Footnote text box:** "· = fewer than 20 messages in that city; share not shown."

**✅ How to know it worked:** find the **Cartagena** row (1 message). Every cell in it must be
a dot. If you see percentages there, the measure didn't take — check it's in the *Values* well
and not a count.

### 8.4 Visual C — Weekly trend by category

**Position:** Visual C (208, 466, 520, 238).

**Build**

1. Empty canvas → **Line chart**.
2. **X-axis:** `dim_date[Week start]` → ▾ → **Don't summarize**.
3. **Y-axis:** `Messages`
4. **Legend:** `dim_category[category_en]`
5. **Keep it readable — top 4 categories only:** with the visual selected, open the **Filters
   pane**, drag `dim_category[category_en]` into **Filters on this visual**, set **Filter
   type: Top N**, **Show items: Top `4`**, **By value:** drag in the `Messages` measure →
   **Apply filter**.

**Format**

- **Data colors → `fx` → Field value → `dim_category[color_hex]`** (as in 8.2).
- **Markers → On** (doc 03 §4 wants the raw weekly points visible, not a smoothed
  impression).

This visual is built from `fact_message` + `dim_date`, **not** from the pre-computed
`agg_weekly_category` table, precisely so that it *does* respond to the city slicer.
`agg_weekly_category` stays in the model as a parity reference
([Appendix A, D3](#d3--the-standalone-agg-tables-ignore-the-slicers)).

### 8.5 Visual D — Top procedures & institutions

Two datasets in one visual slot, so Tab 2 stays at four visuals.
**Position:** Visual D (744, 466, 520, 200) — plus a small slicer above it.

**Build**

1. **The toggle:** empty canvas → **Slicer** → field `agg_entities_by_kind[kind]` →
   **Format → Slicer settings → Options → Style: `Tile`** →
   **Format → Slicer settings → Selection → Single select: On**.
   **Position: 744, 466, 520, 34.** Click `institution` so it starts on a value.
2. **The bar chart:** empty canvas → **Clustered bar chart**.
   - **Y-axis:** `agg_entities_by_kind[entity]`
   - **X-axis:** `agg_entities_by_kind[n]`
   - **… → Sort axis → n → Sort descending.**
   - **Filters on this visual:** `entity` → **Top N → Top 10 by `n`** → Apply.
   - **Format → Data colors:** single teal `#009ba4`.
   - **Position: 744, 508, 520, 196.**

**Dynamic title.** Create this measure, then **Format → General → Title → Title text → `fx` →
Field value → `Entity Chart Title`**:

```DAX
Entity Chart Title =
"Most-mentioned " & SELECTEDVALUE ( agg_entities_by_kind[kind], "entities" ) & "s"
```

**⚠️ This slicer must not filter anything else on the page.** Select the tile slicer → ribbon
**Format → Edit interactions** → set **⊘ None** on every other visual on the page → turn
Edit interactions off.

**Footnote text box:** "Whole-period counts from entity extraction; not filtered by the date
or city slicers."

**Ctrl+S.**

---

## Part 9 — Tab 3 — Is it working?

Go to page `3 · Is it working?`. This is the tab with the most rules attached, because it's
where tone lives.

**Page title:** Insert → Text box, **Is it working?**, 20 pt, position 208/16/**520**/56.

**⚠️ The tone gate banner — build this first, it governs the whole page.**

1. Empty canvas → **Card** → drag the `Tone Gate Banner` measure into **Fields**.
2. **Format → Callout value → Font size: 11**, colour wine `#671e42`.
3. **Position: 744, 16, 520, 56** — beside the title, above everything else.

Every tone-derived visual on this tab sits underneath it.

### 9.1 KPI band

Four **Card** visuals, method as in 7.2.

| # | Measure | Label | Position |
|---|---|---|---|
| 1 | `Mean Usefulness` | Mean usefulness (1–5) | 208, 88 |
| 2 | `% Would Recommend` | Would recommend | 476, 88 |
| 3 | `% Repeat Askers` | Repeat askers | 744, 88 |
| 4 | `Most Negative Category` | Most negative tone (rank) ⚠️ | 1012, 88 |

- **Card 1 must show its sample size.** Select it →
  **Format → General → Title → Subtitle → `fx` → Field value → `MEAL Subtitle`**. A mean of 69
  responses shown without its n is a misleading number.
- **Card 4** replaces doc 03's `% Negative tone` KPI. It names a category and shows **no
  number** ([Appendix A, D1](#d1--the--negative-tone-kpi-cannot-be-published)).

Set **Edit interactions → None** for all four.

### 9.2 Visual A — The funnel

Horizontal bars with conversion labels, **not** the native Funnel visual (doc 03 §8 — its
proportions mislead).
**Position:** Visual A (208, 200, 520, 250).

**Build**

1. Empty canvas → **Clustered bar chart**.
2. **Y-axis:** `agg_funnel[stage]` (already in the right order thanks to Part 4.3).
3. **X-axis:** `agg_funnel[n]`, aggregation **Sum**.
4. **… → Sort axis → stage → Sort ascending.**

**Format**

- **Data labels → On.**
- **Data colors → `fx` → Format style: Gradient**, based on `agg_funnel[stage_order]`,
  Minimum `#009ba4` → Maximum `#eef6f5` (the funnel narrows and lightens).
- Add the conversion rate: drag `agg_funnel[conversion_from_prev]` into the **Tooltips** well
  and set its format to Percentage 0 dp. *Or*, if you want it always visible, place a small
  **Table** visual beside the bars with `stage` and `conversion_from_prev`.

**Subtitle — this one is typed and static, which is allowed because it describes the table,
not a number:** "Whole-period; not affected by the slicers. MEAL respondents are a separate
cohort."

### 9.3 Visual B — The priority matrix

The single most important visual in the product (doc 03 §4). It answers "which need is big but
badly served?"
**Position:** Visual B (744, 200, 520, 250).

First create the two median measures:

```DAX
Median Priority Volume = MEDIANX ( ALL ( agg_priority_matrix ), agg_priority_matrix[messages] )
```
```DAX
Median Priority Unmet  = MEDIANX ( ALL ( agg_priority_matrix ), agg_priority_matrix[unmet_need] )
```

**Build**

1. Empty canvas → **Scatter chart**.
2. **X-axis:** `agg_priority_matrix[messages]`
3. **Y-axis:** `agg_priority_matrix[unmet_need]`
4. **Size:** `agg_priority_matrix[users]`
5. **Values** (called *Details* in some versions): `agg_priority_matrix[category]`. **This is
   the well that makes each category its own bubble** — without it you get one single dot.

**Format**

- **Category labels → On** — direct labels on the bubbles, so no legend-hunting.
- **Data colors:** this table has no relationship to `dim_category`, so `fx` binding isn't
  available here. Set each of the 7 bubbles by hand from the
  [category colour table](#114-category-colours-for-the-manual-bindings).

**The quadrant lines** (this is the one use of the third pane):

1. With the scatter selected, click the **Analytics** tab in the Visualizations pane (the
   **magnifying glass**).
2. **X-Axis Constant Line → + Add.** Click the **`fx`** next to *Value* → **Format style:
   Field value** → `Median Priority Volume`. Set **Line style: Dashed**, colour `#b7b7b7`.
3. **Y-Axis Constant Line → + Add** → same, with `Median Priority Unmet`.

**Quadrant captions:** four Insert → Text boxes, 9 pt grey, one in each corner of the chart:
"Big and badly served — act here" · "Big and well served — protect" · "Small but badly served —
watch" · "Small and well served".

**⚠️ Required caption under the visual** (text box): "The vertical axis is a composite priority
**ranking** (volume, repeat rate, rating and tone, z-scored) — not a rate. Tone is one
directional input; κ = 0.604."

### 9.4 Visual C — Coverage gaps

**Position:** Visual C (208, 466, 520, 238).

**Build**

1. Empty canvas → **Clustered bar chart**.
2. **Y-axis:** `nlp_emergent_themes[theme]`
3. **X-axis:** `nlp_emergent_themes[n_users]`, aggregation **Sum**.
4. **… → Sort axis → n_users → Sort descending.**
5. **Format → Data colors:** wine `#671e42`.

**Footnote text box:** "Keyword-probe counts — a **floor**, not a rate: they count messages
that matched a probe, so the true number is higher. Only 0.9% of messages fall outside the
official taxonomy entirely."

Also place a small **Card** with the `% Outside Official Taxonomy` measure next to it, so both
readings of "unmet need" sit together and neither can be mistaken for the other.

### 9.5 Visual D — Negative tone by category ⚠️

**This is the most rule-bound visual in the report. Every suppression step is mandatory.**
**Position:** Visual D (744, 466, 520, 238).

**Build**

1. Empty canvas → **Clustered bar chart**.
2. **Y-axis:** `dim_category[category_en]`
3. **X-axis:** `Negative Tone Index`
4. **… → Sort axis → Negative Tone Index → Sort descending.**

**Format — the four suppressions**

- **X axis → Off.** ⚠️ Mandatory. With no axis, no percentage can be read off the chart. That
  *is* the tone gate requirement.
- **Data labels → Off.** ⚠️ Mandatory, same reason.
- **Tooltips →** remove `Negative Tone Index` from the tooltip fields, so hovering reveals no
  number either.
- **Data colors:** single madera wine `#671e42`. ⚠️ **Never red, never a red-green scale**
  (doc 03 §5).
- **General → Title:** `Which needs carry the most distress (rank order)`.

**✅ How to know it worked:** you can see which category is worst and roughly how the others
rank, and **there is no number anywhere on or around the chart**. If you can read a value off
it in any way, a suppression is missing.

**Ctrl+S.**

---

## Part 10 — The hidden About page

Every claim on the three tabs is qualified here. This page is what makes the dashboard
defensible.

### 10.1 Build the page

1. Click the **+** next to the page tabs → rename the new page `About the data`.
2. Place, roughly top to bottom (exact positions don't matter here; readability does):

**Cards** (six of them, in a row or two): `Export Date`, `Data Window`, `Schema Check`,
`Users`, `Messages`, `MEAL n`.

**A Table visual from `meta_run`:** columns `key` and `value`. This is the full run identity
card — model names, κ, chosen k, stability ARI, gate flags.

**A Table visual from `parity_check`:** columns `metric`, `exported_value`,
`reconciliation_value`, `match`. Then conditionally colour the `match` column:

1. Select the table → **Format → Cell elements**.
2. In the **Series** dropdown at the top, pick `match`.
3. **Background color → On →** click the **`fx`** that appears.
4. **Format style: Rules.** Add: value `True` → `#eef6f5`; value `False` → `#671e42`.

**This is the parity table doc 03 §2.6 asks you to eyeball after every refresh.**

**Text box — limitations, in plain language:**

- "MEAL responses: 69 of 917 users (7.5%) — indicative, never representative."
- "Tone/sentiment: model-vs-human agreement κ = 0.604, below the 0.7 bar. Tone is shown as
  rank order only; no tone percentage is published anywhere in this report."
- "Age, gender, destination and duration are self-reported; 35 records with implausible
  sub-18 ages are excluded from the profile chart."
- "Coverage-gap counts are keyword-probe floors, not rates."
- "`Users` responds to city and profile filters but **not** to the date slicer; use
  `Active Users` for date-bounded reach."

**Text box — metric glossary:** one line per measure, copied from the Descriptions you wrote
in Part 5. (This is why they weren't optional.)

**Text box — the refresh runbook:** the three steps from Part 12.2.

**Text box — how to move the data:** "The report reads only the CSVs in the folder named by
the Power Query parameter `DataFolder`. To move the data: Home → Transform data → Manage
Parameters → change `DataFolder` → Close & Apply → Refresh. No other edit is ever needed."

3. **Hide the page:** right-click its page tab → **Hide page**. It stays reachable by button,
   not by tab (doc 03 §4).

### 10.2 The ⓘ buttons

On **each** of the three visible tabs, top-right corner:

1. Ribbon → **Insert → Buttons** (▾) → **Information**.
2. **Format → Action → On** → **Type: `Page navigation`** → **Destination: `About the data`**.
3. **Format → Style → Icon →** colour `#3a3a5c`, size 20.
4. **Position: 1244, 16, 20, 20.**
5. **Copy it (Ctrl+C) and paste (Ctrl+V) onto the other two tabs** so the position is
   pixel-identical.

On the About page itself, add a **Back** button: **Insert → Buttons → Back**, top-left.

> **In Power BI Desktop, buttons need Ctrl+click to fire.** In a published report, or in
> Desktop's Reading view, a plain click works. This confuses everyone once.

**Ctrl+S.**

---

## Part 11 — Interactions, dynamic titles, accessibility

### 11.1 One interaction pattern, everywhere (doc 03 §5)

The whole report obeys exactly three behaviours: **slicers filter · clicking a bar
cross-highlights · ⓘ navigates.** Nothing else.

- **Confirm no drill-down exists.** Select each chart and look at its header icons: there
  should be no ⤓ / ⌄ drill arrows. Because you used `Week start` rather than the date
  hierarchy, there shouldn't be — if one appears, you have a hierarchy in a well; replace it
  with the plain field.
- **No drill-through pages** other than About.
- **Re-confirm the KPI cards ignore cross-highlighting** on all three tabs (the Edit
  interactions step from 7.2). This is easy to lose when you copy a card between pages.

### 11.2 Dynamic titles and subtitles

Doc 03 §2.5: every subtitle carrying an **n**, a **window** or a **date** must come from a
measure, never typed.

For each visual: **Format → General → Title → Subtitle → `fx` → Format style: Field value** →
pick `Window Subtitle` (Tabs 1–2) or `MEAL Subtitle` (the MEAL visuals on Tab 3).

Also bind the empty text box in the Tab 1 slicer rail (from 6.3) — actually, a text box can't
take an `fx` binding, so **replace it with a Card** holding `Window Subtitle`, callout font 10.

**Then prove there are no typed numbers left:** ribbon → **View → Selection pane**. It lists
every object on the page. Click through all of them, on all four pages, and confirm no text
box contains a number or a date — except the editorial bullets tile on Tab 1.

### 11.3 Accessibility

- **Alt text on every visual.** Select it → **Format → General → Alt text** → write one
  sentence describing what it shows. Required on all 12 visuals and all 12 KPI cards.
- **Tab order.** **View → Selection pane →** click the **Tab order** tab at its top. Reorder
  each page with the arrow buttons so it runs: page title → KPI cards → visuals left-to-right,
  top-to-bottom → slicers last.
- **Contrast.** The theme's ink `#000031` on white is about 17:1. Grey `#b7b7b7` is for
  decoration only — never for text that carries meaning, since it fails the 4.5:1 minimum on
  white.
- **Mobile layout, Tab 1 only** (doc 03 §5): **View → Mobile layout.** A phone-shaped canvas
  appears with all the page's visuals listed beside it. Drag in the four KPI cards and the map,
  stack them vertically, then **View → Desktop layout** to return.

### 11.4 Category colours (for the manual bindings)

| Category | Hex |
|---|---|
| Legal & documentation | `#009ba4` |
| Humanitarian assistance | `#671e42` |
| Protection | `#62c8ce` |
| Employment | `#a3557a` |
| Finding organizations | `#000031` |
| Journey information | `#c78fa4` |
| Services | `#a6dfe3` |
| Unclassified | `#b7b7b7` |

**Only use this table where an `fx` binding is impossible** (the priority matrix, 9.3).
Everywhere a relationship to `dim_category` exists, bind via **`fx` → Field value →
`color_hex`** instead of typing hexes — that's what keeps the report in sync with the pipeline.

---

## Part 12 — Save, refresh runbook, acceptance tests

### 12.1 Save

**File → Save as** → `mmc_dashboard.pbix` in the repo root.

The `.pbix` file holds the report layout *and* a cached copy of the data, which is why it's
about 3 MB and why it is git-ignored.

### 12.2 The refresh runbook (this goes on the About page)

1. Copy the new export workbooks into `data_&_docs/`.
2. Run the pipeline:
   ```powershell
   .venv\Scripts\python.exe run_pipeline.py
   ```
   **It exits with an error if the parity checks fail. If that happens, stop — do not
   refresh.**
3. Open `mmc_dashboard.pbix` → ribbon **Home → Refresh** → wait → go to the About page and
   check that the parity table is all `True` and `Schema Check` reads "Schema v2 ✓".

Nothing is rebuilt, retyped or re-styled. **If step 3 ever requires an edit inside Power BI,
the dashboard is not finished.**

### 12.3 Acceptance checklist (doc 03 §7)

**Reproducibility — these are release blockers**

- [ ] Refresh against a *second* export (the May snapshot) end-to-end, with zero manual edits.
- [ ] The About-page parity table matches the live measures for every KPI.
- [ ] Filter to one city, then reconcile `Users` and `Messages` against Python:
  ```powershell
  .venv\Scripts\python.exe -c "import pandas as pd; u=pd.read_csv('exports/dim_user.csv'); m=pd.read_csv('exports/fact_message.csv'); c='Medellín'; print(len(u[u.city_canon==c]), len(m[m.city_canon==c]))"
  ```
- [ ] No hand-typed number or date anywhere (the Selection pane walk, 11.2) — only the
      editorial bullets tile.
- [ ] `DataFolder` re-point works: copy `exports/` to another folder, change the parameter,
      refresh, everything still loads.

**Data and UX**

- [ ] Every MEAL visual shows its n; `MEAL Response Rate` recomputes under a city filter.
- [ ] Small-n suppression verified on Cartagena (1 message → the whole row is dots).
- [ ] No message text and no phone-derived value exists in the model (`fact_message` is
      text-free by design; `nlp_voices` holds 4 curated quotes and appears on **none** of the
      three tabs).
- [ ] Re-run the PII gate after every pipeline run (it runs automatically inside
      `run_pipeline.py`, but confirm it passed) — see "Is the data anonymised?" below.
- [ ] `dim_user[safety_alert]` is **not** on any of the three tabs.
- [ ] ⚠️ No tone percentage is visible anywhere: axis off, labels off, tooltip off (9.5).
- [ ] Task-based test with a non-technical reader, under 60 seconds each: "Which city has the
      most users?" · "What does Cúcuta ask about most?" · "Is humanitarian demand growing?" ·
      "How satisfied are users, and how much should I trust that?" · "Which need is big but
      badly served?"
- [ ] Page load under 3 s; interactions under 1 s.
- [ ] The refresh runbook executed once, successfully, by someone other than the builder.

### 12.4 Is the data anonymised?

**Yes, for every user including the new v2 arrivals — with two caveats you should know about
before this file leaves your machine.**

What was verified against the current export (1,392 users, of which 78 are new v2 registrations):

| Check | Result |
|---|---|
| Raw identifiers in `exports/` | **None.** `Name` (the WhatsApp id) is dropped in `load_responses` before anything else touches the frame. |
| `user_id` format | All 1,392 are 12-character **salted SHA-1 digests** (`0014ad7a21e3`). The salt lives in `SAMI_SALT`, out of band and never in the repo — without it the hash cannot be reversed even by someone holding the export. |
| New v2 users specifically | Same code path, no exceptions — the loader pseudonymises before the cohort split, so there is no branch where a v2 row could skip it. |
| Automated PII gate | **21 of 21 shipped tables pass.** `write_all` scans every frame for `whatsapp:` and any 7+ digit run *before* writing anything, so a violation leaves `exports/` untouched rather than half-written. |
| Free-text columns that do ship | `no_usefulness_reason` (96), `nlp_voices[message]` (4), `safety_alert` (5) — hand-scanned for names, emails, document numbers and phone numbers. Clean. |
| Message text | Not exported at all. `fact_message` carries a content **hash**, never the message. |

**Caveat 1 — `safety_alert` is a narrative, and narratives re-identify.** Five users carry a
free-text incident note, some describing a specific person's situation in a named city on a
named date ("their son is being held in a detention center in Cali"). No name or number appears
in them, so the automated gate passes and will keep passing — but a small enough population
plus a specific enough story is identifying regardless of what the regex thinks. **Keep this
column off the report.** It ships so the pipeline can count escalations, not so anyone can read
them on a dashboard.

**Caveat 2 — anonymised is not the same as non-sensitive.** The model still holds city, age,
gender, nationality and migration intent per user. Any visual that slices far enough down
(one city × one nationality × one age band) can isolate a single person even though no name
exists anywhere. That is what the small-n suppression rule in the checklist above is for —
it is a privacy control, not a chart-quality nicety.

**To re-verify at any time:**

```powershell
.venv\Scripts\python.exe -c "import sys,glob; sys.path.insert(0,'src'); import pandas as pd; from sami import qa; [print(('FAIL' if qa.pii_scan(pd.read_csv(f)) else 'ok  '), f) for f in glob.glob('exports/*.csv') if '_manifest' not in f]"
```

---

## Appendix A — Five things doc 03 asks for that cannot be built literally

Each has a substitute built above. Each should be confirmed with Francisco before handover.

### D1 — The "% Negative tone" KPI cannot be published

Doc 03 §3 lists `% Negative Tone` as a core measure and §4 puts it in the Tab 3 KPI band. The
tone gate forbids exactly that: κ = 0.604 < 0.70, so `sentiment_quotable = false`. A KPI card
is the single most quotable surface in the product — precisely the wrong place for a number we
can't stand behind.

**Built instead:** `Most Negative Category` — a card naming the top-ranked category with no
number attached — plus the axis-less rank bar (9.5) and the `Tone Gate Banner` above both. If
a future run passes the gate, swap the card to `Negative Tone Index` and turn the axis back
on; the banner already switches itself.

### D2 — `intent_ext` does not exist; coverage gaps come from theme probes

Doc 03 §2.4 names `intent_ext` as a Python-computed column, and §4 asks for "% of messages
outside the official taxonomy, **by candidate intent**". The pipeline ships no such column.
`% Outside Official Taxonomy` *is* computable (0.9% — the classifier nearly always assigns
something), and the candidate intents live in `nlp_emergent_themes` as regex-probe counts.

**Built instead:** the coverage-gaps bar draws `nlp_emergent_themes[n_users]` with an explicit
"floor, not a rate" footnote, and `% Outside Official Taxonomy` sits beside it as a card. The
two numbers measure different things, and the footnote says so.

### D3 — The standalone agg tables ignore the slicers

`agg_funnel`, `agg_priority_matrix`, `agg_entities_by_kind` and the `agg_weekly_*` tables are
pre-aggregated over the whole period and have no relationship to `dim_date`, `dim_city` or
`dim_user`. Filtering to Cúcuta, or to April, does **not** change them.

**Built instead:** the weekly-category trend is rebuilt from `fact_message` + `dim_date` so
that it *does* respond (8.4). The funnel, the priority matrix and the entities bar stay
standalone — recomputing them in DAX would violate doc 03 §2.4 — and each carries a
"whole-period; not filtered" subtitle so nobody misreads a static visual as a filtered one. If
MMC needs a city-filtered priority matrix, that's a pipeline change (add `city_canon` to the
grain), not a Power BI change.

### D4 — `Users` does not respond to the date slicer

`dim_date` filters the fact tables, and the `dim_user → fact_message` relationship is
single-direction (doc 03 §3 forbids bidirectional filters), so a date selection cannot
propagate back up to the user table.

**Built instead:** two measures with different jobs — `Users` (the 917-person cohort, matches
`parity_check`, responds to city and profile filters) and `Active Users` (date-responsive, used
on every time axis), plus `New Users` via `first_seen`. Both are documented on the About page.
The alternative — making the relationship bidirectional — would buy a date-aware `Users` at
the cost of the parity guarantee and the model rule. Not taken.

### D5 — `agg_city` is gone; MEAL has 4 orphan respondents

Doc 03 §4 sources the map from "`agg_city`/`dim_city` lat/lon". `agg_city` no longer ships —
`dim_city` (13 cities with coordinates) replaced it, and user counts come from the live `Users`
measure. That's strictly better: the bubble size now respects the slicers.

Separately, 4 of the 69 MEAL respondents have `user_id`s absent from `dim_user`. They land in a
blank row on the `dim_user → fact_meal` relationship and drop out under any city filter, so a
city-filtered `MEAL Response Rate` is very slightly conservative. Noted in the measure
description and on the About page; at n = 69 it isn't worth a pipeline change.

---

## Appendix B — Charts that did not make the twelve

Twelve visuals means saying no to seventeen others. The notebooks hold up to 29 figures; these
are the ones that stay in the notebooks and the written report. Build recipes are here in case
MMC ever asks for a scratch page — but **do not add them to the three tabs.** The editorial
constraint in doc 03 §1 is the point of the product.

| Chart | Tables | Visual | Notes |
|---|---|---|---|
| Gender split | `dim_user[gender_clean]` | Donut, Values = `Users` | Absorbed into the Tab 1 profile bar |
| Age histogram | `dim_user[age_num]` | Column; right-click the field → **New group → Bin → size 5** | Filter `age_flag = ok` |
| Travels with minors | `dim_user[minors]` | Donut | |
| Nationality | `dim_user[nationality_canon]` | Bar | ⚠️ Always slice/split by `dim_user[instrument_version]` — v1 respondents who said Colombia had the survey ended, so v1 and v2 nationality mixes are not comparable pooled |
| Time away from origin | `dim_user[away_duration_canon]` | Bar, sorted by `away_duration_order` | |
| Onward destinations | `dim_user[destination_country]` | Bar | The notebook's arrow map has no native equivalent |
| Daily volume | `agg_daily_volume` | Line, X = `day` | Standalone |
| Satisfaction over time | `agg_weekly_rating` | Line, Y = `mean_rating` (**Average**), Y range 1–5 | n per week is tiny |
| Usefulness distribution | `fact_meal[usefulness_rating]` | Bar, sorted by `rating_num` | Always with n = 69 |
| Discovery channel | `fact_meal[discovery_channel]` | Bar | Written report only (doc 03 §4) |
| Archetype scatter | `nlp_umap` + `dim_cluster` | Scatter: X `x`, Y `y`, Details `user_id`, Legend `dim_cluster[name]`, both axes off | Mechanics, not outcome |
| Archetype terms | `nlp_cluster_terms` | Bar of `weight` per `term`, filtered by `cluster_id` | The word-cloud visual is a custom visual — **banned** (doc 03 §8) |
| Tone confusion matrix ⚠️ | `nlp_tone_confusion` | Matrix: rows `human_label`, cols `model_label`, values `n` | Validation evidence — report/About only |
| 3-class tone by category ⚠️ | `fact_message` | 100% stacked bar | Directional texture only; never published |
| Voices | `nlp_voices` | Table: `name`, `message` | Quotes belong in the written report |
| Archetype table | `dim_cluster` | Table | Written report only |

⚠️ = tone-suppressed: order or evidence only, never a published percentage.
