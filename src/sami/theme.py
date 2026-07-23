"""Brand palette, plotly/mpl templates and EN display maps (ported from palette.py)."""

# Diversa brand color palette + shared chart design system.
#
# Two layers live here:
#   1. The Diversa BRAND colours (AGUA, MADERA, ...) used by illustration-style
#      semantic palettes (e.g. the MMC category colours in analysis_responses).
#   2. A general CHART design system (CAT / BLUE_SEQ + helpers) matching the EDA
#      notebooks: a fixed-order categorical palette for identity charts and a
#      light->dark ramp for ordered magnitude. Colour comes last; text and
#      surfaces stay neutral so they never compete with the data marks.
#
# Old names (BLUES, bar_colors, NEGRO, CIELO, ...) are kept as aliases so
# existing notebooks keep working unchanged.

import numpy as np
import matplotlib.pyplot as plt

# --- Brand anchors ----------------------------------------------------------
# The nine supplied brand colours. Everything else in this file is a tint or
# shade interpolated between these.
TEAL   = "#009ba4"   # primary data hue
WHITE  = "#ffffff"
MIST   = "#eef6f5"   # near-white teal-grey surface
AQUA   = "#d5eef0"   # pale cyan
FOG    = "#f3f4f7"   # light grey-blue (grid / base fills)
CREAM  = "#f0ead8"   # low-salience fill
GREY   = "#b7b7b7"
NAVY   = "#000031"   # ink / flags
WINE   = "#671e42"   # accent: annotations, medians, route arrows

# --- Chart design system ----------------------------------------------------
# Teal ramp (light -> dark) -- the sequential ramp for ordered magnitude
# (durations, ratings, missingness, cohorts). Name kept for compatibility.
BLUE_SEQ = ["#eef6f5", "#d5eef0", "#a6dfe3", "#62c8ce", "#009ba4", "#00707a"]
BLUES = BLUE_SEQ                                    # backwards-compatible alias

# Wine ramp (light -> dark) -- second colour family.
EARTH = ["#f0ead8", "#e6cdd6", "#c78fa4", "#a3557a", "#671e42"]

# Categorical hues (identity), assigned in this FIXED order, never cycled.
# Alternates the teal and wine families so adjacent slices/bars stay
# distinguishable while every colour stays on-brand.
#
# VALIDATED TO 7 SLOTS. Slots 1-7 pass CVD separation (worst adjacent pair
# ΔE 15.2 deutan) and the normal-vision floor (ΔE 20.1). Slots 8-10 are the
# brand's three near-neutral pales; they sit ΔE 3-4 apart from each other under
# both normal and protan vision, so a chart that reaches them CANNOT rely on
# colour for identity -- it needs direct labels, or the series folded into
# "Other". `cat_colors` warns when you cross the line.
CAT_VALIDATED = 7
CAT = ['#009ba4', '#671e42', '#62c8ce', '#a3557a', '#000031',
       '#c78fa4', '#a6dfe3',
       '#b7b7b7', '#f0ead8', '#d5eef0']
PRIMARY = TEAL                                      # single-series brand teal
ACCENT  = WINE                                      # annotations / the one pop
DEEP    = NAVY                                      # flags, secondary series

# Neutrals: text inks, grid, surface.
INK, INK2, MUTED = NAVY, '#3a3a5c', GREY
GRID, SURFACE    = FOG, WHITE
SURFACE_ALT      = MIST

# --- Legacy Diversa brand names (remapped onto the new palette) -------------
# Kept so notebooks and sami.geo keep working unchanged; each points at the
# closest colour that preserves its semantic role.
AGUA   = TEAL        # hub / primary
MADERA = NAVY        # flag, alert, secondary series (e.g. self-reported <18)
HONGO  = AQUA        # de-emphasised / below-threshold fill
NEGRO  = NAVY
CIELO  = FOG         # map base fill
AMEBA  = WINE        # median lines, origin->destination arrows
ARBOL  = "#00707a"   # dark teal, third series
MADERA_LIGHT = CREAM
MADERA_MID   = "#e6cdd6"
ARBOL_LIGHT  = MIST
ARBOL_MID    = "#62c8ce"
AGUA_LIGHT   = MIST
AGUA_MID     = "#62c8ce"


def blue_cmap():
    """A continuous light->dark brand-teal colormap for choropleths."""
    from matplotlib.colors import LinearSegmentedColormap
    return LinearSegmentedColormap.from_list("sami_blue", BLUE_SEQ)


def cat_colors(n):
    """First n categorical hues, fixed order (never cycled).

    Past CAT_VALIDATED the returned hues are no longer separable by colour
    alone, so this warns rather than failing silently -- the caller must add
    direct labels or fold the tail into an "Other" series.
    """
    if n > CAT_VALIDATED:
        import warnings
        warnings.warn(
            f"cat_colors({n}): slots {CAT_VALIDATED + 1}-{n} are not separable by "
            "colour alone (CVD ΔE < 8). Direct-label the series or fold into 'Other'.",
            stacklevel=2,
        )
    return CAT[:n]


def seq_colors(n):
    """n evenly-spaced steps of the teal ramp, light->dark."""
    if n <= 1:
        return [BLUE_SEQ[2]]
    idx = np.linspace(0, len(BLUE_SEQ) - 1, n).round().astype(int)
    return [BLUE_SEQ[i] for i in idx]


def mono_cmap(base, light=None):
    """A light->`base` colormap, for tinting one group in a single hue."""
    from matplotlib.colors import LinearSegmentedColormap
    return LinearSegmentedColormap.from_list(
        "sami_mono", [light or MIST, base])


def wordcloud_image(weights, base, width=560, height=340, max_words=45,
                    prefer_horizontal=0.95):
    """Render a term->weight mapping as a single-hue word cloud.

    `weights` must be *distinctive* term scores (c-TF-IDF), never raw counts:
    raw frequency renders the same corpus-wide stopwords in every cloud, and it
    bypasses the distinct-user floor that guards rendered term lists.

    Word size carries the weight; colour is one hue ramped light->`base` by that
    same weight, so colour is redundant with size rather than a second variable.
    Returns a numpy image array for `ax.imshow`.
    """
    from wordcloud import WordCloud
    import pandas as pd

    s = pd.Series(weights).dropna().sort_values(ascending=False).head(max_words)
    if s.empty:
        raise ValueError("wordcloud_image: no terms to render")
    lo, hi = float(s.min()), float(s.max())
    cmap = mono_cmap(base)

    def _color(word, **_):
        t = 0.35 + 0.65 * ((s[word] - lo) / (hi - lo) if hi > lo else 1.0)
        r, g, b, _a = cmap(t)
        return f"rgb({int(r * 255)},{int(g * 255)},{int(b * 255)})"

    wc = WordCloud(width=width, height=height, background_color=SURFACE,
                   prefer_horizontal=0.92, relative_scaling=0.5,
                   max_words=max_words, random_state=0, color_func=_color)
    return wc.generate_from_frequencies(s.to_dict()).to_array()


def pct_count_autopct(values, min_pct=3.0):
    """Pie label 'xx.x%\\n(n)'; blank for slices under min_pct to avoid clutter."""
    total = float(sum(values))

    def _fmt(pct):
        if pct < min_pct:
            return ''
        return f"{pct:.1f}%\n({int(round(pct / 100 * total))})"

    return _fmt


# Legacy categorical bar palette + helper (kept for older cells).
BAR_PALETTE = [BLUES[5], BLUES[2], BLUES[0], BLUES[4], BLUES[1], BLUES[3]]


def bar_colors(n):
    """Return a list of n categorical colours (fixed-order CAT, then a
    ramp fallback if a chart needs more than 10 series)."""
    if n <= len(CAT):
        return CAT[:n]
    extra = seq_colors(n - len(CAT))
    return CAT + extra


plt.rcParams.update({
    'figure.facecolor': SURFACE, 'axes.facecolor': SURFACE,
    'axes.edgecolor': MUTED, 'axes.linewidth': 0.8,
    'text.color': INK, 'axes.labelcolor': INK2, 'axes.titlecolor': INK,
    'axes.titlesize': 12, 'axes.titleweight': 'semibold',
    'axes.titlelocation': 'left', 'axes.titlepad': 10,
    'xtick.color': INK2, 'ytick.color': INK2,
    'axes.grid': False, 'grid.color': GRID, 'grid.linewidth': 0.7,
    'axes.axisbelow': True,
    'axes.spines.top': False, 'axes.spines.right': False,
    'figure.dpi': 110, 'font.size': 10,
})
