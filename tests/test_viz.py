import re
import pandas as pd
import pytest
import matplotlib
matplotlib.use("Agg")
from sami import viz


def test_node_spans_are_ordered_and_non_overlapping():
    spans = viz._node_spans([3, 1, 2])
    assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:]))
    assert all(lo < hi for lo, hi in spans)


def test_node_span_height_is_proportional_to_value():
    spans = viz._node_spans([2, 1], gap=0.0)
    heights = [hi - lo for lo, hi in spans]
    assert heights[0] == pytest.approx(2 * heights[1])


def test_node_spans_fit_inside_the_unit_axis():
    spans = viz._node_spans([5, 3, 1, 1])
    assert spans[0][0] >= 0.0
    assert spans[-1][1] <= 1.0


def test_sankey_draws_one_ribbon_per_link():
    links = pd.DataFrame({"source": ["A", "A", "B"],
                          "target": ["a1", "a2", "b1"],
                          "value": [10, 5, 7]})
    ax = viz.sankey_two_level(links, color_map={"A": "#009ba4", "B": "#671e42"})
    ribbons = [p for p in ax.patches if p.get_label() == "ribbon"]
    assert len(ribbons) == 3


def test_sankey_colours_ribbons_by_source():
    links = pd.DataFrame({"source": ["A", "B"], "target": ["a1", "b1"],
                          "value": [1, 1]})
    ax = viz.sankey_two_level(links, color_map={"A": "#009ba4", "B": "#671e42"})
    ribbons = [p for p in ax.patches if p.get_label() == "ribbon"]
    assert {matplotlib.colors.to_hex(p.get_facecolor()) for p in ribbons} == {
        "#009ba4", "#671e42"}


def test_sankey_rejects_an_empty_link_table():
    with pytest.raises(ValueError, match="no links"):
        viz.sankey_two_level(pd.DataFrame(columns=["source", "target", "value"]),
                             color_map={})


def _right_edge_span(ribbon_patch):
    """The (y0, y1) span a ribbon occupies at its right-hand edge.

    `_ribbon`'s vertex layout puts the right-edge corners at the two points
    with the maximum x -- see viz._ribbon's verts list (indices 3 and 4).
    Reading them back off the patch, rather than trusting the source code
    that built it, is what makes this a real regression test: it asserts on
    the rendered geometry, not on an assumption about how it was produced.
    """
    verts = ribbon_patch.get_path().vertices
    x_max = verts[:, 0].max()
    ys = sorted(y for x, y in verts if x == pytest.approx(x_max))
    return ys[0], ys[-1]


def test_sankey_handles_a_target_fed_by_two_sources():
    # A target with multiple parents must appear exactly once in the target
    # column and its band height must equal the sum of its incoming links --
    # the brief's tgt_order (sorted-by-source) would duplicate it otherwise.
    links = pd.DataFrame({"source": ["A", "B", "A"],
                          "target": ["shared", "shared", "solo"],
                          "value": [10, 5, 3]})
    ax = viz.sankey_two_level(links, color_map={"A": "#009ba4", "B": "#671e42"})
    ribbons = [p for p in ax.patches if p.get_label() == "ribbon"]
    assert len(ribbons) == 3

    nodes = [p for p in ax.patches if p.get_label() == "node"]
    # 2 source nodes + 2 distinct target nodes (not 3, despite 3 links)
    assert len(nodes) == 4


def test_sankey_right_edge_ribbons_partition_a_shared_target_band():
    # The dedup fix (previous test) only checks ribbon/node counts, which
    # stay correct even if the right-side stacking regresses back to
    # `yb0, yb1 = right[t]` for every ribbon landing on "shared" -- that bug
    # makes both ribbons claim the target's *whole* band and overlap, while
    # counts are unaffected. This test reads the actual right-edge y-values
    # off the rendered patches and checks they partition the band: no gap,
    # no overlap, and split in the same 3:1 ratio as the incoming values.
    links = pd.DataFrame({"source": ["A", "B"],
                          "target": ["shared", "shared"],
                          "value": [3, 1]})
    ax = viz.sankey_two_level(links, color_map={"A": "#009ba4", "B": "#671e42"})
    ribbons = [p for p in ax.patches if p.get_label() == "ribbon"]
    assert len(ribbons) == 2

    spans = sorted((_right_edge_span(p) for p in ribbons), key=lambda s: s[0])
    (lo_a, hi_a), (lo_b, hi_b) = spans

    # contiguous, no gap and no overlap
    assert hi_a == pytest.approx(lo_b)
    # the whole shared band -- the target's own node span -- is used exactly
    target_lo, target_hi = viz._node_spans([4])[0]
    assert lo_a == pytest.approx(target_lo)
    assert hi_b == pytest.approx(target_hi)
    # split proportionally to the incoming values (3:1)
    assert (hi_a - lo_a) == pytest.approx(3 * (hi_b - lo_b))


def test_node_spans_rejects_a_gap_too_large_for_the_node_count():
    with pytest.raises(ValueError, match="51"):
        viz._node_spans([1] * 51, gap=0.02)
