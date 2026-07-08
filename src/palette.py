# Diversa brand color palette + shared chart design system.
#
# Two layers live here:
#   1. The Diversa BRAND colours (AGUA, MADERA, ...) used by illustration-style
#      semantic palettes (e.g. the MMC category colours in analysis_responses).
#   2. A general CHART design system (CAT / BLUE_SEQ + helpers) matching the EDA
#      notebooks: a fixed-order categorical palette for identity charts and a
#      light->dark blue ramp for ordered magnitude. Colour comes last; text and
#      surfaces stay neutral so they never compete with the data marks.
#
# Old names (BLUES, bar_colors, NEGRO, CIELO, ...) are kept as aliases so
# existing notebooks keep working unchanged.

import numpy as np
import matplotlib.pyplot as plt

# --- Diversa brand colours (unchanged) -------------------------------------
AGUA   = "#6182d9"
MADERA = "#8f8f78"
HONGO  = "#e0dedb"
NEGRO  = "#000000"
CIELO  = "#f0f0f0"
AMEBA  = "#d6a8eb"
ARBOL  = "#6e824a"
MADERA_LIGHT = "#F7F5EF"
MADERA_MID   = "#D0D2A5"
ARBOL_LIGHT  = "#E6EED5"
ARBOL_MID    = "#D0D2A5"
AGUA_LIGHT   = "#E2EBEC"
AGUA_MID     = "#B3C3DC"

# --- Chart design system (Diversa brand) ------------------------------------
# Diversa brand blue ramp (light -> dark) -- the sequential ramp for ordered
# magnitude (durations, ratings, missingness, cohorts).
BLUE_SEQ = ["#DFE3F0", "#C5CFEB", "#A2B4E5", "#90A6E1", "#7692DC", "#6D8BDB"]
BLUES = BLUE_SEQ                                    # backwards-compatible alias

# Diversa brand earth ramp (light -> dark) -- second colour family.
EARTH = ["#e0dedb", "#d0d2a5", "#b5b797", "#8f8f78", "#6e824a"]

# Categorical hues (identity), assigned in this FIXED order, never cycled.
# Alternates the blue and earth families so adjacent slices/bars stay
# distinguishable while every colour stays on-brand.
CAT = ['#6D8BDB', '#8f8f78', '#A2B4E5', '#6e824a', '#7692DC',
       '#d0d2a5', '#90A6E1', '#b5b797', '#C5CFEB', '#e0dedb']
PRIMARY = '#6D8BDB'                                 # single-series brand blue

# Neutrals: text inks, grid, surface.
INK, INK2, MUTED = '#0b0b0b', '#52514e', '#898781'
GRID, SURFACE    = '#e6e5df', '#ffffff'


def cat_colors(n):
    """First n categorical hues, fixed order (never cycled)."""
    return CAT[:n]


def seq_colors(n):
    """n evenly-spaced steps of the blue ramp, light->dark."""
    if n <= 1:
        return [BLUE_SEQ[2]]
    idx = np.linspace(0, len(BLUE_SEQ) - 1, n).round().astype(int)
    return [BLUE_SEQ[i] for i in idx]


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
    """Return a list of n categorical colours (fixed-order CAT, then a blue
    ramp fallback if a chart needs more than 8 series)."""
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
