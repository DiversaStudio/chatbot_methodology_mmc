"""Map builders for NB1: department choropleth + single-frame Americas flow map.

Reads bundled GeoJSON assets only (no runtime network) so the pipeline is
deterministic and reproducible offline (doc 02 Rule 2). Assets are trimmed
Natural Earth layers committed under src/sami/assets/geo/.
"""
from __future__ import annotations
from pathlib import Path
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import contextily as cx
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable

from . import theme, canon

# A shaded-relief tiled basemap so the shapes read as real geography (terrain,
# coastline, neighbouring countries, ocean) instead of floating on white — the
# Esri WorldShadedRelief tiles are the drop-in equivalent of Basemap's
# .shadedrelief(), but served as tiles that contextily warps onto the data frame.
# Passing crs="EPSG:4326" lets contextily warp the tiles onto the data's own
# lon/lat frame, so no geometry (or arrow centroid) needs reprojecting. A
# transparent labels-only layer rides on top for place names.
_BASEMAP = cx.providers.Esri.WorldShadedRelief
_BASEMAP_LABELS = cx.providers.CartoDB.PositronOnlyLabels


def _add_basemap(ax, labels=True, zorder=-1):
    """Drop a recognizable tiled basemap under whatever is already on `ax`.

    zorder < 0 keeps it beneath the plotted data. Neighbour-country place labels
    then show through the ocean/land around the shapes while the opaque fills hide
    the labels sitting under them.
    """
    cx.add_basemap(ax, crs="EPSG:4326", source=_BASEMAP, attribution=False, zorder=zorder)
    if labels:
        cx.add_basemap(ax, crs="EPSG:4326", source=_BASEMAP_LABELS,
                       attribution=False, zorder=zorder)

# Assets live inside the package so they travel with the code and the
# pipeline stays deterministic + offline.
GEO_DIR = Path(__file__).resolve().parent / "assets" / "geo"
_COLOMBIA = GEO_DIR / "colombia_departments.geojson"
_AMERICAS = GEO_DIR / "americas_countries.geojson"

# Natural Earth admin-0 name for the US differs from the survey vocabulary.
_COUNTRY_ALIASES = {"united states": "United States of America"}


def load_colombia_departments() -> gpd.GeoDataFrame:
    """Colombia departments (admin-1), with a fold-key column for robust joins."""
    gdf = gpd.read_file(_COLOMBIA)
    gdf["dept_key"] = gdf["department"].map(canon.fold)
    return gdf


def load_americas_countries() -> gpd.GeoDataFrame:
    gdf = gpd.read_file(_AMERICAS)
    gdf["name_key"] = gdf["name"].map(canon.fold)
    return gdf


def _country_geom(amer: gpd.GeoDataFrame, name: str):
    key = canon.fold(_COUNTRY_ALIASES.get(canon.fold(name), name))
    hit = amer[amer["name_key"] == key]
    return None if hit.empty else hit.geometry.iloc[0]


def dept_choropleth(ax, counts, cmap=None):
    """Fill Colombia departments by user count.

    counts: dict {department_name -> n} or a pandas Series indexed by department
    (either the canon department name or the Natural Earth name; joined on fold).
    Departments with no users render in the empty surface colour.
    """
    if isinstance(counts, dict):
        counts = pd.Series(counts, dtype="float64")
    keyed = {canon.fold(k): v for k, v in counts.items()}
    gdf = load_colombia_departments()
    gdf["value"] = gdf["dept_key"].map(keyed)

    # Departments with no users stay faintly translucent so the basemap's
    # coastline and neighbours read through them; the shaded ones sit opaque.
    gdf.plot(ax=ax, color=theme.CIELO, edgecolor="white", linewidth=0.4,
             alpha=0.55, zorder=2)  # base
    has = gdf[gdf["value"].notna()]
    vmax = float(gdf["value"].max()) if gdf["value"].notna().any() else 1.0
    norm = Normalize(vmin=0, vmax=vmax)
    cmap = cmap or theme.blue_cmap()
    if not has.empty:
        has.plot(ax=ax, column="value", cmap=cmap, norm=norm,
                 edgecolor="white", linewidth=0.4, zorder=3)
    _add_basemap(ax, labels=True)
    ax.set_axis_off()
    ax.set_aspect("equal")
    sm = ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    return sm


def americas_flow_map(ax, origin, hub, onward, origin_country="Venezuela",
                      hub_country="Colombia"):
    """Single-frame migration map: origin fill, stay-hub fill, onward arrows.

    origin/hub/onward are display strings; onward is a mapping
    {destination_country -> n} used to weight arrow width. Arrows are drawn from
    the hub centroid to each onward-country centroid (excluding the hub itself).
    """
    amer = load_americas_countries()
    # Frame first so the warped basemap tiles fill exactly the map window, then
    # lay the recognizable basemap (coastlines, country labels, ocean) underneath.
    ax.set_xlim(-120, -30)
    ax.set_ylim(-56, 40)
    ax.set_aspect("equal")
    _add_basemap(ax, labels=True)

    def _fill(name, color):
        g = _country_geom(amer, name)
        if g is not None:
            gpd.GeoSeries([g]).plot(ax=ax, color=color, edgecolor="white",
                                    linewidth=0.6, alpha=0.85, zorder=3)
            return g
        return None

    g_origin = _fill(origin_country, theme.AGUA_MID)   # where they come from
    g_hub = _fill(hub_country, theme.PRIMARY)          # where they stay

    hub_c = g_hub.centroid if g_hub is not None else None
    if hub_c is not None and isinstance(onward, dict):
        total = sum(v for k, v in onward.items()
                    if canon.fold(k) != canon.fold(hub_country)) or 1
        for country, n in onward.items():
            if canon.fold(country) == canon.fold(hub_country):
                continue
            g = _country_geom(amer, country)
            if g is None:
                continue
            c = g.centroid
            ax.annotate("", xy=(c.x, c.y), xytext=(hub_c.x, hub_c.y),
                        arrowprops=dict(arrowstyle="-|>", color=theme.AMEBA,
                                        lw=0.8 + 4.0 * n / total, alpha=0.9,
                                        connectionstyle="arc3,rad=0.15"), zorder=5)

    # geopandas .plot autoscaled the axes to the filled countries — restore frame.
    ax.set_xlim(-120, -30)
    ax.set_ylim(-56, 40)
    ax.set_axis_off()
    ax.set_aspect("equal")
