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
| [3](#part-3--load-the-data-power-query) | `DataFolder` parameter, 21 queries, calendar |
| [4](#part-4--the-model) | Relationships, date table, sort orders, hiding, measures table |
| [5](#part-5--the-measures) | All DAX |
| [6](#part-6--canvas-and-slicer-rail) | Page size, layout grid, slicers |
| [7](#part-7--tab-1--who-is-sami-reaching) | Tab 1 |
| [8](#part-8--tab-2--what-do-they-need) | Tab 2 |
| [9](#part-9--tab-3--is-it-working) | Tab 3 |
| [10](#part-10--the-hidden-about-page) | About page + ⓘ buttons |
| [11](#part-11--interactions-titles-accessibility) | Interactions, dynamic subtitles, alt text |
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
Schema Check =
VAR V = LOOKUPVALUE ( meta_run[value], meta_run[key], "schema_version" )
RETURN IF ( V = "3", "Schema v3 ✓", "⚠ Unexpected schema version: " & V )
```

```DAX
Empty State =
IF ( ISBLANK ( [Messages] ), "No data for this selection", "" )
```

Place `Empty State` as a card behind each visual group.

### 5.6 Two calculated columns

Modeling ribbon → **New column**, with the named table selected.

With `dim_city` selected — optional, only if bubble counts must be readable in a static export:

```DAX
map_label =
VAR n = COUNTROWS ( RELATEDTABLE ( dim_user ) )
RETURN
    dim_city[city_canon] & " · " & FORMAT ( n + 0, "#,0" )
```

With `agg_priority_matrix` selected — required by 9.2:

```DAX
Category Label =
LOOKUPVALUE (
    dim_category[category_en],
    dim_category[category_key], agg_priority_matrix[category]
)
```

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

---

## Part 7 — Tab 1 — Who is SAMI reaching?

Go to page `1 · Who is SAMI reaching?`.

### 7.1 Page title

Insert → **Text box** → **Who is SAMI reaching?** → select the text → size **20**.
**Position:** 208, 16, 700, 56.

### 7.2 KPI band

For each of the four:

1. Empty canvas → **Card**.
2. Drag the measure into **Fields**.
3. **Format → Callout value → Font size: 32.**
4. **Format → Category label → On.**
5. Position from the table.

| # | Measure | Label shown | Position |
|---|---|---|---|
| 1 | `Users` | Users reached | 208, 88 |
| 2 | `Avg Session Time` | Avg session (min) | 476, 88 |
| 3 | `Mean Usefulness` | Usefulness rating | 744, 88 |
| 4 | `MEAL n` | Surveys submitted | 1012, 88 |

To set the label under the number: Build pane → double-click the field name inside the
*Fields* well → type the label.

Leave the default interactions in place — the cards respond to the slicers and to clicks on
other visuals.

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
  closed set of five: `Woman`, `Man`, `LGBTQ+`, `Prefer not to say`, `Other`.

**Footnote text box:** "35 records with implausible sub-18 ages are excluded; self-reported.
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

Four **Card** visuals, method as in 7.2. Cards 1–3 are percentages at 0 dp; card 4 is text.

| # | Measure | Label shown | Position |
|---|---|---|---|
| 1 | `% Would Recommend` | Would recommend | 208, 88 |
| 2 | `% Repeat Askers` | Repeat askers | 476, 88 |
| 3 | `% Outside Official Taxonomy` | Arrived unlabelled | 744, 88 |
| 4 | `Most Negative Category` | Most negative tone (rank) | 1012, 88 |

- Card 1: **Format → General → Title → Subtitle → `fx` → Field value → `MEAL Subtitle`.**
- Card 4 shows a category name and no number.
- Set **Edit interactions → None** for all four.

### 9.2 Visual A — The priority matrix

**Position:** 208, 200, 1056, 250 (full top row).

First add the two median measures by the Part 5 method:

```DAX
Median Priority Volume = MEDIANX ( ALL ( agg_priority_matrix ), agg_priority_matrix[messages] )
```
```DAX
Median Priority Unmet  = MEDIANX ( ALL ( agg_priority_matrix ), agg_priority_matrix[unmet_need] )
```

`agg_priority_matrix[Category Label]` from Part 5.6 must exist — the raw `[category]` column
holds keys like `legal_documentation` and would print in snake_case.

**Build**

1. Empty canvas → **Scatter chart**.
2. **X-axis:** `agg_priority_matrix[messages]`
3. **Y-axis:** `agg_priority_matrix[unmet_need]`
4. **Size:** `agg_priority_matrix[users]`
5. **Values** (called *Details* in some versions): `agg_priority_matrix[Category Label]` — this
   is the well that makes each category its own bubble.

**Format**

- **Category labels → On.**
- **Data colors:** set each of the 7 bubbles by hand from the
  [category colour table](#114-category-colours-for-the-manual-bindings). This table has no
  relationship to `dim_category`, so `fx` binding is not available here.

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

| Quadrant | Meaning | Fill |
| --- | --- | --- |
| Top-right | Big and badly served — act here | `#671e42` |
| Top-left | Small but badly served — watch | `#a3557a` |
| Bottom-right | Big and well served — protect | `#009ba4` |
| Bottom-left | Small and well served | `#b7b7b7` |

Keep fills at 90% transparency or higher. Tinting only the top-right quadrant is a valid
option.

**Quadrant captions:** four Insert → Text boxes, 9 pt grey, one in each corner: "Big and badly
served — act here" · "Big and well served — protect" · "Small but badly served — watch" ·
"Small and well served".

**Caption under the visual** (text box): "The vertical axis is a composite priority ranking
(volume, repeat rate, rating and tone, z-scored) — not a rate. Tone is one of the four inputs."

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
- **Data colors**, by hand: `#009ba4`, `#671e42`, `#62c8ce`, `#a3557a`, `#000031`, `#c78fa4`.
- **General → Title:** `Six archetypes of asker`.

**Footnote text box**, 9 pt grey: "Axes are embedding coordinates with no units. 1,198 users
with text; positions change between runs, groupings don't."

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

- "MEAL responses: 69 of 917 users (7.5%) — indicative, never representative."
- "Tone is shown as rank order only; no tone percentage is published anywhere in this report."
- "Age, gender, destination and duration are self-reported; 35 records with implausible
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
| Suggestion | `#b7b7b7` |

Use this table only where an `fx` binding is impossible (the priority matrix, 9.2). Everywhere
a relationship to `dim_category` exists, bind via **`fx` → Field value → `color_hex`**.

---

## Part 12 — Save and refresh

### 12.1 Save

**File → Save as** → `mmc_dashboard.pbix` in the repo root. The file is git-ignored.

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
   the parity table is all `True` and `Schema Check` reads "Schema v3 ✓".

To re-point the report at a different folder: **Home → Transform data → Manage Parameters →**
change `DataFolder` **→ Close & Apply → Refresh.**
