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
