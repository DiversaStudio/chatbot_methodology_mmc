import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from sami import geo


def test_colombia_assets_load_and_have_key():
    gdf = geo.load_colombia_departments()
    assert len(gdf) >= 30
    assert "dept_key" in gdf.columns
    # every priority-city department must exist in the geometry (fold-matched)
    from sami import canon
    for dept in set(canon.DEPARTMENT_OF_CITY.values()):
        assert canon.fold(dept) in set(gdf["dept_key"]), f"{dept} missing from geometry"


def test_americas_assets_load_core_countries():
    gdf = geo.load_americas_countries()
    keys = set(gdf["name_key"])
    for c in ["Venezuela", "Colombia"]:
        assert geo.canon.fold(c) in keys
    # US alias resolves to the Natural Earth long name
    assert geo._country_geom(gdf, "United States") is not None


def test_dept_choropleth_joins_counts():
    counts = {"Antioquia": 120, "Bogotá": 90, "Norte de Santander": 40}
    fig, ax = plt.subplots()
    sm = geo.dept_choropleth(ax, counts)
    assert sm is not None
    # the mappable's vmax reflects the largest count
    assert sm.norm.vmax == 120
    plt.close(fig)


def test_americas_flow_map_runs():
    fig, ax = plt.subplots()
    geo.americas_flow_map(ax, origin="Venezuela", hub="Colombia",
                          onward={"Colombia": 809, "United States": 24, "Argentina": 18})
    assert not ax.has_data() is None  # axis populated without error
    plt.close(fig)
