import json
import warnings
from pathlib import Path

import folium
import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
import streamlit as st
import xarray as xr
from branca.element import Element, MacroElement
from folium.plugins import Fullscreen, TimestampedGeoJson
from jinja2 import Template

from components.i18n import locale_js, t, t_comuna
from components.theme import (
    COLORS,
    FONT_STACK,
    FONT_URL,
    RASTER_VARS,
    BARRIO_LINE,
    RASTER_OPACITY,
    SAT_URL,
    TILES_ATTR,
    TILES_URL,
    VarSpec,
    colormap,
    escala_robusta,
    leyenda_html,
)

# Cámara compartida por todos los mapas: mismo centro y zoom => sin saltos al cambiar de fuente
MAP_ZOOM = 11.75


# =========================================================================
# Carga de datos
# =========================================================================
@st.cache_data
def cargar_shapefile(carpeta: Path):
    formatos = ["*.parquet", "*.shp", "*.geojson", "*.gpkg"]
    arch = None
    for fmt in formatos:
        hits = sorted(carpeta.glob(fmt))
        if hits:
            arch = hits[0]
            break
    if not arch:
        raise FileNotFoundError(f"Sin vectores en {carpeta}")
    gdf = gpd.read_parquet(arch) if arch.suffix == ".parquet" else gpd.read_file(arch)
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    return gdf


# Orden de presentación de las fuentes; las no listadas van al final en orden alfabético
ORDEN_FUENTES = ["C3S", "CHIRPS", "MSWEP", "GEE"]


def listar_fuentes(raster_dir: Path):
    fuentes = {}
    if raster_dir.exists():
        carpetas = [p for p in raster_dir.iterdir() if p.is_dir()]
        orden = {n: i for i, n in enumerate(ORDEN_FUENTES)}
        for d in sorted(carpetas, key=lambda c: (orden.get(c.name.upper(), len(orden)), c.name)):
            fuentes[d.name] = sorted(list(d.glob("*.nc")) + list(d.glob("*.tif")))
    return fuentes


def cargar_recorte_nc(nc_path: Path, bounds, res=0.1):
    minx, miny, maxx, maxy = bounds
    pad = res / 2
    with xr.open_dataset(nc_path) as ds:
        vars_validas = [
            v for v in ds.data_vars if len(ds[v].dims) >= 2 and v not in ["spatial_ref", "crs"]
        ]
        var_name = vars_validas[0] if vars_validas else list(ds.data_vars)[0]
        da = ds[var_name]
        lat_col = next(
            c for c in list(da.coords) + list(da.dims) if c.lower() in ["latitude", "lat", "y"]
        )
        lon_col = next(
            c for c in list(da.coords) + list(da.dims) if c.lower() in ["longitude", "lon", "x"]
        )
        lon_0_360 = float(ds[lon_col].min()) >= 0 and minx < 0
        minx_s, maxx_s = (minx + 360, maxx + 360) if lon_0_360 else (minx, maxx)
        lat_slice = (
            slice(maxy + pad, miny - pad)
            if da[lat_col].values[0] > da[lat_col].values[-1]
            else slice(miny - pad, maxy + pad)
        )
        lon_slice = slice(minx_s - pad, maxx_s + pad)
        da = da.sel({lat_col: lat_slice, lon_col: lon_slice}).load()
    if lon_0_360:
        da = da.assign_coords({lon_col: da[lon_col] - 360})
    if (
        "temp" in var_name.lower()
        or "t2m" in var_name.lower()
        or "mx2t" in var_name.lower()
    ) and float(da.mean().values) > 100:
        da = da - 273.15
    return da, lat_col, lon_col, pad


def cargar_grilla_nc(nc_path: Path, var: str | None = None):
    """NetCDF ya recortado (CHIRPS, MSWEP, GEE): variable, centros de píxel y medio paso."""
    with xr.open_dataset(nc_path) as ds:
        if var is None:
            var = next(v for v in ds.data_vars if len(ds[v].dims) >= 2 and v not in ("spatial_ref", "crs"))
        da_p = ds[var].load()
    lat_col = "lat" if "lat" in da_p.coords else "latitude"
    lon_col = "lon" if "lon" in da_p.coords else "longitude"
    # float64 y redondeo: algunos productos (MSWEP) guardan coordenadas float32 con ruido
    lats = np.round(da_p[lat_col].values.astype(float), 6)
    lons = np.round(da_p[lon_col].values.astype(float), 6)
    pad = (
        abs(float(lats[1] - lats[0])) / 2.0
        if len(lats) > 1
        else abs(float(lons[1] - lons[0])) / 2.0
    )
    return da_p, lats, lons, pad


# =========================================================================
# Estadísticas zonales (promedio de píxeles que intersectan cada barrio)
# =========================================================================
def comuna_de(codigo) -> str:
    """Comuna a partir del código de barrio de Planeación Municipal (CCBB): 01–22 o 81 (área de expansión)."""
    cc = str(codigo)[:2]
    if cc == "81":
        return "Área de expansión"
    return f"Comuna {int(cc)}" if cc.isdigit() and 1 <= int(cc) <= 22 else "Sin comuna"


def preparar_barrios(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf_b = gdf.copy()
    col_nombre = next((c for c in gdf_b.columns if c.lower() == "nombre"), gdf_b.columns[0])
    gdf_b["b_id"] = np.arange(len(gdf_b))
    gdf_b["nombre_barrio"] = gdf_b[col_nombre].astype(str)
    gdf_b["comuna"] = gdf_b["id_sector"].map(comuna_de) if "id_sector" in gdf_b else "Sin comuna"
    return gdf_b


def barrio_en_clic(gdf_b, valor_mapa) -> str | None:
    """Barrio que contiene el punto clicado en un mapa de st_folium (`last_clicked`), o None.

    Se usa la coordenada y no el elemento SVG: un clic sobre el límite entre dos barrios puede
    caer en el grupo SVG y Leaflet lo reporta como clic en el mapa base, no en el barrio.
    """
    punto = (valor_mapa or {}).get("last_clicked")
    if not punto:
        return None
    dentro = gdf_b.geometry.contains(shapely.Point(punto["lng"], punto["lat"]))
    return gdf_b.loc[dentro, "nombre_barrio"].iat[0] if dentro.any() else None


def orden_comunas(comunas) -> list[str]:
    """Comuna 1 … Comuna 22 en orden numérico y el área de expansión al final."""
    def clave(c):
        partes = c.split()
        return (0, int(partes[-1])) if partes[-1].isdigit() else (1, c)
    return sorted(set(comunas), key=clave)


def _pixeles_por_barrio(gdf_b, lats, lons, pad):
    """Índices planos (i * n_lon + j) de los píxeles que intersectan cada barrio (STRtree)."""
    ii, jj = np.divmod(np.arange(len(lats) * len(lons)), len(lons))
    cajas = shapely.box(lons[jj] - pad, lats[ii] - pad, lons[jj] + pad, lats[ii] + pad)
    barrio_idx, pixel_idx = shapely.STRtree(cajas).query(
        gdf_b.geometry.values, predicate="intersects"
    )
    orden = np.argsort(barrio_idx, kind="stable")
    cortes = np.cumsum(np.bincount(barrio_idx, minlength=len(gdf_b)))[:-1]
    return np.split(pixel_idx[orden], cortes)


def _series_zonales(arr: np.ndarray, por_barrio, decimales: int):
    plano = arr.reshape(arr.shape[0], -1)
    series = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)  # barrios sin píxeles válidos
        for idx in por_barrio:
            medias = np.nanmean(plano[:, idx], axis=1) if len(idx) else np.full(arr.shape[0], np.nan)
            series.append([None if np.isnan(v) else round(float(v), decimales) for v in medias])
    return series


def estadisticas_zonales(gdf: gpd.GeoDataFrame, arrays: dict, lats, lons, pad, decimales: int = 1):
    """Devuelve (gdf preparado con n_pixeles, lista de dicts por barrio con una serie por variable)."""
    gdf_b = preparar_barrios(gdf)
    por_barrio = _pixeles_por_barrio(gdf_b, lats, lons, pad)
    series = {k: _series_zonales(np.asarray(a, dtype=float), por_barrio, decimales) for k, a in arrays.items()}
    stats = [
        {"id": int(k), "nom": nom, "n_pix": int(len(por_barrio[k])), **{v: series[v][k] for v in arrays}}
        for k, nom in enumerate(gdf_b["nombre_barrio"])
    ]
    gdf_b["n_pixeles"] = [s["n_pix"] for s in stats]
    return gdf_b, stats


def calcular_estadisticas_zonales(gdf, da_rh, da_t, lat_col, lon_col, pad):
    lats = da_rh[lat_col].values
    lons = da_rh[lon_col].values
    time_vals = pd.to_datetime(da_rh.time.values)
    gdf_b, stats = estadisticas_zonales(gdf, {"rh": da_rh.values, "t": da_t.values}, lats, lons, pad)
    return gdf_b, stats, time_vals, lats, lons


# =========================================================================
# Construcción de mapas
# =========================================================================
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
  .gc-tooltip {{ font-family: {FONT_STACK}; font-size: 12px; border-radius: 8px !important;
      border: 1px solid {COLORS["grid"]} !important; box-shadow: 0 4px 14px rgba(11,11,11,.08) !important; }}
</style>
"""


class _ScriptMapa(MacroElement):
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
    datos = gdf_b[["b_id"] + campos + ["geometry"]].assign(comuna=gdf_b["comuna"].map(lambda c: t_comuna(c, lang)))
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


def _periodo(time_vals):
    if len(time_vals) > 1:
        dt_hours = max(1, int((time_vals[1] - time_vals[0]).total_seconds() / 3600))
        period = f"P{dt_hours // 24}D" if dt_hours >= 24 else f"PT{dt_hours}H"
        fmt = "YYYY-MM-DD" if dt_hours >= 24 else "YYYY-MM-DD HH:mm"
        return period, fmt
    return "P1D", "YYYY-MM-DD"


def _features_pixeles(arr, lats, lons, pad, time_vals, cm, opacidad):
    feats = []
    for t_idx, fecha in enumerate(time_vals):
        iso = fecha.isoformat()
        for i, lat in enumerate(lats):
            for j, lon in enumerate(lons):
                v = float(arr[t_idx, i, j])
                if np.isnan(v):
                    continue
                feats.append({
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [[
                        [lon - pad, lat - pad], [lon + pad, lat - pad],
                        [lon + pad, lat + pad], [lon - pad, lat + pad], [lon - pad, lat - pad],
                    ]]},
                    "properties": {
                        "times": [iso],
                        "style": {"fillColor": cm.rgb_hex_str(v), "fillOpacity": opacidad,
                                  "color": COLORS["surface"], "weight": 0.8, "opacity": 0.5},
                    },
                })
    return {"type": "FeatureCollection", "features": feats}


def _timestamped(fc, period, fmt):
    return TimestampedGeoJson(
        fc,
        period=period,
        duration=period,
        add_last_point=False,
        auto_play=False,
        loop=False,
        max_speed=5,
        loop_button=True,
        date_options=fmt,
        time_slider_drag_update=True,
    )


def _grilla_js(arr, dec):
    return [[[None if np.isnan(v) else round(float(v), dec) for v in fila] for fila in paso] for paso in arr]


# JS común: lectura del píxel bajo el cursor y del promedio zonal del barrio
_JS_LECTURA = """
var GC = window.GC;
// En móvil el panel arranca plegado para no tapar el mapa (se despliega tocando el título)
if (window.innerWidth <= 640) {
    var panel = document.querySelector('.gc-panel');
    if (panel) panel.removeAttribute('open');
}
GC.tIdx = function() {
    var td = GC.map.timeDimension;
    return td ? Math.max(0, td.getCurrentTimeIndex()) : 0;
};
GC.fmt = function(v, u) { return (v !== null && v !== undefined) ? v.toLocaleString(GC.locale) + ' ' + u : '—'; };
GC.pixel = function(ll) {
    var g = GC.grid, el = document.getElementById('gc-pix');
    if (!el) return;
    if (GC.var === 'none') { el.innerText = '—'; return; }
    var i = g.lats.findIndex(function(v) { return Math.abs(ll.lat - v) <= g.pad; });
    var j = g.lons.findIndex(function(v) { return Math.abs(ll.lng - v) <= g.pad; });
    el.innerText = (i < 0 || j < 0) ? '—' : GC.fmt(g[GC.var][GC.tIdx()][i][j], GC.units[GC.var]);
};
GC.barrio = function(idx) {
    GC.activo = idx;
    var b = GC.barrios[idx];
    if (!b) return;
    document.getElementById('gc-bnom').innerText = b.nom;
    document.getElementById('gc-bpix').innerText = b.n_pix;
    document.getElementById('gc-bval').innerText =
        GC.var === 'none' ? '—' : GC.fmt(b[GC.var][GC.tIdx()], GC.units[GC.var]);
};
GC.limpiar = function() {
    GC.activo = null;
    ['gc-bnom', 'gc-bpix', 'gc-bval'].forEach(function(id) { document.getElementById(id).innerText = '—'; });
};
GC.capaBarrios.eachLayer(function(l) {
    l.on('mouseover', function() { GC.barrio(l.feature.properties.b_id); });
    l.on('mouseout', GC.limpiar);
});
GC.map.on('mousemove', function(e) { GC.ultimo = e.latlng; GC.pixel(e.latlng); });
if (GC.map.timeDimension) {
    GC.map.timeDimension.on('timeload timechange', function() {
        if (GC.activo !== null) GC.barrio(GC.activo);
        if (GC.ultimo) GC.pixel(GC.ultimo);
    });
}
"""

def _html_lectura(lang: str | None = None) -> str:
    filas = [("gc-pix", "mapa.lectura_pixel", ' class="gc-readout-big"'), ("gc-bnom", "gen.barrio", ""),
             ("gc-bpix", "mapa.lectura_pix_int", ""), ("gc-bval", "mapa.lectura_zonal", "")]
    return '<div class="gc-readout">' + "".join(
        f'<div class="gc-readout-row"><span>{t(k, lang)}</span><span id="{i}"{c}>—</span></div>' for i, k, c in filas
    ) + "</div>"


def _datos_js(m, capa, grid, barrios, units, var_inicial, lang):
    return (
        "window.GC = {"
        f"map: {m.get_name()}, capaBarrios: {capa.get_name()},"
        f"grid: {json.dumps(grid)}, barrios: {json.dumps(barrios)}, units: {json.dumps(units)},"
        f"var: '{var_inicial}', activo: null, ultimo: null, locale: '{locale_js(lang)}'"
        "};\n"
    )


def generar_mapa_dual(gdf_b, capas, titulo, barrios_stats, time_vals, lats, lons, pad, lang: str | None = None):
    """Visor temporal con dos variables alternables.

    capas: [(clave, arreglo T×Ny×Nx, VarSpec, etiqueta corta), (…)]. La primera se muestra al abrir.
    """
    m = mapa_base(gdf_b, lang=lang)
    period, fmt = _periodo(time_vals)
    prep = []
    for clave, arr, spec, etiqueta in capas:
        arr = np.asarray(arr, float)
        cm = colormap(spec.cmap, *escala_robusta(arr, desde_cero=spec.forma == "barra"))
        prep.append((clave, arr, spec, etiqueta, cm, _features_pixeles(arr, lats, lons, pad, time_vals, cm, RASTER_OPACITY)))

    (k0, _, _, _, _, fc0), (k1, _, _, _, _, fc1) = prep
    tg0 = _timestamped(fc0, period, fmt)
    tg0.add_to(m)
    capa_comunas(gdf_b, lang=lang).add_to(m)
    capa = capa_barrios(gdf_b, lang=lang).add_to(m)
    control_capas(m)

    grid = {"lats": [float(x) for x in lats], "lons": [float(x) for x in lons], "pad": float(pad),
            **{c: _grilla_js(a, sp.decimales) for c, a, sp, *_ in prep}}
    radios = "".join(
        f'<label><input type="radio" name="gc-var" value="{c}" {"checked" if n == 0 else ""} '
        f'onchange="GC.cambiar(\'{c}\')">{et}</label>'
        for n, (c, _, _, et, _, _) in enumerate(prep)
    )
    leyendas = "".join(
        f'<div id="gc-leg-{c}" style="display:{"block" if n == 0 else "none"}">'
        f'{leyenda_html(cm, sp, opacidad=RASTER_OPACITY, lang=lang)}</div>'
        for n, (c, _, sp, _, cm, _) in enumerate(prep)
    )
    m.get_root().html.add_child(Element(f"""
    <details class="gc-panel" open>
        <summary class="gc-panel-title">{titulo}</summary>
        <div class="gc-seg">
            {radios}
            <label><input type="radio" name="gc-var" value="none" onchange="GC.cambiar('none')">{t("mapa.ocultar", lang)}</label>
        </div>
        {leyendas}
        {_html_lectura(lang)}
    </details>
    """))

    js = _datos_js(m, capa, grid, barrios_stats, {c: sp.unidad for c, _, sp, *_ in prep}, k0, lang)
    js += f"""
    window.GC.capas = {{
        {k0}: {tg0.get_name()},
        {k1}: L.timeDimension.layer.geoJson(
            L.geoJson({json.dumps(fc1)}, {{ style: function(f) {{ return f.properties.style; }} }}),
            {{ updateTimeDimension: false, duration: "{period}", period: "{period}" }}
        )
    }};
    window.GC.cambiar = function(tipo) {{
        var GC = window.GC;
        GC.var = tipo;
        Object.keys(GC.capas).forEach(function(k) {{
            document.getElementById('gc-leg-' + k).style.display = (k === tipo) ? 'block' : 'none';
            if (k === tipo) {{ GC.map.addLayer(GC.capas[k]); }} else {{ GC.map.removeLayer(GC.capas[k]); }}
        }});
        // Los límites de barrio deben quedar encima del raster para recibir el hover
        if (GC.map.hasLayer(GC.capaBarrios)) GC.capaBarrios.bringToFront();
        if (GC.ultimo) GC.pixel(GC.ultimo);
        if (GC.activo !== null) GC.barrio(GC.activo);
    }};
    """
    js += _JS_LECTURA
    _ScriptMapa(js).add_to(m)
    return m


def generar_mapa_interactivo(gdf_b, arr_rh, arr_t, barrios_stats, time_vals, lats, lons, pad, lang: str | None = None):
    capas = [("rh", arr_rh, RASTER_VARS["rh"], t("var_corta.hr", lang)),
             ("t", arr_t, RASTER_VARS["t"], t("var_corta.tmax_mapa", lang))]
    return generar_mapa_dual(gdf_b, capas, "C3S · AgERA5", barrios_stats, time_vals, lats, lons, pad, lang=lang)


def generar_mapa_simple(gdf_b, arr, clave, titulo, leyenda, barrios_stats, time_vals, lats, lons, pad,
                        lang: str | None = None):
    """Visor temporal de una sola variable (precipitación CHIRPS / MSWEP)."""
    m = mapa_base(gdf_b, lang=lang)
    spec = RASTER_VARS[clave]
    arr = np.asarray(arr, float)
    cm = colormap(spec.cmap, *escala_robusta(arr, desde_cero=spec.forma == "barra"))
    period, fmt = _periodo(time_vals)

    fc = _features_pixeles(arr, lats, lons, pad, time_vals, cm, RASTER_OPACITY)
    _timestamped(fc, period, fmt).add_to(m)
    capa_comunas(gdf_b, lang=lang).add_to(m)
    capa = capa_barrios(gdf_b, lang=lang).add_to(m)
    control_capas(m)

    grid = {"lats": [float(x) for x in lats], "lons": [float(x) for x in lons], "pad": float(pad),
            clave: _grilla_js(arr, spec.decimales)}

    m.get_root().html.add_child(Element(f"""
    <details class="gc-panel" open>
        <summary class="gc-panel-title">{titulo}</summary>
        {leyenda_html(cm, spec, leyenda, opacidad=RASTER_OPACITY, lang=lang)}
        {_html_lectura(lang)}
    </details>
    """))
    js = _datos_js(m, capa, grid, barrios_stats, {clave: spec.unidad}, clave, lang) + _JS_LECTURA
    _ScriptMapa(js).add_to(m)
    return m


# =========================================================================
# Coropleta: un valor por barrio (agregado del periodo)
# =========================================================================
COROPLETA_OPACITY = 0.72
SIN_DATO = "#d9d8d2"


def puestos(valores) -> np.ndarray:
    """Puesto de cada barrio de mayor a menor (1 = valor más alto); 0 si no tiene dato."""
    v = pd.Series(np.asarray(valores, float))
    return v.rank(ascending=False, method="min").fillna(0).astype(int).to_numpy()


def mapa_coropleta(gdf_b, valores, spec: VarSpec, titulo: str, *, etiqueta: str, fmt_valor,
                   seleccion: int | None = None, foco=None, pista: str | None = None,
                   height: int | str = "100%", lang: str | None = None):
    """Barrios coloreados por un valor del periodo, con puesto en el tooltip y leyenda del colormap real.

    fmt_valor: función valor → texto (incluye unidad). seleccion: b_id del barrio a resaltar.
    foco: máscara booleana; los barrios fuera de ella se atenúan y la cámara se ajusta a los de dentro.
    """
    vals = np.asarray(valores, float)
    cm = colormap(spec.cmap, *escala_robusta(vals))
    n_validos = int(np.isfinite(vals).sum())
    pos = puestos(vals)
    foco = np.ones(len(vals), bool) if foco is None else np.asarray(foco, bool)
    datos = gdf_b[["b_id", "nombre_barrio", "comuna", "geometry"]].assign(
        comuna=gdf_b["comuna"].map(lambda c: t_comuna(c, lang)),
        valor=[fmt_valor(v) if np.isfinite(v) else t("mapa.sin_dato", lang) for v in vals],
        puesto=[t("gen.a_de_b", lang, a=p, b=n_validos) if p else "—" for p in pos],
        relleno=[cm.rgb_hex_str(v) if np.isfinite(v) else SIN_DATO for v in vals],
        opacidad=np.where(foco, COROPLETA_OPACITY, 0.16),
    )

    m = mapa_base(gdf_b, height=height, lang=lang)
    if not foco.all():
        minx, miny, maxx, maxy = gdf_b.loc[foco].total_bounds
        m.fit_bounds([[miny - 0.004, minx - 0.004], [maxy + 0.004, maxx + 0.004]])
    folium.GeoJson(
        datos,
        name=etiqueta,
        style_function=lambda f: {"fillColor": f["properties"]["relleno"], "fillOpacity": f["properties"]["opacidad"],
                                  "color": "#ffffff", "weight": 0.7, "opacity": 0.9},
        highlight_function=lambda f: {"weight": 2.4, "color": COLORS["ink"], "fillOpacity": 0.85},
        tooltip=folium.GeoJsonTooltip(fields=["nombre_barrio", "comuna", "valor", "puesto"],
                                      aliases=[t("gen.barrio", lang), t("gen.comuna", lang), etiqueta,
                                               t("mapa.puesto", lang)], sticky=True,
                                      class_name="gc-tooltip"),
    ).add_to(m)
    capa_comunas(gdf_b, show=True, lang=lang).add_to(m)
    if not foco.all():
        borde = gpd.GeoDataFrame(geometry=[gdf_b.loc[foco].geometry.union_all()], crs=gdf_b.crs)
        folium.GeoJson(borde, name=t("mapa.ambito", lang), interactive=False, control=False,
                       style_function=lambda f: {"fillOpacity": 0, "color": COLORS["ink"], "weight": 2.2,
                                                 "opacity": 0.9}).add_to(m)
    if seleccion is not None:
        folium.GeoJson(
            gdf_b.iloc[[seleccion]][["nombre_barrio", "geometry"]], name=t("mapa.barrio_sel", lang),
            style_function=lambda f: {"fillOpacity": 0, "color": COLORS["ink"], "weight": 3, "opacity": 1},
            interactive=False,
        ).add_to(m)

    control_capas(m)
    pista_html = f'<div class="gc-legend-note" style="margin-top:8px">{pista}</div>' if pista else ""
    m.get_root().html.add_child(Element(f"""
    <details class="gc-panel" open>
        <summary class="gc-panel-title">{titulo}</summary>
        {leyenda_html(cm, spec, etiqueta, opacidad=COROPLETA_OPACITY, nota=t("mapa.nota_escala_barrios", lang),
                      lang=lang)}
        {pista_html}
    </details>
    """))
    # En móvil el panel arranca plegado para no tapar el mapa
    _ScriptMapa("""
    if (window.innerWidth <= 640) {
        var panel = document.querySelector('.gc-panel');
        if (panel) panel.removeAttribute('open');
    }""").add_to(m)
    return m


def geojson_barrios(gdf_b, tabla: pd.DataFrame, columna_nombre: str) -> bytes:
    """GeoJSON (EPSG:4326) con la geometría de cada barrio y las columnas numéricas/texto de la tabla.

    columna_nombre: columna de la tabla con el nombre del barrio (su encabezado depende del idioma).
    """
    cols = [c for c in tabla.columns
            if not tabla[c].map(lambda v: isinstance(v, (list, tuple, np.ndarray))).any()]
    geo = gdf_b[["nombre_barrio", "geometry"]].merge(
        tabla[cols], left_on="nombre_barrio", right_on=columna_nombre, how="right"
    )
    geo = gpd.GeoDataFrame(geo.drop(columns="nombre_barrio"), geometry="geometry", crs="EPSG:4326")
    geo["geometry"] = geo.geometry.set_precision(1e-6)  # ~0.1 m: archivos más livianos sin perder forma
    return geo.to_json(drop_id=True, na="null").encode("utf-8")


# =========================================================================
# Estaciones in situ
# =========================================================================
def cargar_y_procesar_estaciones(csv_path: Path):
    """Registros semanales por estación e información de cada estación (con aviso traducido mientras procesa)."""
    with st.spinner(t("gen.procesando_estaciones")):
        return _estaciones_semanales(csv_path)


@st.cache_data(show_spinner=False)
def _estaciones_semanales(csv_path: Path):
    cols = [
        "Estacion",
        "Fecha",
        "Precipitacion",
        "Tmin",
        "Tmax",
        "Humedad relativa",
        "Velocidad del viento",
        "Radiación solar",
        "Latitud",
        "Longitud",
    ]
    df = pd.read_csv(csv_path, usecols=cols)
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    df = df.sort_values(["Estacion", "Fecha"])

    reglas = {
        "Precipitacion": "sum",
        "Tmin": "mean",
        "Tmax": "mean",
        "Humedad relativa": "mean",
        "Velocidad del viento": "mean",
        "Radiación solar": "mean",
        "Latitud": "first",
        "Longitud": "first",
    }

    # Semana epidemiológica INS Colombia / CDC (MMWR): domingo a sábado.
    # "W-SAT" agrupa (sábado anterior, sábado] = domingo..sábado y etiqueta con el sábado de cierre.
    df_semanal = (
        df.groupby(["Estacion", pd.Grouper(key="Fecha", freq="W-SAT")])
        .agg(reglas)
        .reset_index()
    )
    # Año y número de semana epidemiológica: la semana 1 es la primera con >= 4 días en enero,
    # es decir, la que contiene el primer miércoles del año.
    miercoles = df_semanal["Fecha"] - pd.Timedelta(days=3)
    df_semanal["Año epi"] = miercoles.dt.year
    df_semanal["Semana epi"] = (miercoles.dt.day_of_year - 1) // 7 + 1

    # Primero se descartan filas sin coordenadas: algunas estaciones (Compartir) empiezan sin ellas
    estaciones_info = (
        df[["Estacion", "Latitud", "Longitud"]].dropna().drop_duplicates("Estacion")
    )

    return df_semanal, estaciones_info


# =========================================================================
# Celdas de una grilla raster frente a Cali (común a todas las fuentes)
# =========================================================================
def celdas_sobre_cali(barrios, lats, lons, pad):
    """Celdas de la grilla que tocan algún barrio, con % de su área dentro de Cali.

    Devuelve (celdas que tocan Cali, total de celdas del extent, celdas que toca cada barrio).
    """
    lats, lons = np.asarray(lats, float), np.asarray(lons, float)
    ii, jj = np.divmod(np.arange(len(lats) * len(lons)), len(lons))
    celdas = gpd.GeoDataFrame(
        {"fila": ii, "col": jj, "lat": lats[ii], "lon": lons[jj]},
        geometry=shapely.box(lons[jj] - pad, lats[ii] - pad, lons[jj] + pad, lats[ii] + pad),
        crs="EPSG:4326",
    )
    total = len(celdas)
    cali = barrios.geometry.union_all()
    celdas = celdas[celdas.intersects(cali)].copy()

    utm = "EPSG:32618"  # UTM 18N: áreas en m² para Cali
    celdas_utm = celdas.to_crs(utm)
    cali_utm = gpd.GeoSeries([cali], crs="EPSG:4326").to_crs(utm).iloc[0]
    celdas["pct_cali"] = (celdas_utm.intersection(cali_utm).area / celdas_utm.area * 100).round(0)

    b_idx, c_idx = shapely.STRtree(celdas.geometry.values).query(barrios.geometry.values, predicate="intersects")
    celdas["n_barrios"] = np.bincount(c_idx, minlength=len(celdas))
    # Mismo criterio "intersecta" de las estadísticas zonales
    celdas_por_barrio = np.bincount(b_idx, minlength=len(barrios))
    return celdas, total, celdas_por_barrio


def resumen_extent(gdf, lats, lons, pad) -> dict:
    """Conteo de celdas de una fuente raster: en el extent del archivo y sobre Cali."""
    celdas, total, por_barrio = celdas_sobre_cali(preparar_barrios(gdf), lats, lons, pad)
    return {
        "forma": (len(lats), len(lons)),
        "res": 2 * pad,
        "total": total,
        "tocan_cali": len(celdas),
        "dentro_50": int((celdas["pct_cali"] >= 50).sum()),
        "por_barrio_mediana": float(np.median(por_barrio)),
        "por_barrio_max": int(por_barrio.max()),
        "barrios_una_celda": int((por_barrio == 1).sum()),
        "n_barrios": len(por_barrio),
    }


# =========================================================================
# Grilla de 1 km (la misma de los NetCDF de GEE)
# =========================================================================
@st.cache_data(show_spinner=False)
def grilla_1km_estaciones(_gdf, estaciones: pd.DataFrame, gee_nc: str | None, mtime: float | None):
    """Celdas de 1 km que tocan Cali con sus estaciones, barrios y fracción de área dentro de la ciudad,
    más el número de celdas que toca cada barrio (en el orden de la capa de barrios).

    Si existe el NetCDF de GEE se usan sus coordenadas; si no, la grilla teórica idéntica.
    """
    from descargas.comun import RES_1KM, grilla_1km

    if gee_nc:
        _, lats, lons, pad = cargar_grilla_nc(Path(gee_nc))
        origen = "GEE"
    else:
        lats, lons, _ = grilla_1km(tuple(_gdf.total_bounds))
        pad, origen = RES_1KM / 2, "teórica"

    barrios = preparar_barrios(_gdf)
    celdas, total, celdas_por_barrio = celdas_sobre_cali(barrios, lats, lons, pad)

    pts = gpd.GeoDataFrame(estaciones, geometry=gpd.points_from_xy(estaciones["Longitud"], estaciones["Latitud"]),
                           crs="EPSG:4326")
    unidas = gpd.sjoin(pts, celdas[["geometry"]], predicate="within", how="inner")
    por_celda = unidas.groupby("index_right")["Estacion"].agg(list)
    celdas["n_est"] = celdas.index.map(por_celda.str.len()).fillna(0).astype(int)
    celdas["estaciones"] = celdas.index.map(lambda k: ", ".join(por_celda.get(k, [])) or "—")
    celdas["celda"] = celdas.apply(lambda r: f"F{r.fila + 1:02d} · C{r.col + 1:02d}", axis=1)
    celdas["centro"] = celdas.apply(lambda r: f"{r.lat:.4f}°, {r.lon:.4f}°", axis=1)

    resumen = {
        "origen": origen,
        "forma": (len(lats), len(lons)),
        "res": 2 * pad,
        "total": total,
        "tocan_cali": len(celdas),
        "dentro_50": int((celdas["pct_cali"] >= 50).sum()),
        "con_estacion": int((celdas["n_est"] > 0).sum()),
        "max_est": int(celdas["n_est"].max()) if len(celdas) else 0,
        "fuera": int(len(pts) - len(unidas)),
        "celdas_por_barrio_mediana": float(np.median(celdas_por_barrio)),
        "celdas_por_barrio_max": int(celdas_por_barrio.max()),
    }
    cols = ["celda", "centro", "n_est", "estaciones", "n_barrios", "pct_cali", "geometry"]
    return celdas[cols].reset_index(drop=True), resumen, celdas_por_barrio
