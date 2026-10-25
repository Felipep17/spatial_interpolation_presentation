"""Mapa base común (cámara, mapas base, controles y estilos) y capas de barrios y de comunas."""

import folium
import geopandas as gpd
import numpy as np
import shapely
import streamlit as st
from branca.element import Element, MacroElement
from folium.plugins import Fullscreen
from jinja2 import Template

from geoclima.ui.i18n import t, t_comuna
from geoclima.ui.tema import BARRIO_LINE, COLORS, FONT_STACK, FONT_URL, SAT_URL, TILES_ATTR, TILES_URL

# Cámara compartida por todos los mapas: mismo centro y zoom => sin saltos al cambiar de fuente
MAP_ZOOM = 11.75

# Geometría para dibujar: simplificada a ~1 m y con coordenadas de 6 decimales (~0.1 m). No se nota en el mapa y
# baja el GeoJSON de barrios de ~2.7 MB a ~0.4 MB, que se arma y se envía al navegador en cada interacción.
# Las estadísticas zonales y los clics siguen usando la geometría original.
TOLERANCIA_MAPA = 1e-5


MAP_CSS = f"""
<link href="{FONT_URL}" rel="stylesheet">
<style>
  html, body, .leaflet-container {{ font-family: {FONT_STACK}; background: {COLORS["page"]}; }}
  .leaflet-container {{ border-radius: 12px; }}
  .leaflet-control-attribution {{ font-size: 10px; background: rgba(252,252,251,.8) !important; }}
  .leaflet-control-scale-line {{ font-size: 10px; line-height: 1.3; padding: 0 4px; color: {COLORS["ink_2"]};
      background: rgba(252,252,251,.8); border-color: {COLORS["ink_2"]}; }}
  .leaflet-bar, .leaflet-control-layers {{
      border: 1px solid {COLORS["grid"]} !important; border-radius: 8px !important;
      box-shadow: 0 2px 8px rgba(11,11,11,.06) !important;
  }}
  .leaflet-bar a {{ color: {COLORS["ink_2"]} !important; }}
  .leaflet-control-layers-expanded {{ padding: 8px 10px; font-size: 12px; color: {COLORS["ink_2"]}; }}
  .leaflet-bar-timecontrol {{ background: {COLORS["surface"]}; }}
  .leaflet-bar-timecontrol .timecontrol-date {{ font: 600 12px {FONT_STACK}; color: {COLORS["ink"]}; }}

  .gc-panel {{
      position: absolute; top: 12px; left: 56px; z-index: 1000; width: 248px;
      background: {COLORS["surface"]}; color: {COLORS["ink"]};
      border: 1px solid {COLORS["grid"]}; border-radius: 12px;
      box-shadow: 0 8px 24px rgba(11,11,11,.08); padding: 14px 14px 12px; font-size: 12.5px;
  }}
  .gc-panel-title {{ font-size: 11px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase;
      color: {COLORS["muted"]}; margin-bottom: 8px; cursor: pointer; list-style: none;
      display: flex; justify-content: space-between; align-items: center; user-select: none; }}
  .gc-panel-title::-webkit-details-marker {{ display: none; }}
  .gc-panel-title::after {{ content: "▾"; font-size: 12px; transition: transform .15s ease; }}
  .gc-panel:not([open]) {{ padding-bottom: 6px; width: auto; }}
  .gc-panel:not([open]) .gc-panel-title {{ margin-bottom: 0; gap: 10px; }}
  .gc-panel:not([open]) .gc-panel-title::after {{ transform: rotate(-90deg); }}

  /* Móvil: sin botones de zoom (se usa el gesto), panel compacto y control temporal ajustado */
  @media (max-width: 640px) {{
      .leaflet-control-zoom {{ display: none; }}
      .leaflet-control-scale {{ display: none; }}
      .gc-panel {{ left: 8px; top: 8px; width: auto; max-width: calc(100% - 64px); padding: 10px 12px; font-size: 12px; }}
      .gc-panel[open] {{ max-height: calc(100% - 90px); overflow-y: auto; }}
      .gc-seg label {{ font-size: 11px; padding: 5px 2px; }}
      .gc-readout-big {{ font-size: 15px; }}
      .leaflet-bar-timecontrol {{ max-width: calc(100vw - 20px); }}
      .leaflet-bar-timecontrol .timecontrol-speed,
      .leaflet-bar-timecontrol .timecontrol-loop {{ display: none !important; }}
      .leaflet-bar-timecontrol .timecontrol-slider .slider {{ width: 90px !important; }}
      .leaflet-bar-timecontrol .timecontrol-date {{ min-width: 0 !important; padding: 0 6px !important; font-size: 11px !important; }}
      .leaflet-control-attribution {{ font-size: 8px; max-width: 60%; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  }}
  .gc-seg {{ display: flex; background: {COLORS["surface_alt"]}; border-radius: 8px; padding: 3px; gap: 2px; margin-bottom: 12px; }}
  .gc-seg label {{ flex: 1; text-align: center; cursor: pointer; padding: 5px 4px; border-radius: 6px;
      font-size: 11.5px; font-weight: 500; color: {COLORS["ink_2"]}; transition: all .15s ease; }}
  .gc-seg input {{ display: none; }}
  .gc-seg label:has(input:checked) {{ background: {COLORS["surface"]}; color: {COLORS["ink"]};
      box-shadow: 0 1px 3px rgba(11,11,11,.12); }}
  .gc-legend {{ margin-bottom: 10px; }}
  .gc-legend-title {{ font-size: 12px; font-weight: 600; color: {COLORS["ink"]}; margin-bottom: 5px; }}
  .gc-legend-title span {{ font-weight: 400; color: {COLORS["muted"]}; }}
  .gc-legend-bar {{ height: 10px; border-radius: 3px; }}
  .gc-legend-ticks {{ display: flex; justify-content: space-between; font-size: 10.5px; color: {COLORS["ink_2"]};
      margin-top: 3px; font-variant-numeric: tabular-nums; }}
  .gc-legend-note {{ font-size: 10px; color: {COLORS["muted"]}; margin-top: 2px; }}
  .gc-readout {{ border-top: 1px solid {COLORS["grid"]}; padding-top: 9px; margin-top: 2px; }}
  .gc-readout-row {{ display: flex; justify-content: space-between; align-items: baseline; gap: 8px; padding: 2px 0; }}
  .gc-readout-row span:first-child {{ color: {COLORS["muted"]}; font-size: 11.5px; }}
  .gc-readout-row span:last-child {{ font-weight: 600; text-align: right; font-variant-numeric: tabular-nums; }}
  .gc-readout-big {{ font-size: 18px; font-weight: 700; letter-spacing: -.01em; }}
  .gc-anim {{
      position: absolute; left: 12px; bottom: 46px; z-index: 1000; display: flex; align-items: center; gap: 6px;
      background: {COLORS["surface"]}; border: 1px solid {COLORS["grid"]}; border-radius: 10px;
      box-shadow: 0 8px 24px rgba(11,11,11,.08); padding: 6px 10px; max-width: calc(100% - 24px);
  }}
  .gc-anim button {{
      border: 1px solid {COLORS["grid"]}; background: {COLORS["surface_alt"]}; color: {COLORS["ink"]};
      border-radius: 6px; min-width: 30px; height: 28px; font: 600 13px {FONT_STACK}; cursor: pointer; padding: 0 8px;
  }}
  .gc-anim button:hover {{ background: {COLORS["grid"]}; }}
  .gc-anim button.gc-play {{ background: {COLORS["accent"]}; border-color: {COLORS["accent"]}; color: #fff; }}
  .gc-anim input[type=range] {{ width: 220px; accent-color: {COLORS["accent"]}; }}
  .gc-anim-fecha {{ font: 600 12.5px {FONT_STACK}; color: {COLORS["ink"]}; min-width: 92px; text-align: center;
      font-variant-numeric: tabular-nums; }}
  .gc-anim-n {{ font-size: 11px; color: {COLORS["muted"]}; white-space: nowrap; }}
  @media (max-width: 640px) {{
      .gc-anim {{ left: 8px; bottom: 18px; gap: 4px; padding: 5px 6px; }}
      .gc-anim input[type=range] {{ width: 90px; }}
      .gc-anim-n {{ display: none; }}
  }}
  .gc-tooltip {{ font-family: {FONT_STACK}; font-size: 12px; border-radius: 8px !important;
      border: 1px solid {COLORS["grid"]} !important; box-shadow: 0 4px 14px rgba(11,11,11,.08) !important; }}
  /* Valores largos (lista de estaciones de una celda) en varias líneas; max-content porque el panel no tiene ancho */
  .leaflet-tooltip.gc-tooltip {{ white-space: normal; width: max-content; max-width: 280px; }}
  .gc-tooltip th {{ white-space: nowrap; vertical-align: top; }}
</style>
"""


class ScriptMapa(MacroElement):
    """JS que se ejecuta después de crear el mapa y sus capas (sin polling)."""

    _template = Template("{% macro script(this, kwargs) %}{{ this.js }}{% endmacro %}")

    def __init__(self, js: str):
        super().__init__()
        self._name = "ScriptMapa"
        self.js = js


def mapa_base(gdf, height: int | str = "100%", controles: bool = True, lang: str | None = None) -> folium.Map:
    """Mapa con fondo y cámara idénticos en toda la aplicación (textos de controles en `lang`)."""
    minx, miny, maxx, maxy = [float(v) for v in gdf.total_bounds]
    margen = 0.35
    m = folium.Map(
        location=[(miny + maxy) / 2, (minx + maxx) / 2],
        zoom_start=MAP_ZOOM,
        zoom_snap=0.25,
        zoom_delta=0.5,
        min_zoom=10,
        max_zoom=19,  # edificios visibles desde z16
        max_bounds=True,
        min_lat=miny - margen,
        max_lat=maxy + margen,
        min_lon=minx - margen,
        max_lon=maxx + margen,
        tiles=None,
        width="100%",
        height=height,
        control_scale=controles,
        zoom_control=controles,
    )
    # Mapas base alternables desde el control de capas (OSM por defecto)
    folium.TileLayer(TILES_URL, attr=TILES_ATTR, name=t("mapa.calles", lang),
                     max_native_zoom=19, max_zoom=19).add_to(m)
    folium.TileLayer(SAT_URL, attr=t("mapa.sat_attr", lang), name=t("mapa.satelite", lang), show=False,
                     max_native_zoom=18, max_zoom=19).add_to(m)
    if controles:
        Fullscreen(position="topleft", title=t("mapa.pantalla_completa", lang),
                   title_cancel=t("mapa.salir_pantalla", lang)).add_to(m)
    m.get_root().header.add_child(Element(MAP_CSS))
    return m


@st.cache_data(show_spinner=False)
def _geometria_mapa(_geoms, firma: tuple) -> np.ndarray:
    simple = shapely.simplify(np.asarray(_geoms), TOLERANCIA_MAPA, preserve_topology=True)
    return shapely.transform(simple, lambda c: np.round(c, 6))


def para_mapa(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Copia de la capa con la geometría liviana para dibujar (mismas filas, mismo orden)."""
    geoms = gdf.geometry.values
    firma = (len(geoms), int(shapely.get_num_coordinates(geoms).sum()), *np.round(gdf.total_bounds, 6))
    return gdf.assign(geometry=gpd.GeoSeries(_geometria_mapa(geoms, firma), index=gdf.index, crs=gdf.crs))


@st.cache_data(show_spinner=False)
def _comunas_geojson(_gdf_b, n: int) -> str:
    comunas = _gdf_b[["comuna", "geometry"]].dissolve("comuna").reset_index()
    comunas["geometry"] = comunas.geometry.simplify(0.00005)
    return comunas.to_json()


def capa_comunas(gdf_b, show: bool = False, lang: str | None = None) -> folium.GeoJson:
    """Límites de comuna (disolución de barrios), sin interacción para no tapar el hover de los barrios."""
    return folium.GeoJson(
        _comunas_geojson(gdf_b, len(gdf_b)), name=t("mapa.limites_comuna", lang), show=show, interactive=False,
        style_function=lambda f: {"fillOpacity": 0, "color": COLORS["ink"], "weight": 1.8, "opacity": 0.85},
    )


def control_capas(m: folium.Map) -> folium.Map:
    """Control de mapas base y capas. Se agrega al final: su JS referencia capas ya creadas."""
    folium.LayerControl(position="topright", collapsed=True).add_to(m)
    return m


def capa_barrios(gdf_b, con_pixeles: bool = True, alias_pixeles: str | None = None,
                 lang: str | None = None) -> folium.GeoJson:
    campos = ["nombre_barrio", "comuna", "n_pixeles"] if con_pixeles else ["nombre_barrio", "comuna"]
    alias = [t("gen.barrio", lang), t("gen.comuna", lang)]
    if con_pixeles:
        alias.append(alias_pixeles or t("mapa.pixeles", lang))
    datos = para_mapa(gdf_b[["b_id"] + campos + ["geometry"]]).assign(
        comuna=gdf_b["comuna"].map(lambda c: t_comuna(c, lang)))
    return folium.GeoJson(
        datos,
        name=t("mapa.limites_barrio", lang),
        show=True,
        style_function=lambda x: {
            "fillColor": COLORS["ink"],
            "fillOpacity": 0.0,
            **BARRIO_LINE,
        },
        highlight_function=lambda x: {
            "weight": 2,
            "color": COLORS["accent_dark"],
            "fillOpacity": 0.06,
            "fillColor": COLORS["accent"],
        },
        tooltip=folium.GeoJsonTooltip(fields=campos, aliases=alias, sticky=True, class_name="gc-tooltip"),
    )
