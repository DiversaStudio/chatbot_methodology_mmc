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


def _sample_frame():
    return pd.DataFrame({
        "cluster_id": [0, 0, 1], "subcluster_id": [0, 1, 10],
        "subcluster_name": ["Starting a business", "Looking for work", "Biometrics"],
        "sentiment_label": ["negative", "positive", "neutral"],
        "city_canon": ["Cucuta", "Bogota", "Cali"],
        "text_redacted": ["a", "b", "c"],
    })


def test_filter_examples_filters_by_tone():
    out = viz.filter_examples(_sample_frame(), tone="negative")
    assert set(out["sentiment_label"]) == {"negative"}


def test_filter_examples_filters_by_subcluster():
    out = viz.filter_examples(_sample_frame(), subcluster=10)
    assert set(out["subcluster_id"]) == {10}


def test_filter_examples_combines_filters_and_caps_rows():
    out = viz.filter_examples(_sample_frame(), cluster=0, n=1)
    assert len(out) == 1
    assert set(out["cluster_id"]) == {0}


def test_filter_examples_with_no_filters_returns_everything_up_to_n():
    assert len(viz.filter_examples(_sample_frame())) == 3


def test_filter_examples_composes_tone_cluster_and_subcluster_together():
    # The brief claims the three filters compose; every existing test only
    # exercises one (or one plus the row cap) at a time, so a regression that
    # silently ORs instead of ANDs the conditions would go undetected.
    df = pd.concat([_sample_frame(), pd.DataFrame({
        "cluster_id": [0], "subcluster_id": [1],
        "subcluster_name": ["Looking for work"],
        "sentiment_label": ["negative"],
        "city_canon": ["Medellin"],
        "text_redacted": ["d"],
    })], ignore_index=True)
    out = viz.filter_examples(df, tone="negative", cluster=0, subcluster=1)
    assert len(out) == 1
    assert out.loc[0, "text_redacted"] == "d"


def test_style_examples_colours_the_tone_column():
    from sami import theme
    styled = viz.style_examples(_sample_frame())
    rendered = styled.to_html()
    assert theme.TONE["negative"]["fill"] in rendered


def test_style_examples_leaves_every_other_column_unfilled():
    # Stakeholder was explicit: ONLY tone is coloured. pandas 3.x emits every
    # CSS rule inside a <style> block BEFORE the table, keyed by id selectors
    # like #T_<hash>_row<r>_col<c> -- cells never carry an inline style=, so
    # a <tbody>-only search can never see "background-color" at all and any
    # assertion built on that fragment is vacuous regardless of what
    # style_examples does (proved by mutation-testing this exact test: a
    # broken implementation that fills every column still passes it). Search
    # the <style> block instead and assert on the SELECTORS: every
    # background-color rule must target col0 (sentiment_label) and no other
    # column index, with one rule per row.
    df = _sample_frame()
    rendered = viz.style_examples(df).to_html()
    style_block = rendered.split("<style", 1)[1].split("</style>", 1)[0]
    rules = re.findall(r"([^{}]+)\{([^{}]+)\}", style_block)

    fill_selectors = []
    for selector, decl in rules:
        if "background-color" in decl:
            fill_selectors.extend(s.strip() for s in selector.split(","))

    assert fill_selectors, "expected at least one background-color rule"
    assert all(re.search(r"_col0$", s) for s in fill_selectors), fill_selectors
    assert len(fill_selectors) == len(df)


def test_style_examples_raises_a_clear_error_when_tone_column_is_missing():
    # style_examples' whole point is colouring sentiment_label; selecting
    # EXAMPLE_COLUMNS present in the frame and then subsetting the Styler on
    # "sentiment_label" regardless would raise a bare pandas KeyError with no
    # indication of which column was expected -- naming it explicitly here
    # is a deliberate, legible failure instead of an accidental one.
    df = _sample_frame().drop(columns=["sentiment_label"])
    with pytest.raises(KeyError, match="sentiment_label"):
        viz.style_examples(df)
