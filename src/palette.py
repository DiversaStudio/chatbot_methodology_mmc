# Diversa brand color palette
# Primary (external comms — logo, papelería)
AGUA   = "#6182d9"
MADERA = "#8f8f78"
HONGO  = "#e0dedb"
NEGRO  = "#000000"

# Secondary (web, illustrations, social)
CIELO  = "#f0f0f0"
AMEBA  = "#d6a8eb"
ARBOL  = "#6e824a"

# Extended (multi-illustration scenes, max 4 colors)
MADERA_LIGHT = "#F7F5EF"
MADERA_MID   = "#D0D2A5"
ARBOL_LIGHT  = "#E6EED5"
ARBOL_MID    = "#D0D2A5"
AGUA_LIGHT   = "#E2EBEC"
AGUA_MID     = "#B3C3DC"

# Blue ramp used for all chart series (light -> dark)
BLUES = ["#DFE3F0", "#C5CFEB", "#A2B4E5", "#90A6E1", "#7692DC", "#6D8BDB"]

import matplotlib.pyplot as plt

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.edgecolor": NEGRO,
    "axes.labelcolor": NEGRO,
    "text.color": NEGRO,
    "xtick.color": NEGRO,
    "ytick.color": NEGRO,
    "axes.spines.top": False,
    "axes.spines.right": False,
})

# Fixed sequence used to give every bar of a categorical bar/barh chart a
# distinct shade of the blue ramp. Ordered so adjacent bars alternate
# dark/light and stay distinguishable within one hue family. `bar_colors(n)`
# cycles through it, repeating if a chart has more bars than colors.
BAR_PALETTE = [BLUES[5], BLUES[2], BLUES[0], BLUES[4], BLUES[1], BLUES[3]]


def bar_colors(n):
    """Return a list of n colors, cycling through BAR_PALETTE."""
    return [BAR_PALETTE[i % len(BAR_PALETTE)] for i in range(n)]
