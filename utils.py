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
from folium.plugins import TimestampedGeoJson
from jinja2 import Template

from components.theme import (
    COLORS,
    FONT_STACK,
    FONT_URL,
    RASTER_VARS,
    BARRIO_LINE,
    RASTER_OPACITY,
    TILES_ATTR,
    TILES_URL,
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


def listar_fuentes(raster_dir: Path):
    fuentes = {}
    if raster_dir.exists():
        for d in sorted([p for p in raster_dir.iterdir() if p.is_dir()]):
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


def cargar_chirps(nc_path: Path):
    with xr.open_dataset(nc_path) as ds:
        da_p = ds["precipitation"].load()
    lat_col = "lat" if "lat" in da_p.coords else "latitude"
    lon_col = "lon" if "lon" in da_p.coords else "longitude"
    lats = da_p[lat_col].values
    lons = da_p[lon_col].values
    pad = (
        abs(float(lats[1] - lats[0])) / 2.0
        if len(lats) > 1
        else abs(float(lons[1] - lons[0])) / 2.0
    )
    return da_p, lats, lons, pad


# =========================================================================
# Estadísticas zonales (promedio de píxeles que intersectan cada barrio)
# =========================================================================
def preparar_barrios(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf_b = gdf.copy()
    col_nombre = next((c for c in gdf_b.columns if c.lower() == "nombre"), gdf_b.columns[0])
    gdf_b["b_id"] = np.arange(len(gdf_b))
    gdf_b["nombre_barrio"] = gdf_b[col_nombre].astype(str)
    return gdf_b


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
      color: {COLORS["muted"]}; margin-bottom: 8px; }}
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


def mapa_base(gdf, height: int | str = "100%", controles: bool = True) -> folium.Map:
    """Mapa con fondo y cámara idénticos en toda la aplicación."""
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
    folium.TileLayer(TILES_URL, attr=TILES_ATTR, name="OpenStreetMap", control=False,
                     max_native_zoom=19, max_zoom=19).add_to(m)
    m.get_root().header.add_child(Element(MAP_CSS))
    return m


def capa_barrios(gdf_b, con_pixeles: bool = True) -> folium.GeoJson:
    campos = ["nombre_barrio", "n_pixeles"] if con_pixeles else ["nombre_barrio"]
    alias = ["Barrio", "Píxeles"] if con_pixeles else ["Barrio"]
    return folium.GeoJson(
        gdf_b[["b_id"] + campos + ["geometry"]],
        name="Límites Cali",
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
    for t_idx, t in enumerate(time_vals):
        iso = t.isoformat()
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
GC.tIdx = function() {
    var td = GC.map.timeDimension;
    return td ? Math.max(0, td.getCurrentTimeIndex()) : 0;
};
GC.fmt = function(v, u) { return (v !== null && v !== undefined) ? v.toLocaleString('es-CO') + ' ' + u : '—'; };
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

_HTML_LECTURA = """
<div class="gc-readout">
    <div class="gc-readout-row"><span>Píxel bajo el cursor</span><span id="gc-pix" class="gc-readout-big">—</span></div>
    <div class="gc-readout-row"><span>Barrio</span><span id="gc-bnom">—</span></div>
    <div class="gc-readout-row"><span>Píxeles intersectados</span><span id="gc-bpix">—</span></div>
    <div class="gc-readout-row"><span>Promedio zonal</span><span id="gc-bval">—</span></div>
</div>
"""


def _datos_js(m, capa, grid, barrios, units, var_inicial):
    return (
        "window.GC = {"
        f"map: {m.get_name()}, capaBarrios: {capa.get_name()},"
        f"grid: {json.dumps(grid)}, barrios: {json.dumps(barrios)}, units: {json.dumps(units)},"
        f"var: '{var_inicial}', activo: null, ultimo: null"
        "};\n"
    )


def generar_mapa_interactivo(gdf_b, da_rh, da_t, barrios_stats, time_vals, lats, lons, pad):
    m = mapa_base(gdf_b)
    spec_rh, spec_t = RASTER_VARS["rh"], RASTER_VARS["t"]
    arr_rh, arr_t = np.asarray(da_rh.values, float), np.asarray(da_t.values, float)

    cm_rh = colormap(spec_rh.cmap, *escala_robusta(arr_rh))
    cm_t = colormap(spec_t.cmap, *escala_robusta(arr_t))
    period, fmt = _periodo(time_vals)

    fc_rh = _features_pixeles(arr_rh, lats, lons, pad, time_vals, cm_rh, RASTER_OPACITY)
    fc_t = _features_pixeles(arr_t, lats, lons, pad, time_vals, cm_t, RASTER_OPACITY)
    tg_rh = _timestamped(fc_rh, period, fmt)
    tg_rh.add_to(m)
    capa = capa_barrios(gdf_b).add_to(m)
    folium.LayerControl(position="topright", collapsed=True).add_to(m)

    grid = {"lats": [float(x) for x in lats], "lons": [float(x) for x in lons], "pad": float(pad),
            "rh": _grilla_js(arr_rh, 1), "t": _grilla_js(arr_t, 1)}

    m.get_root().html.add_child(Element(f"""
    <div class="gc-panel">
        <div class="gc-panel-title">C3S · AgERA5</div>
        <div class="gc-seg">
            <label><input type="radio" name="gc-var" value="rh" checked onchange="GC.cambiar('rh')">Humedad</label>
            <label><input type="radio" name="gc-var" value="t" onchange="GC.cambiar('t')">Temp. máx.</label>
            <label><input type="radio" name="gc-var" value="none" onchange="GC.cambiar('none')">Ocultar</label>
        </div>
        <div id="gc-leg-rh">{leyenda_html(cm_rh, spec_rh, opacidad=RASTER_OPACITY)}</div>
        <div id="gc-leg-t" style="display:none">{leyenda_html(cm_t, spec_t, opacidad=RASTER_OPACITY)}</div>
        {_HTML_LECTURA}
    </div>
    """))

    js = _datos_js(m, capa, grid, barrios_stats, {"rh": spec_rh.unidad, "t": spec_t.unidad}, "rh")
    js += f"""
    window.GC.capas = {{
        rh: {tg_rh.get_name()},
        t: L.timeDimension.layer.geoJson(
            L.geoJson({json.dumps(fc_t)}, {{ style: function(f) {{ return f.properties.style; }} }}),
            {{ updateTimeDimension: false, duration: "{period}", period: "{period}" }}
        )
    }};
    window.GC.cambiar = function(tipo) {{
        var GC = window.GC;
        GC.var = tipo;
        ['rh', 't'].forEach(function(k) {{
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


def generar_mapa_chirps(gdf_b, da_p, lats, lons, pad, barrios_stats, time_vals):
    m = mapa_base(gdf_b)
    spec = RASTER_VARS["p"]
    arr = np.asarray(da_p.values, float)
    cm_p = colormap(spec.cmap, *escala_robusta(arr, desde_cero=True))

    fc = _features_pixeles(arr, lats, lons, pad, time_vals, cm_p, RASTER_OPACITY)
    _timestamped(fc, "P1D", "YYYY-MM-DD").add_to(m)
    capa = capa_barrios(gdf_b).add_to(m)
    folium.LayerControl(position="topright", collapsed=True).add_to(m)

    grid = {"lats": [float(x) for x in lats], "lons": [float(x) for x in lons], "pad": float(pad),
            "p": _grilla_js(arr, 2)}

    m.get_root().html.add_child(Element(f"""
    <div class="gc-panel">
        <div class="gc-panel-title">CHIRPS v3.0</div>
        {leyenda_html(cm_p, spec, "Precipitación diaria", opacidad=RASTER_OPACITY)}
        {_HTML_LECTURA}
    </div>
    """))
    js = _datos_js(m, capa, grid, barrios_stats, {"p": spec.unidad}, "p") + _JS_LECTURA
    _ScriptMapa(js).add_to(m)
    return m


# =========================================================================
# Estaciones in situ
# =========================================================================
@st.cache_data(show_spinner="Procesando registros de estaciones…")
def cargar_y_procesar_estaciones(csv_path: Path):
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
    df_semanal["Semana epi"] = (miercoles.dt.dayofyear - 1) // 7 + 1

    estaciones_info = (
        df[["Estacion", "Latitud", "Longitud"]].drop_duplicates("Estacion").dropna()
    )

    return df_semanal, estaciones_info
