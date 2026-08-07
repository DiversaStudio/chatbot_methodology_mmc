"""Chart shapes matplotlib has no builtin for. Palette lives in `theme`.

Pure matplotlib on purpose: the notebooks here are verified by executing them
with nbconvert and reading the output PNGs, so a chart that only renders in a
live browser session (plotly, bokeh) cannot be checked at all.
"""
from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.path import Path as MplPath
from matplotlib.patches import PathPatch, Rectangle

NODE_WIDTH = 0.02
DEFAULT_GAP = 0.02


def _node_spans(values, gap: float = DEFAULT_GAP):
    """Stack `values` into (y0, y1) bands inside [0, 1], separated by `gap`.

    Bands are proportional to value; the gaps are taken out of the available
    height first so the column always fits, however many nodes there are.
    """
    values = [float(v) for v in values]
    total = sum(values)
    if total <= 0:
        raise ValueError("cannot lay out nodes with zero total value")
    usable = 1.0 - gap * max(len(values) - 1, 0)
    y, spans = 0.0, []
    for v in values:
        h = usable * v / total
        spans.append((y, y + h))
        y += h + gap
    return spans


def _ribbon(x0, x1, y0a, y1a, y0b, y1b, color, alpha=0.72):
    """A cubic-bezier band from span (y0a, y1a) on the left to (y0b, y1b)."""
    cx = (x0 + x1) / 2
    verts = [(x0, y0a), (cx, y0a), (cx, y0b), (x1, y0b),
             (x1, y1b), (cx, y1b), (cx, y1a), (x0, y1a), (x0, y0a)]
    codes = [MplPath.MOVETO, MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4,
             MplPath.LINETO, MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4,
             MplPath.CLOSEPOLY]
    return PathPatch(MplPath(verts, codes), facecolor=color, edgecolor="none",
                      alpha=alpha, label="ribbon")


def sankey_two_level(links, *, color_map, ax=None,
                      left_label="", right_label="", gap=DEFAULT_GAP):
    """Two-column Sankey: `source` on the left, `target` on the right.

    `links` needs columns source, target, value. Ribbon colour is taken from
    `color_map[source]`, so the parent's identity colour carries across.
    """
    if len(links) == 0:
        raise ValueError("no links to draw")
    ax = ax or plt.subplots(figsize=(11, 7))[1]

    src_order = list(dict.fromkeys(links["source"]))
    # dict.fromkeys, not a sorted-by-source column, because a target can be
    # fed by more than one source: sorting by source and taking the target
    # column directly would repeat that target once per incoming link.
    tgt_order = list(dict.fromkeys(links["target"]))
    src_tot = [links.loc[links["source"] == s, "value"].sum() for s in src_order]
    tgt_tot = [links.loc[links["target"] == t, "value"].sum() for t in tgt_order]

    left = dict(zip(src_order, _node_spans(src_tot, gap)))
    right = dict(zip(tgt_order, _node_spans(tgt_tot, gap)))

    x0, x1 = 0.0 + NODE_WIDTH, 1.0 - NODE_WIDTH
    # Ribbons leaving a source must stack to exactly fill that source's band:
    # walk the source's own links in a fixed order and advance a per-source
    # cursor by each ribbon's share, so heights sum to the band with no gap
    # or overflow regardless of how the target side is ordered.
    src_cursor = {s: left[s][0] for s in src_order}
    tgt_cursor = {t: right[t][0] for t in tgt_order}
    for rec in links.to_dict("records"):
        s, t, v = rec["source"], rec["target"], float(rec["value"])
        s_span = left[s][1] - left[s][0]
        h_a = s_span * v / max(src_tot[src_order.index(s)], 1e-9)
        ya0, ya1 = src_cursor[s], src_cursor[s] + h_a
        src_cursor[s] = ya1

        t_span = right[t][1] - right[t][0]
        h_b = t_span * v / max(tgt_tot[tgt_order.index(t)], 1e-9)
        yb0, yb1 = tgt_cursor[t], tgt_cursor[t] + h_b
        tgt_cursor[t] = yb1

        ax.add_patch(_ribbon(x0, x1, ya0, ya1, yb0, yb1, color_map.get(s, "#999999")))

    for name, (y0, y1) in left.items():
        ax.add_patch(Rectangle((0.0, y0), NODE_WIDTH, y1 - y0,
                               color=color_map.get(name, "#999999"), label="node"))
        ax.text(-0.01, (y0 + y1) / 2, name, ha="right", va="center", fontsize=9)
    for name, (y0, y1) in right.items():
        ax.add_patch(Rectangle((1.0 - NODE_WIDTH, y0), NODE_WIDTH, y1 - y0,
                               color="#bbbbbb", label="node"))
        ax.text(1.01, (y0 + y1) / 2, name, ha="left", va="center", fontsize=9)

    ax.set_xlim(-0.32, 1.32)
    ax.set_ylim(-0.02, 1.02)
    ax.axis("off")
    if left_label:
        ax.text(0.0, 1.05, left_label, ha="left", fontsize=10, weight="bold")
    if right_label:
        ax.text(1.0, 1.05, right_label, ha="right", fontsize=10, weight="bold")
    return ax
