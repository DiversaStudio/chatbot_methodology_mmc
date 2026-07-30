# Building `mmc_dashboard.pbix`

Build steps for the MMC dashboard: 3 tabs, 13 visuals, 4 KPI cards per tab, a hidden About
page, and a refresh that needs no rebuilding.

All data preparation happens in Python (`run_pipeline.py` → `exports/`). Power BI loads the
CSVs, relates them, aggregates and draws. Column reference:
[`exports/_schema.md`](../exports/_schema.md).

---

## Contents

| Part | What you do |
|---|---|
| [0](#part-0--conventions) | Conventions used by every step below |
| [1](#part-1--install) | Install Power BI Desktop and the one custom visual |
| [2](#part-2--apply-the-theme) | Load the colour theme |
| [3](#part-3--load-the-data-power-query) | `DataFolder` parameter, 22 queries, calendar |
| [4](#part-4--the-model) | Relationships, date table, sort orders, hiding, measures table |
| [5](#part-5--the-measures) | All DAX |
| [6](#part-6--canvas-and-slicer-rail) | Page size, layout grid, slicers |
| [7](#part-7--tab-1--who-is-sami-reaching) | Tab 1 |
| [8](#part-8--tab-2--what-do-they-need) | Tab 2 |
| [9](#part-9--tab-3--is-it-working) | Tab 3 |
| [10](#part-10--the-hidden-about-page) | About page, ⓘ buttons, green `?` provenance markers |
| [11](#part-11--interactions-titles-accessibility) | Interactions, titles, subtitles, alt text |
| [12](#part-12--save-and-refresh) | Save, refresh runbook |

---

## Part 0 — Conventions

**Panes** (right side of Report view): **Data** lists tables; **Visualizations** has the chart
icons and three sub-tabs — **Build** (bar-chart icon, field wells), **Format** (paint roller),
**Analytics** (magnifying glass, reference lines); **Filters** holds visual/page filters. A
missing pane comes back from **View → tick its checkbox**.

`table[column]` means the column `column` inside the table `table`.

| Step written as | Do this |
|---|---|
| *Empty canvas → **Card*** | Click empty canvas so nothing is selected, then click the visual's icon |
| *Drag `x` into **Y-axis*** | Select the visual, Build sub-tab, drag the field from the Data pane onto that well (or tick its checkbox and drag it between wells) |
| *▾ → **Don't summarize*** | Hover the field in its well, click the **▾**, pick the aggregation |
| *Format → **Data labels** → On* | Paint roller → type the setting name in the **search box** at the top → set it |
| *Position: 208, 200, 520, 250* | Format → General → Properties → **Size and position** → X, Y, Width, Height in px |
| *… → **Sort axis*** | Hover the visual → **…** at its top-right → Sort axis → field → direction |
| *`fx` → **Field value*** | Click the small **`fx`** beside a format setting → Format style: *Field value* or *Gradient* → pick the field |

**Ctrl+S** after every Part.

---

## Part 1 — Install

- **Windows PC.** Power BI Desktop is Windows-only.
- **Power BI Desktop** — Microsoft Store → search "Power BI Desktop" → **Get**, or
  `https://aka.ms/pbidesktopstore`.
- **The `exports/` folder**, freshly generated:
  ```powershell
  .venv\Scripts\python.exe run_pipeline.py
  ```
  Run it **without** `--skip-nlp` so the whole folder is one coherent export. `exports/` ends
  up with 21 `.csv` files plus `_manifest.csv` and `_schema.md`.
- **Copy the full path to `exports/`** from the File Explorer address bar. You paste it once,
  in Part 3.1.
- **One custom visual: Word Cloud** (Part 9.4), sideloaded from
  [`docs/WordCloud.1.2.9.pbiviz`](WordCloud.1.2.9.pbiviz) — it is not on AppSource. Everything
  else uses built-in visuals.

**First launch:** open Power BI Desktop, close the splash screen with its ×. You are on a
blank Report view.

---

## Part 2 — Apply the theme

1. Ribbon → **View** tab.
2. **Themes** group → the **▾** at its right end.
3. **Browse for themes** → repo → `docs` → [`sami_theme.json`](sami_theme.json) → **Open**.

Category colours are not in the theme — they live in `dim_category[color_hex]` and get bound
per-visual with `fx`.

---

## Part 3 — Load the data (Power Query)

Open the editor: ribbon → **Home → Transform data** (the button, not its ▾).

### 3.1 Create the `DataFolder` parameter

1. **Home → Manage Parameters (▾) → New Parameter.**
2. **Name:** `DataFolder` · **Type:** `Text` · **Suggested Values:** `Any value` ·
   **Current Value:** your full path to `exports`, **no trailing backslash**.
3. **OK.**

### 3.2 Create each query

For every table below:

1. **Home → New Source (▾) → Blank Query.**
2. **Home → Advanced Editor.**
3. **Ctrl+A**, delete, paste the block, confirm *"No syntax errors have been detected"* →
   **Done**.
4. **Query Settings → Name** → type the query name (= CSV filename without `.csv`) → Enter.

If a yellow *"Information is required about data privacy"* bar appears: click it → **Ignore
Privacy Levels checks for this file** → Save.

Do **not** create queries for `_manifest.csv` or `_schema.md`.

---

**`dim_user`**

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
                     "registered_at",
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
                     {"registered_at", type datetime},
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

Any visual built on `no_usefulness_reason` takes a visual-level filter
`reason_is_valid = true`.

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
                     "top_categories", "display_order", "color_hex"},
                    MissingField.Error
                 ),
    Typed     = Table.TransformColumnTypes(
                    Selected,
                    {{"cluster_id", Int64.Type}, {"name", type text},
                     {"n_users", Int64.Type}, {"n_messages", Int64.Type},
                     {"median_age", type number}, {"top_categories", type text},
                     {"display_order", Int64.Type}, {"color_hex", type text}},
                    "en-US"
                 )
in
    Typed
```

---

**`dim_quadrant`**

Four static rows that make the priority matrix's legend a real visual instead of four
hand-drawn shapes. See [9.2](#92-visual-a--the-priority-matrix).

```m
let
    Source    = Csv.Document(
                    File.Contents(DataFolder & "\dim_quadrant.csv"),
                    [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
                 ),
    Headers   = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected  = Table.SelectColumns(
                    Headers,
                    {"quadrant_key", "label", "action", "axis_x", "axis_y",
                     "color_hex", "display_order"},
                    MissingField.Error
                 ),
    Typed     = Table.TransformColumnTypes(
                    Selected,
                    {{"quadrant_key", type text}, {"label", type text},
                     {"action", type text}, {"axis_x", type text},
                     {"axis_y", type text}, {"color_hex", type text},
                     {"display_order", Int64.Type}},
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

Leave empty `mean_rating` values as `null` — do not replace them with 0.

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

---

**`agg_registration_funnel`**

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

Any visual on this table puts `instrument_version` on an axis or legend — never sum across it.

---

**`agg_language`**

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

`n_users` counts users who ever used a language, so it does not sum to the user total. Use it
for bars, not for a pie.

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
                    {"category", "category_en", "color_hex", "messages", "users",
                     "pct_repeat", "mean_rating", "meal_n", "rating_is_fallback",
                     "pct_negative", "n_axes", "unmet_need"},
                    MissingField.Error
                 ),
    Typed     = Table.TransformColumnTypes(
                    Selected,
                    {{"category", type text}, {"category_en", type text},
                     {"color_hex", type text}, {"messages", Int64.Type},
                     {"users", Int64.Type}, {"pct_repeat", type number},
                     {"mean_rating", type number}, {"meal_n", Int64.Type},
                     {"rating_is_fallback", type logical}, {"pct_negative", type number},
                     {"n_axes", Int64.Type}, {"unmet_need", type number}},
                    "en-US"
                 )
in
    Typed
```

`pct_negative` loads but is never placed on a visual.

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

**`meta_run`** — both columns stay text.

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

If a boolean column (`has_text`, `is_repeat_asker`, `intends_to_stay`, `match`,
`rating_is_fallback`) stays text after loading — left-aligned with an `ABC` header icon —
leave it as text and write its DAX comparison as `= "True"` instead of `= TRUE()`.

### 3.3 The calendar table

**New Source → Blank Query → Advanced Editor**, paste, **Done**, rename to `dim_date`:

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

### 3.4 Load into the report

**Home → Close & Apply.** The Data pane ends up with **22 tables** — 21 CSV queries plus
`dim_date`.

**Ctrl+S** as `mmc_dashboard.pbix` in the repo root.

---

## Part 4 — The model

Switch to **Model view** (third icon in the left view switcher). Delete every relationship
Power BI auto-detected: click the line, press **Delete**.

### 4.1 Draw the nine relationships

Drag the **first** field onto the second, and accept the defaults — **Cardinality: One to many
(1:\*)**, **Cross-filter direction: Single**.

`dim_quadrant` is the one loaded table with **no relationship at all**, by design: a
category's quadrant depends on where it falls relative to two median lines Power BI computes
at render time, so there is nothing to join on. It is a legend, not a dimension. If you find
yourself drawing a relationship from it, stop — see [9.2](#92-visual-a--the-priority-matrix).

| Drag this (the "one" side) | Onto this (the "many" side) |
|---|---|
| `dim_user[user_id]` | `fact_message[user_id]` |
| `dim_user[user_id]` | `fact_meal[user_id]` |
| `dim_user[user_id]` | `nlp_umap[user_id]` |
| `dim_city[city_canon]` | `dim_user[city_canon]` |
| `dim_category[category_key]` | `fact_message[dominant_category]` |
| `dim_cluster[cluster_id]` | `dim_user[cluster_id]` |
| `dim_cluster[cluster_id]` | `nlp_cluster_terms[cluster_id]` |
| `dim_date[Date]` | `fact_message[ts]` |
| `dim_date[Date]` | `fact_meal[ts]` |

Every relationship stays **single-direction**. Do not relate `dim_cluster` to
`nlp_umap[cluster_id]` — that is a duplicate path through `dim_user`.

The model ends with **9 relationship lines**, each with a `1` at one end, a `*` at the other,
one arrowhead, none dashed.

#### 4.1a — If the `dim_date → fact_*` drag is refused

Give each fact table a date-only column.

1. **Home → Transform data → `fact_message` → Advanced Editor.** Change the last three lines:

   ```m
                       "en-US"
                    ),
       WithDate  = Table.AddColumn(Typed, "date", each Date.From([ts]), type date)
   in
       WithDate
   ```

2. Same edit on `fact_meal`.
3. **Home → Close & Apply.**
4. Redraw the two relationships onto `fact_message[date]` and `fact_meal[date]`, same defaults.
5. Hide both new `date` columns in §4.4.

### 4.2 Mark the calendar

1. Data pane → click the table name `dim_date`.
2. Ribbon → **Table tools → Mark as date table (▾) → Mark as date table.**
3. **Date column:** `Date` → **OK**.

### 4.3 Sort-by columns

For each row: Data pane → click the left column → ribbon **Column tools → Sort by column (▾)**
→ pick the right column.

| Sort this column… | …by this column |
|---|---|
| `dim_user[away_duration_canon]` | `dim_user[away_duration_order]` |
| `dim_user[city_duration_canon]` | `dim_user[city_duration_order]` |
| `dim_category[category_en]` | `dim_category[display_order]` |
| `dim_cluster[name]` | `dim_cluster[display_order]` |
| `dim_quadrant[label]` | `dim_quadrant[display_order]` |
| `agg_funnel[stage]` | `agg_funnel[stage_order]` |
| `agg_registration_funnel[stage]` | `agg_registration_funnel[stage_order]` |
| `fact_meal[usefulness_rating]` | `fact_meal[rating_num]` |

If Power BI refuses the `agg_registration_funnel` pair, skip that row and sort that visual with
**… → Sort axis**.

### 4.4 Hide fields

Right-click the field in the Data pane → **Hide in report view**.

Hide: every `user_id`, every `message_id`, `dim_category[category_key]`, every `cluster_id`,
every column ending in `_order`, `dim_date[Month no]`, `fact_message[ts]`, `fact_meal[ts]`,
`dim_category[color_hex]`, and (if you took §4.1a) `fact_message[date]` and `fact_meal[date]`.

To see them again: right-click in the Data pane → **View hidden**.

### 4.5 Create the measures table

1. Ribbon → **Home → Enter data.**
2. Leave the empty column as it is. **Name:** `_Measures`.
3. **Load.**
4. After Part 5, right-click its `Column1` → **Hide in report view**.

---

## Part 5 — The measures

For each measure: Data pane → right-click `_Measures` → **New measure** → select the whole
formula bar contents and paste the block → **Enter**. Then with it still selected, in the
**Measure tools** ribbon tab set the **Description** and the **Format** given under each block.

Create them in the order below, since later measures reference earlier ones.

### 5.1 Reach and cohort

```DAX
Users = COUNTROWS ( dim_user )
```
**Description:** Distinct people who reached SAMI in the loaded export. Responds to city and
profile slicers, not to the date slicer — use `Active Users` for that.
**Format:** Whole number, thousands separator.

```DAX
Active Users =
DISTINCTCOUNT ( fact_message[user_id] )
```
**Description:** Users who sent at least one message inside the selected date range. Use this
in anything drawn on a time axis.
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
            dim_user[registered_at] >= FirstDay
                && dim_user[registered_at] < LastDay + 1
        )
    )
```

**Use `registered_at`, not `first_seen`.** `first_seen` is a user's first *message*, and is
blank for the 194 people who completed registration without ever writing. Filtering on it drops
them silently, so `New Users` came back 194 short of `Users` with nothing on the page to explain
the gap — and over the full date range it reproduced the "users with text" figure exactly,
which is not an independent fact. `registered_at` is the user's earliest response record and is
never blank, so the two measures reconcile.

Also note what this measure does **not** mean over the default window: with the whole date range
selected, every user registered inside it, so `New Users` equals `Users`. It earns its place
against a *narrower* selection — a month, a week — where it answers "how many of these people
are new?" Put a date selection on before reading it.
**Description:** Users whose first-ever message falls inside the selected window.
**Format:** Whole number.

```DAX
Avg Session Time =
MEDIANX (
    FILTER ( dim_user, NOT ( ISBLANK ( dim_user[session_minutes] ) ) ),
    dim_user[session_minutes]
)
```
**Description:** Median conversation length in minutes, from record creation to last message.
Covers the ~5% of users with session timestamps.
**Format:** Decimal number, **1** decimal place. Card label: **"Avg session (min)"**.

```DAX
Cities Covered =
CALCULATE (
    DISTINCTCOUNT ( dim_user[city_canon] ),
    dim_user[city_canon] <> "Other"
)
```
**Description:** Named cities with at least one user. Excludes the "Other" bucket.
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
**Format:** Percentage, **0** decimal places.

### 5.2 Demand

```DAX
Messages = COUNTROWS ( fact_message )
```
**Description:** Messages sent to SAMI in the current selection.
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
**Description:** Median messages per message-sending user.
**Format:** Decimal, 1 dp.

```DAX
% Zero-question Users =
DIVIDE (
    CALCULATE ( COUNTROWS ( dim_user ), dim_user[has_text] = FALSE () ),
    COUNTROWS ( dim_user )
)
```
**Description:** Users who registered but never sent a message.
**Format:** Percentage, 0 dp.

```DAX
% Repeat Askers =
DIVIDE (
    CALCULATE ( COUNTROWS ( dim_user ), dim_user[is_repeat_asker] = TRUE () ),
    COUNTROWS ( dim_user )
)
```
**Description:** Users at or above the 90th percentile of message count.
**Format:** Percentage, 0 dp.

```DAX
% Outside Official Taxonomy =
DIVIDE (
    CALCULATE ( [Messages], fact_message[dominant_category] = "unclassified" ),
    [Messages]
)
```
**Description:** Share of messages carrying no category label — the `unclassified` key, which
displays as *Suggestion*. A data-completeness reading, not a service gap. Label it
**"Arrived unlabelled"**.
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
**Description:** Message volume in the 28 days before the selected window.
**Format:** Whole number.

```DAX
Δ Messages vs Prev 4 Weeks =
DIVIDE ( [Messages] - [Messages Prev 4 Weeks], [Messages Prev 4 Weeks] )
```
**Description:** Growth against the previous 4 weeks. Blank when there is no prior window.
**Format:** Percentage, 0 dp.

`Δ` is a real character — copy the block rather than retyping it.

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
**Description:** Category with the largest 4-week growth.

### 5.3 Experience (the MEAL survey)

```DAX
MEAL n = COUNTROWS ( fact_meal )
```
**Description:** MEAL survey responses in the selection.
**Format:** Whole number.

```DAX
MEAL Response Rate = DIVIDE ( [MEAL n], [Users] )
```
**Description:** Responses ÷ users under the same filters.
**Format:** Percentage, 1 dp.

```DAX
Mean Usefulness = AVERAGE ( fact_meal[rating_num] )
```
**Description:** Mean 1–5 usefulness rating. Always shown alongside `MEAL n`.
**Format:** Decimal, **1 dp**.

```DAX
% Would Recommend =
DIVIDE ( CALCULATE ( [MEAL n], fact_meal[would_recommend] = "Yes" ), [MEAL n] )
```
**Description:** Share of MEAL respondents who would recommend SAMI.
**Format:** Percentage, 0 dp.

```DAX
Avg Session Time (Registered) =
MEDIANX (
    FILTER (
        dim_user,
        NOT ( ISBLANK ( dim_user[session_minutes] ) )
            && dim_user[registration_status] = "Completed"
    ),
    dim_user[session_minutes]
)
```
**Description:** Median conversation length in minutes for users who completed registration.
**Format:** Decimal number, 1 decimal place.

### 5.4 Tone

```DAX
Negative Tone Index =
DIVIDE (
    CALCULATE ( [Messages], fact_message[sentiment_label] = "negative" ),
    [Messages]
)
```
**Description:** Rank input only. Used to order categories; its value is never displayed.
**Format:** leave as Decimal.

```DAX
Most Negative Category =
CONCATENATEX (
    TOPN ( 1, VALUES ( dim_category[category_en] ), [Negative Tone Index], DESC ),
    dim_category[category_en]
)
```
**Description:** Category with the highest share of negative-tone messages, shown as a name
with no value.

### 5.5 Dynamic text

```DAX
Window Subtitle =
"n = " & FORMAT ( [Users], "#,0" ) & " users · "
    & FORMAT ( MIN ( dim_date[Date] ), "dd MMM yyyy" ) & " – "
    & FORMAT ( MAX ( dim_date[Date] ), "dd MMM yyyy" )
```

```DAX
MEAL Subtitle =
"n = " & FORMAT ( [MEAL n], "#,0" ) & " survey responses ("
    & FORMAT ( [MEAL Response Rate], "0.0%" ) & " of users)"
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

**`Data Up To`** — the Tab 1 KPI card ([7.2](#72-kpi-band)). Answers "how current is this?"
with the timestamp of the most recent message in the data, not the date the pipeline ran.
Description: *"Timestamp of the latest message in the export, in Colombian time."* Format: text.

```DAX
Data Up To =
VAR Raw   = LOOKUPVALUE ( meta_run[value], meta_run[key], "ts_max" )
VAR UTCts = DATEVALUE ( LEFT ( Raw, 10 ) ) + TIMEVALUE ( MID ( Raw, 12, 8 ) )
VAR COTts = UTCts - ( 5 / 24 )
RETURN FORMAT ( COTts, "d MMM yyyy, HH:mm" ) & " COT"
```

**Read the timezone carefully — this is the one measure where getting it wrong is invisible.**
`ts_max` is stored **UTC** (`load.load_responses` parses with `utc=True`, then drops the
tzinfo, so the value looks naive but is not local). Rendering it unconverted would print
`13:46` for a message actually sent at `08:46` Bogotá time — plausible, and wrong by five
hours. The `- (5/24)` shift is safe as a constant because Colombia observes no daylight saving;
do not copy this pattern for any other country without checking that.

The suffix is not decoration. A bare timestamp on a dashboard read by people in several
countries is ambiguous, and this card exists precisely to be trusted.

```DAX
Schema Check =
VAR V = LOOKUPVALUE ( meta_run[value], meta_run[key], "schema_version" )
RETURN IF ( V = "4", "Schema v4 ✓", "⚠ Unexpected schema version: " & V )
```

```DAX
Empty State =
IF ( ISBLANK ( [Messages] ), "No data for this selection", "" )
```

Place `Empty State` as a card behind each visual group.

**`Archetypes Found`** — the Tab 3 KPI card. Counts what the clustering actually produced
rather than hard-coding six, so a re-run at a different `k` corrects the card by itself.
Description: *"Number of distinct asker archetypes found by the clustering."* Format: whole
number.

```DAX
Archetypes Found = DISTINCTCOUNT ( dim_cluster[cluster_id] )
```

**`Archetype Subtitle`** — sits under that card and under the archetype scatter. The stability
score is the number that says whether the grouping is worth reading at all; showing the count
without it invites the reader to treat six clusters as six facts.

```DAX
Archetype Subtitle =
VAR ARI = LOOKUPVALUE ( meta_run[value], meta_run[key], "stability_ari" )
RETURN
IF (
    ISBLANK ( ARI ),
    "Stability not recorded for this run",
    "Stable grouping · ARI " & FORMAT ( VALUE ( ARI ), "0.00" )
)
```

**`Report Stamp`** — the footer on every tab. Both halves come from `meta_run`, so neither can
go stale: `report_version` is bumped in `src/sami/export.py` (`REPORT_VERSION`), the date is
the export timestamp. This is the only place in the report where a version number is allowed
to appear — never type one into a text box.

```DAX
Report Stamp =
"v" & LOOKUPVALUE ( meta_run[value], meta_run[key], "report_version" )
    & "  ·  updated "
    & FORMAT (
        DATEVALUE ( LEFT ( LOOKUPVALUE ( meta_run[value], meta_run[key], "generated_at" ), 10 ) ),
        "d MMM yyyy"
      )
```

### 5.6 The calculated column

Modeling ribbon → **New column**, with the named table selected.

With `dim_city` selected — optional, only if bubble counts must be readable in a static export:

```DAX
map_label =
VAR n = COUNTROWS ( RELATEDTABLE ( dim_user ) )
RETURN
    dim_city[city_canon] & " · " & FORMAT ( n + 0, "#,0" )
```

That is now the **only** calculated column in the model.

*Removed:* `agg_priority_matrix[Category Label]`, a `LOOKUPVALUE` against `dim_category`. The
label ships in the export as `agg_priority_matrix[category_en]` — use that field directly in
9.2. If you built the report before this change, delete the old column so nobody has to guess
which of the two is authoritative.

---

## Part 6 — Canvas and slicer rail

Switch to **Report view**.

### 6.1 Page size and grid

1. Click empty canvas → **paint roller** (it reads *Format your report page*).
2. **Canvas settings → Type: 16:9** (1280 × 720 — the coordinate system used throughout).
3. Ribbon → **View → Page view → Fit to page.**
4. Ribbon → **View →** tick **Gridlines** and **Snap to grid**.
5. Double-click the page tab → rename to `1 · Who is SAMI reaching?`.

### 6.2 The layout grid

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
| Slicer rail | 16 | 16 | 176 | 688 |
| Page title | 208 | 16 | 700 | 56 |
| KPI card 1 | 208 | 88 | 252 | 96 |
| KPI card 2 | 476 | 88 | 252 | 96 |
| KPI card 3 | 744 | 88 | 252 | 96 |
| KPI card 4 | 1012 | 88 | 252 | 96 |
| Visual A (top-left) | 208 | 200 | 520 | 250 |
| Visual B (top-right) | 744 | 200 | 520 | 250 |
| Visual C (bottom-left) | 208 | 466 | 520 | 238 |
| Visual D (bottom-right) | 744 | 466 | 520 | 238 |

### 6.3 Build the slicer rail

**Date slicer**

1. Empty canvas → **Slicer**.
2. Drag `dim_date[Date]` into **Field**.
3. **Format → Slicer settings → Options → Style: `Between`.**
4. **Format → General → Title → On**, text `Date range`.
5. **Position: 16, 16, 176, 120.**

**City slicer**

1. Empty canvas → **Slicer**.
2. Drag **`dim_city[city_canon]`** into **Field** (not `dim_user`).
3. **Format → Slicer settings → Options → Style: `Vertical list`.**
4. **Format → Slicer settings → Selection →** turn **Multi-select with Ctrl** off.
5. Title: `City`.
6. **Position: 16, 152, 176, 300.**

**Window subtitle card**

1. Empty canvas → **Card** → drag `Window Subtitle` into **Fields**.
2. **Format → Callout value → Font size: 10.**
3. **Position: 16, 470, 176, 80.**

No category slicer on Tab 1.

### 6.4 Create the other two pages

1. Right-click the page tab → **Duplicate page**, twice.
2. Rename the copies `2 · What do they need?` and `3 · Is it working?`.
3. On each copy, delete the page title text box; keep both slicers.
4. On pages 2 and 3 only, add a third slicer: `dim_category[category_en]`, Style **Vertical
   list**, Title `Category`, **Position: 16, 470, 176, 234** (delete the subtitle card there).

### 6.5 Sync the slicers

1. Ribbon → **View → Sync slicers.**
2. Page 1 → click the **date slicer** → tick **Sync** and **Visible** for all three pages.
3. Click the **city slicer** → same.
4. Page 2 → click the **category slicer** → tick **Sync** and **Visible** for pages 2 and 3
   only.

### 6.6 The footer stamp

Every tab carries the report version and the data date, bottom-right, so a screenshot taken
out of context still says what it is and how old it is.

1. Page 1 → **Insert → Card** (not a text box) → field `Report Stamp`.
2. **Format → Callout value:** font **Segoe UI**, size **9**, colour `#3a3a5c`.
3. **Format → Category label → Off**; **General → Effects → Background → Off**,
   **Border → Off**.
4. **Position: 1044, 690, 220, 24.**
5. **Edit interactions → None** from every slicer — the stamp describes the export, not the
   selection, and must not change when someone filters.
6. **Ctrl+C**, then **Ctrl+V** onto the other two pages.

It renders as `v1.1.0 · updated 30 Jul 2026`. Bumping the version is a one-line edit to
`REPORT_VERSION` in [`src/sami/export.py`](../src/sami/export.py) followed by a pipeline run;
there is nothing to change in the report.

---

## Part 7 — Tab 1 — Who is SAMI reaching?

Go to page `1 · Who is SAMI reaching?`.

### 7.1 Page title

Insert → **Text box** → **Who is SAMI reaching?** → select the text → size **20**.
**Position:** 208, 16, 700, 56.

### 7.2 KPI band

For each of the five:

1. Empty canvas → **Card**.
2. Drag the measure into **Fields**.
3. **Format → Callout value → Font size: 32.**
4. **Format → Callout value → Display units: None**, **Value decimal places: 0.**
5. **Format → Category label → On.**
6. Position from the table.

**Step 4 is not cosmetic.** Power BI defaults display units to *Auto*, which renders 1,198 as
**"1K"**. A headline count is the one number on the page a reader will quote, and a rounded
"1K" both loses the figure and reads as an estimate — it invites exactly the "that can't be
right" reaction that a precise 1,198 does not. Set this on every card in the report, including
the Tab 3 band.

Five cards at **204 wide with 9 px gutters** fill the 1056 px band, same spacing as
[9.1](#91-kpi-band):

| # | Measure | Label shown | Position |
|---|---|---|---|
| 1 | `Users` | Users reached | 208, 88, 204, 96 |
| 2 | `Avg Session Time` | Avg session (min) | 421, 88, 204, 96 |
| 3 | `Mean Usefulness` | Usefulness rating | 634, 88, 204, 96 |
| 4 | `MEAL n` | Surveys submitted | 847, 88, 204, 96 |
| 5 | `Data Up To` | Data up to | 1060, 88, 204, 96 |

To set the label under the number: Build pane → double-click the field name inside the
*Fields* well → type the label.

Card 5 is text, not a number: set **Callout value → Font size: 18** so the timestamp fits on
one line, and **Edit interactions → None** from every slicer — it describes the export, not the
selection.

Leave the default interactions in place for cards 1–4 — they respond to the slicers and to
clicks on other visuals.

**`Data Up To` is not the same fact as the footer stamp.** The footer's date is
`generated_at`, when the pipeline last ran. This card is `ts_max`, the timestamp of the most
recent message in the data. They differ whenever the pipeline is re-run without a fresh export,
and the gap between them is exactly what a reader asking "is this current?" wants to see.

### 7.3 Visual A — Map: users by city

**Position:** 208, 200, 520, 250.

**Build**

1. Empty canvas → **Map** (the globe). Not *Filled map*, not *ArcGIS Maps*.
2. Drag `dim_city[lat]` into **Latitude** → ▾ → **Don't summarize**.
3. Drag `dim_city[lon]` into **Longitude** → ▾ → **Don't summarize**.
4. Drag `Users` into **Bubble size**.
5. Leave **Legend** empty.
6. Drag `dim_city[city_canon]`, `Users` and `Messages` into **Tooltips**. Do not put
   `lat`/`lon` in the tooltip, and do not bind `Users` twice.

**Format**

- **Map settings → Style: Grayscale.**
- **Map settings → Auto zoom: On.**
- **Map settings → Controls → Lasso select: Off**, **Zoom buttons: On**, reduced size.
- **Bubbles → Size: 18.**
- **Data colors:** teal `#009ba4`.
- **General → Title:** `Users by city`.

**Footnote text box** under the map, 9 pt grey: "Users whose city is 'Other' (unspecified) are
not mapped."

**Optional — numbers printed on the bubbles.** Drag `dim_city[map_label]` (Part 5.6) into
**Location**, then **Format → Category labels → On**, font 9, colour `#4a4a4a`. The label is a
calculated column, so it shows unfiltered totals; add "counts are unfiltered totals" to the
footnote if you use it.

### 7.4 Visual B — Weekly active users

**Position:** 208, 200, 1056, 250 (full top row).

**Build**

1. Empty canvas → **Line and clustered column chart**.
2. Drag `dim_date[Week start]` into **X-axis** → ▾ → **Don't summarize**. Use the plain field,
   never the Date Hierarchy.
3. Drag `Active Users` into **Y-axis**.
4. Drag `Messages` into **Secondary Y axis**.

**Format**

- **Lines → Stroke width: 3.** `Active Users` teal `#009ba4`; `Messages` red.
- **Markers → On.**
- **X axis → Type: Categorical.**
- Label both axes; keep the left axis starting at zero.
- **General → Title → Subtitle → `fx` → Format style: Field value → `Peak Week Note`.**

Add the subtitle measure by the Part 5 method:

```DAX
Peak Week Note =
VAR ByWeek = ADDCOLUMNS ( VALUES ( dim_date[Week start] ), "@u", [Active Users] )
VAR Top1 = TOPN ( 1, ByWeek, [@u], DESC )
RETURN
    "Peak: " & FORMAT ( MAXX ( Top1, [@u] ), "#,0" ) & " active users in the week of "
        & FORMAT ( MAXX ( Top1, dim_date[Week start] ), "dd MMM yyyy" )
```

### 7.5 Visual C — Profile: age × gender

**Position:** 208, 466, 520, 238.

**Build**

1. Empty canvas → **Clustered bar chart**.
2. **Y-axis:** `dim_user[age_range]`
3. **X-axis:** `Users`
4. **Legend:** `dim_user[gender_clean]`
5. **Filters on this visual:** drag `dim_user[age_flag]` in → tick **`ok`** only.
6. **Filters on this visual:** drag `dim_user[registration_status]` in → **is `Completed`**.
   Visual-level only, never page-level.

**Format**

- **Data colors:** Woman `#009ba4`, Man `#671e42`, all others grey `#b7b7b7`. The legend is a
  closed set of **four**: `Woman`, `Man`, `LGBTQ+`, `Other or prefer not to say`.

`Other` and `Prefer not to say` were merged on 2026-07-30. They were 3 and 19 people; a named
3-person cell is re-identifying in a migrant population, the same reason the trans and
non-binary self-descriptions were folded into LGBTQ+ at the July review. The joint label is
deliberately **not** "Prefer not to say" — that would report 3 people who gave an answer as
having declined to. If the legend still shows five entries after a refresh, the export
pre-dates the merge.

**Footnote text box:** "50 records with implausible sub-18 ages are excluded; self-reported.
9 unfinished registrations are excluded from the profile charts."

### 7.6 Visual D — Settlement: time in city

**Position:** 744, 466, 520, 238.

**Build**

1. Empty canvas → **Clustered bar chart**.
2. **Y-axis:** `dim_user[city_duration_canon]`
3. **X-axis:** `Users`
4. **… → Sort axis → city_duration_canon → Sort ascending.**

**Format**

- **Data colors → `fx` → Format style: Gradient →** field `dim_user[city_duration_order]`,
  **Minimum** `#eef6f5`, **Maximum** `#009ba4`.
- **General → Title:** `Most users have been in their city for months, not days`.

### 7.7 The editorial tile

Insert → **Text box** in the remaining bottom-right space, headed **"This period in 3
bullets"**, with three hand-written lines. Underneath, in small grey type: "Editorial summary —
written by hand, updated each cycle."

This is the only hand-written content in the report.

---

## Part 8 — Tab 2 — What do they need?

Go to page `2 · What do they need?`. Insert → Text box: **What do they need?**, 20 pt,
position 208, 16, 700, 56.

### 8.1 KPI band

Method as in 7.2. Default **Callout value** size.

| # | Measure | Label shown | Position |
|---|---|---|---|
| 1 | `Users` | Users | 208, 88 |
| 2 | `Avg Session Time (Registered)` | Avg session (min) | 476, 88 |
| 3 | `Mean Usefulness` | Usefulness rating | 744, 88 |
| 4 | `MEAL n` | Surveys completed | 1012, 88 |

Leave the interactions alone.

### 8.2 Visual A — The funnel

**Position:** 208, 200, 520, 250.

**Build**

1. Empty canvas → **Funnel** visual.
2. **Category:** `agg_funnel[stage]`
3. **Values:** `agg_funnel[n]`, aggregation **Sum**.
4. **… → Sort axis → stage → Sort ascending.**

**Format**

- **Data labels → On**, **Label contents: `Data value, percent of first`.**
- **Data colors → `fx` → Format style: Gradient**, field `agg_funnel[stage_order]`,
  Minimum `#009ba4` → Maximum `#eef6f5`.
- Drag `agg_funnel[conversion_from_prev]` into **Tooltips**, format Percentage 0 dp.
- **General → Title:** `From arrival to survey`.

**Subtitle** (typed, static): "Whole-period; not affected by the slicers. MEAL respondents are
a separate cohort."

### 8.3 Visual B — Usefulness rating (donut)

**Position:** 744, 200, 520, 250.

**Build**

1. Empty canvas → **Donut chart**.
2. **Legend:** `fact_meal[usefulness_rating]`
3. **Values:** `fact_meal[user_id]` → ▾ → **Count**.

**Format**

- **Detail labels → Label contents: `Percent of total`.**
- **Legend → On, Position: Right.**
- **Data colors:** `Very useful` `#00707a`, `Useful` `#009ba4`, `Moderately useful` `#62c8ce`,
  `Slightly useful` `#a6dfe3`, `Not useful` `#671e42`.
- **General → Title:** `How useful was it?`
- **Title → Subtitle → `fx` → Field value → `MEAL Subtitle`.**

### 8.4 Visual C — Top institutions

**Position:** 208, 466, 520, 238.

**Build**

1. Empty canvas → **Clustered bar chart**.
2. **Y-axis:** `agg_entities_by_kind[entity]`
3. **X-axis:** `agg_entities_by_kind[n]`
4. **Filters pane → Filters on this visual:** drag `agg_entities_by_kind[kind]` into the drop
   zone (not into the Build pane) → **Basic filtering** → tick `institution` → Apply.
5. **… → Sort axis → n → Sort descending.**

**Format**

- **Data colors:** teal `#009ba4`.
- **Data labels → On.**
- **General → Title:** `Most-mentioned institutions`.

### 8.5 Visual D — Top procedures

**Position:** 744, 466, 520, 238.

Copy Visual C and change three things:

1. Visual-level filter on `kind` → **is `procedure`**.
2. **Data colors:** wine `#671e42`.
3. **General → Title:** `Most-requested procedures`.

Then add: **Filters on this visual:** `entity` → **Top N → Top 10 by `n`** → Apply.

**Footnote text box**, 9 pt grey, under the two entity charts: "Whole-period counts from entity
extraction; not filtered by the date or city slicers."

---

## Part 9 — Tab 3 — Is it working?

Go to page `3 · Is it working?`.

**Page title:** Insert → Text box, **Is it working?**, 20 pt, position 208, 16, 520, 56.

### 9.1 KPI band

**Five** **Card** visuals, method as in 7.2. Cards 1–3 are percentages at 0 dp; card 4 is a
whole number; card 5 is text.

The band is 1056 px wide (208 → 1264). Five cards at **204 wide with 9 px gutters** fill it:

| # | Measure | Label shown | Position |
|---|---|---|---|
| 1 | `% Would Recommend` | Would recommend | 208, 88, 204, 96 |
| 2 | `% Repeat Askers` | Repeat askers | 421, 88, 204, 96 |
| 3 | `% Outside Official Taxonomy` | Arrived unlabelled | 634, 88, 204, 96 |
| 4 | `Archetypes Found` | Archetypes found | 847, 88, 204, 96 |
| 5 | `Most Negative Category` | Most negative tone (rank) | 1060, 88, 204, 96 |

- Card 1: **Format → General → Title → Subtitle → `fx` → Field value → `MEAL Subtitle`.**
- Card 4: **Subtitle → `fx` → Field value → `Archetype Subtitle`** — it renders
  "Stable grouping · ARI 0.84". The count is meaningless without it.
- Card 5 shows a category name and no number.
- At 204 px the callout font in the theme (32 pt) may clip a three-digit percentage. If any
  card wraps, drop **Callout value → font size** to 28 on all five, not just the one that
  wrapped — an uneven band reads as a mistake.
- Set **Edit interactions → None** for all five.

### 9.2 Visual A — The priority matrix

**Position:** 208, 200, 1056, 250 (full top row).

First add the two median measures by the Part 5 method:

```DAX
Median Priority Volume = MEDIANX ( ALL ( agg_priority_matrix ), agg_priority_matrix[messages] )
```
```DAX
Median Priority Unmet  = MEDIANX ( ALL ( agg_priority_matrix ), agg_priority_matrix[unmet_need] )
```

Label the bubbles with **`agg_priority_matrix[category_en]`**, never the raw `[category]`
column — that one holds keys like `legal_documentation` and prints in snake_case.

`category_en` is resolved at export time from the same `CAT_EN` map `dim_category` is built
from, so the seven bubble labels are the same strings as every other category label in the
report, by construction. A key the taxonomy gained but `CAT_EN` does not know now fails the
pipeline run; previously it silently produced an unlabelled bubble, because the old
`LOOKUPVALUE` column returned BLANK across the missing relationship.

**Build**

1. Empty canvas → **Scatter chart**.
2. **X-axis:** `agg_priority_matrix[messages]`
3. **Y-axis:** `agg_priority_matrix[unmet_need]`
4. **Size:** `agg_priority_matrix[users]`
5. **Values** (called *Details* in some versions): `agg_priority_matrix[category_en]` — this
   is the well that makes each category its own bubble.

**Format**

- **Category labels → On.** They now print as *Legal & documentation*, not
  `legal_documentation`.
- **Data colors:** set each of the 7 bubbles by hand. This is a scatter, so there is no `fx`
  button ([11.5](#115-category-colours-for-the-manual-bindings)), and unlike the archetype
  scatter the theme's palette order does not match the categories — so these seven really are
  hand-set. The hex for each bubble now ships alongside it in
  `agg_priority_matrix[color_hex]`: drop that column into a table visual next to `category_en`
  while you work, set the seven swatches from it, then delete the scratch table. That way the
  colours you type are read off the data rather than transcribed from a doc that can drift.

**The quadrant lines** — with the scatter selected, click the **Analytics** tab (magnifying
glass):

1. **X-Axis Constant Line → + Add** → `fx` next to *Value* → **Format style: Field value** →
   `Median Priority Volume`. **Line style: Dashed**, colour `#b7b7b7`.
2. **Y-Axis Constant Line → + Add** → same, with `Median Priority Unmet`.

**Quadrant shading** — either route:

*Constant-line shading.* Expand each constant line → **Shade area → On** → pick the side with
the **Before / After** selector → **Transparency 90%**. The two shades overlap, so the
top-right corner reads darkest.

*Four rectangles.* **Insert → Shapes → Rectangle**, four of them in the four corners of the
plot area. Each: **Format shape → Fill → On**, **Transparency 92%**, **Border → Off**. Then
select the scatter → **Format → General → Effects → Background → Off**, and use **Format ribbon
→ Selection pane** to drag the four shapes below the scatter.

The four fills come from `dim_quadrant[color_hex]` — read them off the table rather than
typing them, so the shading and the legend can never disagree:

| `quadrant_key` | Corner | Label | Action | Fill |
| --- | --- | --- | --- | --- |
| `high_volume_high_need` | Top-right | Big and badly served | Act here | `#671e42` |
| `low_volume_high_need` | Top-left | Small but badly served | Watch | `#a3557a` |
| `high_volume_low_need` | Bottom-right | Big and well served | Protect | `#009ba4` |
| `low_volume_low_need` | Bottom-left | Small and well served | Steady state | `#b7b7b7` |

Keep fills at 90% transparency or higher. Tinting only the top-right quadrant is a valid
option.

**The quadrant legend** — replaces the four loose corner captions with one visual bound to
data:

1. Empty canvas → **Table** visual.
2. **Columns:** `dim_quadrant[label]`, then `dim_quadrant[action]`.
3. **Format → Cell elements → Series: `label` → Background color → On → `fx` →**
   **Format style: Field value → Field: `dim_quadrant[color_hex]`.** Each row now carries its
   own quadrant colour as a swatch.
4. **Format → Grid → Vertical/Horizontal gridlines → Off**, **Column headers → Off**,
   **General → Effects → Background → Off**.
5. `label` sorts by `display_order` from [4.3](#43-sort-by-columns), so the legend reads
   most-urgent first regardless of alphabetical order.
6. **Position: 1044, 200, 220, 120** (top-right, inside the matrix's frame).
7. **Edit interactions:** set the legend's effect on **every** other visual to **None**. It
   has no relationship to anything (see [4.1](#41-draw-the-nine-relationships)); clicking a
   row must not appear to filter.

**Caption under the visual** (text box): "The vertical axis is a composite priority ranking
built from volume, repeat rate, rating and tone, z-scored."

**The `?` marker:** add a provenance button in this visual's top-right corner pointing at the
`TT · Priority matrix` tooltip page — see [10.3](#103-the-green--provenance-markers). The priority
matrix is the visual most often screenshotted out of context and the one whose y-axis is least
self-explanatory, so this one matters more than the rest.

### 9.3 Visual B — The archetype scatter

**Position:** 208, 466, 520, 238.

**Build**

1. Empty canvas → **Scatter chart**.
2. **X Axis:** `nlp_umap[x]` → ▾ → **Don't summarize**.
3. **Y Axis:** `nlp_umap[y]` → ▾ → **Don't summarize**.
4. **Values / Details:** `nlp_umap[user_id]`
5. **Legend:** `dim_cluster[name]` — this colours the dots and carries the click through to the
   word cloud.

**Format**

- **X axis → Off**, **Y axis → Off.**
- **Markers → Size 4.**
- **Legend → Position: Bottom centre**, font 9.
- **Data colors → leave every swatch untouched.** See below — this is deliberate, not an
  omission.
- **General → Title:** `Archetypes of asker` — no number in the title. The count lives in the
  KPI card, which reads it from the data; a hard-coded "Six" in a title is wrong the first
  time the clustering picks a different `k`.
- **Subtitle → `fx` → Field value → `Archetype Subtitle`.**

**Colouring the archetypes: why you touch nothing here.**

**A scatter chart cannot bind data colours to a field.** The `fx` button that other visuals
expose under *Data colors* does not exist on a scatter with a Legend — Power BI offers only a
fixed swatch per legend value. This is the same limitation [9.2](#92-visual-a--the-priority-matrix)
already runs into with the category bubbles. Do not go looking for the button; it is not
hidden, it is absent.

That leaves two ways to get the right colours, and the second is better:

1. *Click each of the six swatches by hand.* Works, but binds a colour to whatever position
   the legend was in that day. The next re-cluster re-colours every archetype and any slide
   made from an older screenshot quietly starts lying.
2. *Let the theme do it.* The first six entries of `dataColors` in
   [`sami_theme.json`](sami_theme.json) **are** the archetype palette, in order —
   `#009ba4`, `#671e42`, `#62c8ce`, `#a3557a`, `#000031`, `#c78fa4`. Power BI hands theme
   colours to legend values in legend order, so as long as the legend is sorted by
   `display_order` ([4.3](#43-sort-by-columns)) the largest archetype gets brand teal, the
   second gets wine, and so on — with no swatch ever clicked. Re-runs, a changed `k` and a
   re-sorted legend all self-correct, because nothing was pinned in the first place.

Route 2 is the instruction above. The one rule that keeps it working: **once you click a
swatch, Power BI pins that colour to that legend value and stops re-deriving it.** If the
colours ever look wrong after a refresh, the fix is *Data colors → Revert to default*, not
more clicking.

`dim_cluster[color_hex]` still ships in the export — it is what the notebooks plot with, and
it is the written-down answer to "what colour is this archetype supposed to be" when you need
to check the report against it. It is simply not consumable by this visual.

**Footnote text box**, 9 pt grey: "Axes are embedding coordinates with no units. 1,198 users
with text; positions change between runs, groupings don't."

**The `?` marker:** provenance button in the top-right corner → **NLP model output** tooltip
page, per [10.3](#103-the-green--provenance-markers).

### 9.4 Visual C — The word cloud

**Position:** 744, 466, 520, 238.

**Install it** — Word Cloud is no longer on AppSource, so it is sideloaded from a file rather
than installed from the store. The file ships with the repo:
[`docs/WordCloud.1.2.9.pbiviz`](WordCloud.1.2.9.pbiviz).

1. Visualizations pane → **`…` → Import a visual from a file.**
2. Click **Import** on the caution dialog.
3. Pick `docs/WordCloud.1.2.9.pbiviz` → **Open**. Its icon appears at the bottom of the
   Visualizations pane.

The visual is stored inside the `.pbix`, so anyone opening the saved file gets it without
importing anything. It never auto-updates.

To publish to the Power BI **Service**, the tenant setting **Allow visuals created using the
Power BI SDK** must be enabled — check with whoever administers the tenant before promising a
published report. If it is off, or if the visual stops rendering after a Desktop upgrade,
rebuild this slot as a **Treemap**: Category `nlp_cluster_terms[term]`, Values
`nlp_cluster_terms[weight]` (Sum), same relationship and slicer wiring below.

**Build**

1. Empty canvas → the **Word Cloud** icon.
2. **Category:** `nlp_cluster_terms[term]`
3. **Values:** `nlp_cluster_terms[weight]`, aggregation **Sum**.

**Format** — 1.2.9 exposes exactly four setting groups:

- **Rotate Text → Off.**
- **Stop Words → Off.**
- **General → Word-breaking → Off.**
- **General → Max number of words: 40** (the table holds 40 terms per cluster).
- **General → Min font size: 12**, **Max font size: 40.**
- **Data colors** is per-word and impractical across 240 terms — leave it on the theme default.
- **General → Title:** `What this archetype talks about`.

**Wire it to the archetype selection**

1. The relationship `dim_cluster[cluster_id] → nlp_cluster_terms[cluster_id]` from
   [4.1](#41-draw-the-nine-relationships) must exist, or the cloud shows all 240 terms
   regardless of what is clicked.
2. Add a **Slicer** on `dim_cluster[name]`, style **Dropdown**, in the header strip.
3. Leave **Edit interactions** from the scatter (9.3) to the cloud on **Filter**, not
   Highlight. Clicking a dot or a legend entry swaps the cloud.
4. Set **Edit interactions** from the cloud to both other visuals → **None**.
5. Set **Edit interactions** from the priority matrix (9.2) to the cloud → **None**. The matrix
   is keyed by category and `nlp_cluster_terms` is keyed by cluster, with no path between them,
   so a category selection cannot reach the cloud. Setting it to None makes that explicit
   instead of leaving a click that silently does nothing.

**Verify the wiring before moving on.** This connection fails silently — a broken cloud still
renders, just with the wrong words — so check it rather than assuming:

1. Click a single dot in the archetype scatter. The cloud must **change**, and the words must
   match that archetype's row in `nlp_cluster_terms`. Clicking *Building a livelihood* should
   surface `emprendimiento`; if it does not, you are not filtered.
2. Click the same archetype's **legend entry**. Same result — legend and dot must agree.
3. Click empty canvas to clear. The cloud should show a blended cloud of all 240 terms.

If the cloud never changes, work through these in order:

| Symptom | Cause | Fix |
|---|---|---|
| Always all 240 terms | The `dim_cluster[cluster_id] → nlp_cluster_terms[cluster_id]` relationship is missing | Draw it — [4.1](#41-draw-the-nine-relationships) |
| Words dim but don't disappear | Interaction is set to **Highlight**, not **Filter** | Scatter selected → **Format → Edit interactions** → the ▣ filter icon on the cloud |
| Changes on a dot but not the legend | Legend is on a different field than `dim_cluster[name]` | Re-drag `dim_cluster[name]` into **Legend** |
| Cloud empties completely | Relationship drawn backwards (`nlp_cluster_terms` on the "one" side) | Delete it and re-drag from `dim_cluster` |

**Caption under the visual** (text box, 9 pt grey): "Terms are ranked per archetype across the
whole corpus. Driven by the archetype selection only — not by the priority matrix, and not by
the city, gender or date slicers."

---

## Part 10 — The hidden About page

### 10.1 Build the page

1. Click **+** next to the page tabs → rename the page `About the data`.
2. Place, roughly top to bottom:

**Cards** (six): `Export Date`, `Data Window`, `Schema Check`, `Users`, `Messages`, `MEAL n`.

**Table visual from `meta_run`:** columns `key`, `value`.

**Table visual from `parity_check`:** columns `metric`, `exported_value`,
`reconciliation_value`, `match`. Then colour the `match` column:

1. Select the table → **Format → Cell elements.**
2. **Series** dropdown → `match`.
3. **Background color → On →** click the **`fx`**.
4. **Format style: Rules.** Add `True` → `#eef6f5`; `False` → `#671e42`.

**Text box — limitations:**

- "MEAL responses: 115 of 1,392 users (8%). Every MEAL figure describes those 115 respondents."
- "Age, gender, destination and duration are self-reported; 50 records with implausible
  sub-18 ages are excluded from the profile chart."
- "Archetype word clouds are ranked over the whole corpus and do not respond to the city,
  gender or date filters."
- "Archetype positions on the scatter change between pipeline runs; the groupings do not."
- "`Users` responds to city and profile filters but not to the date slicer; use `Active Users`
  for date-bounded reach."

**Text box — metric glossary:** one line per measure, copied from the Descriptions in Part 5.

**Text box — the refresh runbook:** the two steps from Part 12.2.

**Text box — how to move the data:** "The report reads only the CSVs in the folder named by the
Power Query parameter `DataFolder`. To move the data: Home → Transform data → Manage Parameters
→ change `DataFolder` → Close & Apply → Refresh. No other edit is ever needed."

3. Right-click the page tab → **Hide page.**

### 10.2 The ⓘ buttons

On each of the three visible tabs:

1. Ribbon → **Insert → Buttons (▾) → Information.**
2. **Format → Action → On → Type: `Page navigation` → Destination: `About the data`.**
3. **Format → Style → Icon →** colour `#3a3a5c`, size 20.
4. **Position: 1244, 16, 20, 20.**
5. **Ctrl+C**, then **Ctrl+V** onto the other two tabs.

On the About page, add **Insert → Buttons → Back**, top-left.

In Desktop, buttons fire on **Ctrl+click**; in a published report a plain click works.

### 10.3 The green `?` provenance markers

Every visual gets a small teal `?` in its corner. Hovering it shows a tooltip page naming the
source table, the n, and the one caveat that matters for that source. Hover, not click — the
reader stays on the page and keeps their selection.

The ⓘ button from 10.2 above is different and both stay: ⓘ is one per page and
navigates to the full About page; `?` is one per visual and answers "where did *this* number
come from" without moving.

**Build the four tooltip pages**

For each of the four below: **+** next to the page tabs → rename → **Format pane → Page
information → Allow use as tooltip → On** → **Canvas settings → Type: Tooltip** (320 × 240).
Fill it with text boxes at 9 pt, `#3a3a5c`, and hide the page when done.

| Page name | Covers |
|---|---|
| `TT · Chat data` | Tab 1 and 2 visuals — map, weekly actives, profile, settlement, funnel, categories, institutions, procedures |
| `TT · MEAL survey` | Rating donut, would-recommend, MEAL n, anything sourced from the survey |
| `TT · NLP model output` | Archetype scatter and word cloud |
| `TT · Priority matrix` | The matrix (9.2) |

The matrix gets its own page because it is the one visual that blends all three sources; a
reader who lands on it needs the axis explained, not just the table named.

Put `Export Date` and `Schema Check` as small cards at the foot of all four, so every tooltip
also says how fresh the data is.

The finished text for each page is in [10.4](#104-tooltip-page-copy).

**Add a `?` to a visual**

1. **Insert → Buttons (▾) → Blank.**
2. **Format → Style → Text → On →** text `?`, font **Segoe UI Semibold** 12, colour `#009ba4`.
3. **Style → Fill → On →** `#ffffff`; **Border → On →** `#009ba4`, radius 10.
4. **Size 20 × 20**, positioned in the visual's **top-right corner, inset 8 px** from its
   frame.
5. **Format → Action → Off.** A `?` must not navigate — hovering is the whole interaction.
6. **Format → General → Tooltip → Type: Report page → Page:** the matching page above.
7. **General → Alt text:** "Where this data comes from" — screen readers get no hover.

Build one, then **Ctrl+C / Ctrl+V** for the rest and re-point the tooltip page. Every visual on
Tabs 1–3 gets one, including the KPI cards.

**Do not** give a `?` to the quadrant legend, the footer stamp, the slicers or the page titles.
They are chrome, not findings, and a `?` on them dilutes the signal that a `?` means "this is a
claim about the data".

**Check before you finish:** Ctrl+click a `?` and confirm nothing happens (no navigation), then
hover and confirm the tooltip names a table you actually loaded in Part 3. A tooltip page that
was renamed after the buttons were made silently falls back to the default data tooltip — the
giveaway is a hover that shows raw field values instead of prose.

### 10.4 Tooltip page copy

Paste-ready. Each block is one tooltip page: a bold heading line, then the body. 9 pt,
`#3a3a5c`, bold heading at 10 pt `#000031`.

**Every number below is read off the 30 Jul 2026 export.** They are written into the text
rather than bound to measures because a tooltip page cannot filter itself to the visual that
called it. That makes them the one place in the report where a figure can go stale — check
them against the About page whenever the cohort changes materially, and see the note at the
end of this section.

---

**`TT · Priority matrix`**

> **How to read this chart**
>
> Each bubble is one message category. Left to right: how many messages it received. Bottom to
> top: a priority score combining message volume, repeat-asker rate, MEAL usefulness rating and
> message tone — each standardised, then averaged. The score has no unit; what it expresses is
> each category's position relative to the others. Bubble size is the number of distinct users.
>
> The two dashed lines are the medians across the seven categories. They move as the data
> moves, and are not targets.
>
> Where the rating comes from: categories with fewer than 20 MEAL responses of their own use
> the overall mean rating instead of their own. Five of the seven are in that position —
> `rating_is_fallback` marks them.
>
> The "Suggestion" bucket sits outside this chart.
>
> Source: `agg_priority_matrix.csv` · 7 categories · 4,663 messages · 25 Mar – 28 Jul 2026

---

**`TT · NLP model output`**

> **How the archetypes were found**
>
> Each user's messages are turned into a numeric representation of their meaning by a
> multilingual language model, then grouped by similarity. No one sorted these by hand, and the
> groups are not the platform's categories.
>
> Six archetypes across the 1,198 users who sent at least one message with text. The pipeline
> chose the number six; re-running it on resampled data recovers the same grouping (agreement
> 0.84 of 1.00).
>
> The two axes are coordinates from that representation. They carry no unit and no direction —
> nearness is the meaning. Positions shift each time the pipeline runs; which users group
> together does not.
>
> The word cloud shows the 40 terms most distinctive to the selected archetype, ranked across
> the whole corpus. It answers to the archetype you select, and not to the city, gender or date
> filters.
>
> Archetype names are written by the team as summaries of each group's terms.
>
> Source: `dim_cluster.csv`, `nlp_umap.csv`, `nlp_cluster_terms.csv` · model
> `multilingual-e5-large`

---

**`TT · Chat data`**

> **Where this comes from**
>
> Every message sent to SAMI in the window shown — 4,663 messages from 1,392 registered users,
> 25 Mar to 28 Jul 2026.
>
> Age, gender, city, nationality and destination are self-reported by the user at registration.
> 50 records give an age under 18 and are held out of the age profile; 9 registrations that
> were never completed are held out of the profile charts.
>
> Cities are matched to a fixed list of 14 with known coordinates. An answer outside that list
> falls into "Other" and has no position on the map.
>
> Message categories are the platform's own labelling, carried through as a suggestion.
>
> Users appear as salted one-way hashes. No names, phone numbers or document numbers exist in
> this dataset.
>
> Source: `fact_message.csv`, `dim_user.csv`, `dim_city.csv`

---

**`TT · MEAL survey`**

> **Where this comes from**
>
> The MEAL survey is a separate, voluntary questionnaire, not part of the chat. 115 people
> answered it, out of 1,392 registered users — 8%.
>
> Every figure on this visual describes those 115 respondents. It does not describe the other
> 1,277 users, who were never asked.
>
> Usefulness is a five-point scale, from "Not useful" to "Very useful".
>
> Source: `fact_meal.csv`, `agg_weekly_rating.csv` · 25 Mar – 28 Jul 2026

---

**Keeping the numbers true.** Six figures are hard-coded above: 4,663 messages, 1,392 users,
1,198 with text, 115 MEAL respondents, 50 sub-18 records, 9 incomplete registrations. After any
refresh, open the About page and compare. If they have moved, edit these four pages — it is a
two-minute job and it is the difference between a tooltip that builds trust and one that
quietly costs it.

---

## Part 11 — Interactions, titles, accessibility

### 11.1 Interaction pattern

Three behaviours only: **slicers filter · clicking a bar cross-highlights · ⓘ navigates.**

- Select each chart and confirm there are no ⤓ / ⌄ drill arrows in its header. If one appears,
  a date hierarchy is in a well — replace it with the plain field.
- No drill-through pages other than About.

### 11.2 Dynamic subtitles

For each visual: **Format → General → Title → Subtitle → `fx` → Format style: Field value** →
`Window Subtitle` (Tabs 1–2) or `MEAL Subtitle` (the MEAL visuals).

Then ribbon → **View → Selection pane**, click through every object on all four pages, and
confirm no text box contains a number or a date — except the editorial bullets tile on Tab 1.

### 11.3 Accessibility

- **Alt text:** select each visual → **Format → General → Alt text** → one sentence. Required
  on every visual and every KPI card.
- **Tab order:** **View → Selection pane → Tab order** tab → reorder each page: page title →
  KPI cards → visuals left-to-right, top-to-bottom → slicers last.
- **Contrast:** grey `#b7b7b7` is for decoration only, never for text that carries meaning.
- **Mobile layout, Tab 1 only:** **View → Mobile layout** → drag in the four KPI cards and the
  map, stack them vertically → **View → Desktop layout**.

### 11.4 Visual titles

Titles are the report's only running commentary, so they follow one rule: **a title says what
the reader should take away, a subtitle says how much data it rests on.**

- **Sentence case, no terminal full stop.** "Where askers are writing from", not "Users By
  City" and not "Where askers are writing from."
- **No numbers, no dates, no counts.** Those belong in the subtitle, which is bound to
  `Window Subtitle` / `MEAL Subtitle` and updates with the filters
  ([11.2](#112-dynamic-subtitles)). A number typed into a title is wrong the moment anyone
  touches a slicer.
- **No chart-type words.** Not "Scatter of archetypes", not "Funnel", not "Donut" — the reader
  can see what shape it is.
- **No field names.** "Time already in the city", not "city_duration_canon".
- Keep to one line at the visual's width. If it needs two, the visual is doing two things.

Walk **View → Selection pane** on all three tabs and check every title against those five.
Titles the old build shipped with numbers baked in — most of all "Six archetypes of asker" —
are corrected in [9.3](#93-visual-b--the-archetype-scatter).

### 11.5 Category colours (for the manual bindings)

| Category | Hex |
|---|---|
| Legal & documentation | `#009ba4` |
| Humanitarian assistance | `#671e42` |
| Protection | `#62c8ce` |
| Employment | `#a3557a` |
| Finding organizations | `#000031` |
| Journey information | `#c78fa4` |
| Services | `#a6dfe3` |
| Suggestion | `#b7b7b7` |

Use this table only where an `fx` binding is impossible (the priority matrix, 9.2). Everywhere
a relationship to `dim_category` exists, bind via **`fx` → Field value → `color_hex`**.

**Archetype colours** are not typed and not bound — they fall out of the theme palette in
legend order ([9.3](#93-visual-b--the-archetype-scatter)). The exporter assigns them by size
rank, so the table below is a fact about *this* run, not a rule. Use it to check the report,
not to set it:

| Archetype | Rank | Hex |
|---|---|---|
| Urgent humanitarian needs | 0 | `#009ba4` |
| Nationality and family papers | 1 | `#671e42` |
| Stuck mid-procedure | 2 | `#62c8ce` |
| Permits, visas and travel | 3 | `#a3557a` |
| Settling in | 4 | `#000031` |
| Building a livelihood | 5 | `#c78fa4` |

**Quadrant colours** come from `dim_quadrant[color_hex]` via the legend's *Cell elements*
binding ([9.2](#92-visual-a--the-priority-matrix)) — a Table visual, which does support `fx`.

### Where `fx` works and where it does not

Not every visual exposes conditional formatting on colour, and the guide's bindings follow that
line rather than a preference:

| Visual | `fx` on data colours? | So we… |
|---|---|---|
| Bar, column, donut, treemap, map | Yes | bind `dim_category[color_hex]` |
| Table, matrix | Yes, via **Cell elements** | bind `dim_quadrant[color_hex]` |
| **Scatter (with a Legend)** | **No — the button does not exist** | rely on theme order (9.3) or set swatches by hand (9.2) |

The two scatters are the only visuals in the report where a colour is not bound to a field.
For the archetype scatter that costs nothing, because legend order reproduces the palette. For
the priority matrix's seven category bubbles there is no such trick — those seven swatches are
the report's only genuinely hand-set colours. Anywhere else, if you are opening a colour
picker, the field you want is already in the model.

---

## Part 12 — Save and refresh

### 12.1 Save

**File → Save as** → `mmc_dashboard.pbix` in the repo root.

The file **is tracked in git**, not ignored — an earlier version of this line said otherwise.
Two consequences worth knowing before you save:

- A `.pbix` embeds the loaded data model, so committing it commits a copy of the export rows
  along with the layout. That is the same pseudonymised data already in `exports/`, but it
  means the binary is not just a layout file.
- It is a binary, so diffs are unreadable and two people editing it will conflict rather than
  merge. Coordinate before working on it in parallel.

### 12.2 The refresh runbook

1. Save the responses export into `datasets/responses/` and the MEAL export into
   `datasets/meal/` (see [`datasets/README.md`](../datasets/README.md) for the intake
   contract), then run the pipeline:
   ```powershell
   .venv\Scripts\python.exe run_pipeline.py
   ```
   It exits with an error if the parity checks fail. If that happens, stop — do not refresh.
   For preflight checks and troubleshooting, see [`docs/OPERATIONS.md`](OPERATIONS.md).
2. Open `mmc_dashboard.pbix` → ribbon **Home → Refresh** → go to the About page and check that
   the parity table is all `True` and `Schema Check` reads "Schema v4 ✓". Then glance at the
   footer stamp on Tab 1: the date must be today's export, not the previous one.

To re-point the report at a different folder: **Home → Transform data → Manage Parameters →**
change `DataFolder` **→ Close & Apply → Refresh.**
