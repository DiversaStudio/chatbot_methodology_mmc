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
