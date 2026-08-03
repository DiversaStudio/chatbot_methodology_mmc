import warnings

import pytest

from sami import theme


def test_theme_exposes_palette():
    # palette.py defines brand color constants; at least one categorical list exists
    public = [n for n in dir(theme) if not n.startswith("_")]
    assert public, "theme should expose palette constants"
    # spot-check: a hex color is present somewhere in the module's public values
    values = [getattr(theme, n) for n in public]
    flat = []
    for v in values:
        flat.extend(v if isinstance(v, (list, tuple)) else [v])
    assert any(isinstance(x, str) and x.startswith("#") for x in flat)


def test_cluster_identity_stays_inside_the_validated_range():
    assert theme.K_SOFT_CAP == theme.CAT_VALIDATED == 7
    assert theme.CLUSTER_IDENTITY == theme.CAT[:theme.CAT_VALIDATED]
    assert not hasattr(theme, "ARCHETYPE")


def test_cluster_colors_at_and_below_the_cap_are_validated_and_distinct():
    for n in (1, 6, 7):
        cols = theme.cluster_colors(n)
        assert len(cols) == n
        assert len(set(cols)) == n
        assert set(cols) <= set(theme.CAT[:theme.CAT_VALIDATED])


def test_cluster_colors_never_hands_out_the_reserved_grey():
    """#b7b7b7 belongs to the cluster_id = -1 'No conversation text' bucket."""
    assert theme.NO_TEXT_COLOR == "#b7b7b7"
    for n in (7, 8, 12):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assert theme.NO_TEXT_COLOR not in theme.cluster_colors(n)


def test_cluster_colors_warns_past_the_cap_but_still_returns_n():
    with pytest.warns(UserWarning, match="colour can no longer distinguish"):
        cols = theme.cluster_colors(9)
    assert len(cols) == 9
    assert cols[:7] == theme.CLUSTER_IDENTITY
