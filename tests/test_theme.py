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


def test_cluster_colors_are_always_distinct():
    """BLUE_SEQ shares three literal hexes with CAT (#009ba4, #62c8ce, #a6dfe3),
    all three inside CLUSTER_IDENTITY. Naively concatenating CLUSTER_IDENTITY with
    seq_colors() therefore reissues colours already handed out at n=8, 10 and 12 --
    two structurally different clusters would get the identical color_hex in
    dim_cluster, not merely a harder-to-separate one. Every n from 1 to 12 must
    come back with n distinct colours, and NO_TEXT_COLOR must never be among them."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for n in range(1, 13):
            cols = theme.cluster_colors(n)
            assert len(cols) == n
            assert len(set(cols)) == n, f"n={n}: duplicates {cols}"
            assert theme.NO_TEXT_COLOR not in cols


def test_cluster_colors_terminates_on_an_absurd_request():
    """An n past the reachable colour space raises instead of hanging.

    The past-the-cap hue walk draws from a finite set: at fixed saturation and
    value the wheel quantises to a few hundred 8-bit hexes. Without a bound the
    loop would spin forever hunting a colour that does not exist, and the
    pipeline would appear to stall with no output. Unreachable in practice --
    `choose_k` caps k at 12 -- so this test guards the failure mode, not a
    real code path.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with pytest.raises(ValueError, match="fold the tail"):
            theme.cluster_colors(5000)


def test_cluster_colors_is_deterministic_across_calls():
    """color_hex is exported data, so the same n must always give the same list."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert theme.cluster_colors(12) == theme.cluster_colors(12)
        assert theme.cluster_colors(9)[:7] == theme.CLUSTER_IDENTITY
