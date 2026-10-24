import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from components.charts import mostrar, serie_temporal
from components.theme import MAP_HEIGHT, RASTER_VARS
from components.ui import empty_state, metric_card, render_header, section_title
from utils import (
    calcular_estadisticas_zonales,
    cargar_chirps,
    cargar_recorte_nc,
    estadisticas_zonales,
    generar_mapa_chirps,
    generar_mapa_interactivo,
    listar_fuentes,
)

FUENTES_META = {
    "C3S": {
        "nombre": "Copernicus C3S · AgERA5",
        "desc": "Indicadores agrometeorológicos diarios derivados del reanálisis ERA5 (0.1°).",
        "url": "https://cds.climate.copernicus.eu/datasets/sis-agrometeorological-indicators?tab=overview",
    },
    "CHIRPS": {
        "nombre": "CHIRPS v3.0",
        "desc": "Precipitación diaria cuasi-global combinando satélite y estaciones (0.05°).",
        "url": "https://www.chc.ucsb.edu/data/chirps3",
    },
    "MSWEP": {
        "nombre": "MSWEP",
        "desc": "Precipitación global multi-fuente ponderada (satélite, reanálisis y pluviómetros).",
        "url": "https://climatedataguide.ucar.edu/climate-data/global-high-resolution-precipitation-mswep",
    },
    "GEE": {
        "nombre": "Google Earth Engine",
        "desc": "Productos derivados exportados desde Earth Engine.",
        "url": None,
    },
}


# =========================================================================
# Procesamiento cacheado (clave: rutas + fecha de modificación)
# =========================================================================
@st.cache_data(show_spinner=False)
def _bundle_c3s(_gdf, f_rh: str, f_t: str, bounds: tuple, mtimes: tuple):
    da_rh, lat_c, lon_c, pad = cargar_recorte_nc(Path(f_rh), bounds)
    da_t, _, _, _ = cargar_recorte_nc(Path(f_t), bounds)
    gdf_b, stats, times, lats, lons = calcular_estadisticas_zonales(_gdf, da_rh, da_t, lat_c, lon_c, pad)
    mapa = generar_mapa_interactivo(gdf_b, da_rh, da_t, stats, times, lats, lons, pad)
    return {"html": mapa.get_root().render(), "stats": stats, "times": times, "res": 2 * pad}


@st.cache_data(show_spinner=False)
def _bundle_chirps(_gdf, f_ch: str, mtime: float):
    da_p, lats, lons, pad = cargar_chirps(Path(f_ch))
    times = pd.to_datetime(da_p.time.values)
    gdf_b, stats = estadisticas_zonales(_gdf, {"p": da_p.values}, lats, lons, pad, decimales=2)
    mapa = generar_mapa_chirps(gdf_b, da_p, lats, lons, pad, stats, times)
    return {"html": mapa.get_root().render(), "stats": stats, "times": times, "res": 2 * pad}


def _serie_area(stats, clave: str) -> np.ndarray:
    """Promedio diario entre barrios de las series zonales."""
    mat = np.array([[np.nan if v is None else v for v in s[clave]] for s in stats], dtype=float)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        return np.nanmean(mat, axis=0)


def _resolucion(grados: float) -> str:
    return f"{grados:.2f}° · ~{grados * 111:.0f} km"


# =========================================================================
# Render
# =========================================================================
def render(gdf, inputs_path: Path):
    fuentes = listar_fuentes(inputs_path / "raster")

    render_header(
        title="Fuentes satelitales y reanálisis",
        subtitle="Exploración espaciotemporal de productos raster y estadísticas zonales por barrio.",
        eyebrow="Módulo 01 · Raster",
        badges=[("Fuentes", "violet", str(len(fuentes))), ("Barrios", "gray", f"{len(gdf):,}")],
    )

    if not fuentes:
        empty_state("Sin fuentes raster", "No se encontraron carpetas en inputs/raster.")
        return

    opciones = list(fuentes)
    nombre = st.segmented_control(
        "Fuente",
        opciones,
        default=opciones[0],
        required=True,
        key="fuente_satelital",
        format_func=lambda k: f"{k}  ·  {len(fuentes[k])}",
        label_visibility="collapsed",
    )
    archivos = fuentes[nombre]
    meta = FUENTES_META.get(nombre.upper(), {"nombre": nombre, "desc": "", "url": None})

    c_info, c_link = st.columns([4, 1], vertical_alignment="center")
    with c_info:
        section_title(meta["nombre"], meta["desc"])
    with c_link:
        if meta["url"]:
            st.link_button("Documentación", meta["url"], icon=":material/open_in_new:", type="tertiary",
                           width="stretch")

    if nombre.upper() == "C3S":
        _render_c3s(gdf, archivos)
    elif nombre.upper() == "CHIRPS":
        _render_chirps(gdf, archivos)
    else:
        _render_inventario(nombre, archivos)


def _render_c3s(gdf, archivos):
    f_rh = next((f for f in archivos if "relative_humidity" in f.name), None)
    f_t = next((f for f in archivos if "temperature_maximu" in f.name or "t2m" in f.name), None)
    if not (f_rh and f_t):
        empty_state("Archivos incompletos", "Se requieren los NetCDF de humedad relativa y temperatura máxima.")
        return

    with st.spinner("Preparando visor C3S…"):
        b = _bundle_c3s(gdf, str(f_rh), str(f_t), tuple(gdf.total_bounds),
                        (f_rh.stat().st_mtime, f_t.stat().st_mtime))

    times = b["times"]
    rh, t = _serie_area(b["stats"], "rh"), _serie_area(b["stats"], "t")
    s_rh, s_t = RASTER_VARS["rh"], RASTER_VARS["t"]
    periodo = f"{times[0]:%d/%m/%Y} – {times[-1]:%d/%m/%Y}"

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        metric_card("Humedad relativa media", s_rh.fmt(np.nanmean(rh)),
                    delta=f"{np.nanmin(rh):.0f}–{np.nanmax(rh):.0f} %", delta_description="rango diario",
                    neutral_delta=True, chart=np.round(rh, 1).tolist(), chart_type="area",
                    help="Promedio de las series zonales de todos los barrios.")
    with k2:
        metric_card("Temperatura máxima media", s_t.fmt(np.nanmean(t)),
                    delta=f"{np.nanmin(t):.1f}–{np.nanmax(t):.1f} °C", delta_description="rango diario",
                    neutral_delta=True, chart=np.round(t, 1).tolist(), chart_type="area")
    with k3:
        metric_card("Último día · Tmax", s_t.fmt(t[-1]),
                    delta=round(float(t[-1] - np.nanmean(t)), 1), delta_description="vs. media del periodo",
                    delta_color="off", help=f"{times[-1]:%d/%m/%Y}")
    with k4:
        metric_card("Cobertura", f"{len(times)} días", delta=periodo, neutral_delta=True,
                    help=f"Resolución {_resolucion(b['res'])}")

    st.iframe(b["html"], height=MAP_HEIGHT)
    st.caption("Desplace el cursor sobre el mapa para leer el píxel y el promedio zonal del barrio. "
               "Use el control temporal inferior para recorrer los días.")

    section_title("Series diarias", "Promedio de las estadísticas zonales de todos los barrios.")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**{s_rh.label}**")
        mostrar(serie_temporal(times, rh, s_rh, height=260, referencia=float(np.nanmean(rh))), key="c3s_rh")
    with c2:
        st.markdown(f"**{s_t.label}**")
        mostrar(serie_temporal(times, t, s_t, height=260, referencia=float(np.nanmean(t))), key="c3s_t")

    section_title("Resumen por barrio", "Estadísticos del periodo calculados sobre la serie zonal diaria.")
    filas = []
    for s in b["stats"]:
        v_rh = np.array([np.nan if v is None else v for v in s["rh"]], float)
        v_t = np.array([np.nan if v is None else v for v in s["t"]], float)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            filas.append({
                "Barrio": s["nom"], "Píxeles": s["n_pix"],
                "HR media (%)": np.nanmean(v_rh), "HR diaria": s["rh"],
                "Tmax media (°C)": np.nanmean(v_t), "Tmax máx. (°C)": np.nanmax(v_t), "Tmax diaria": s["t"],
            })
    df = pd.DataFrame(filas).sort_values("Tmax media (°C)", ascending=False)
    st.dataframe(
        df,
        hide_index=True,
        height=380,
        column_config={
            "Barrio": st.column_config.TextColumn(pinned=True),
            "Píxeles": st.column_config.NumberColumn(format="%d", width="small"),
            "HR media (%)": st.column_config.NumberColumn(format="%.1f"),
            "HR diaria": st.column_config.LineChartColumn(),
            "Tmax media (°C)": st.column_config.NumberColumn(format="%.1f"),
            "Tmax máx. (°C)": st.column_config.NumberColumn(format="%.1f"),
            "Tmax diaria": st.column_config.LineChartColumn(),
        },
    )


def _render_chirps(gdf, archivos):
    f_ch = next((f for f in archivos if "chirps" in f.name.lower() and f.suffix == ".nc"), None)
    if not f_ch:
        empty_state("Sin archivo CHIRPS", "No se encontró un NetCDF de CHIRPS en la carpeta de la fuente.")
        return

    with st.spinner("Preparando visor CHIRPS…"):
        b = _bundle_chirps(gdf, str(f_ch), f_ch.stat().st_mtime)

    times = b["times"]
    p = _serie_area(b["stats"], "p")
    spec = RASTER_VARS["p"]
    i_max = int(np.nanargmax(p))
    dias_lluvia = int(np.sum(p >= 1))

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        metric_card("Acumulado del periodo", f"{np.nansum(p):,.1f} mm",
                    delta=f"{times[0]:%d/%m} – {times[-1]:%d/%m/%Y}", neutral_delta=True,
                    chart=np.round(p, 2).tolist(), chart_type="bar",
                    help="Suma de la precipitación diaria promedio de los barrios.")
    with k2:
        metric_card("Días con lluvia", f"{dias_lluvia} de {len(times)}",
                    delta=f"{100 * dias_lluvia / len(times):.0f} % del periodo", neutral_delta=True,
                    help="Días con promedio de barrios ≥ 1 mm.")
    with k3:
        metric_card("Máximo diario", spec.fmt(p[i_max]), delta=f"{times[i_max]:%d/%m/%Y}", neutral_delta=True)
    with k4:
        metric_card("Resolución espacial", _resolucion(b["res"]), delta="Grilla nativa", neutral_delta=True)

    st.iframe(b["html"], height=MAP_HEIGHT)
    st.caption("Desplace el cursor sobre el mapa para leer el píxel y el promedio zonal del barrio. "
               "Use el control temporal inferior para recorrer los días.")

    section_title("Precipitación diaria", "Promedio de las estadísticas zonales de todos los barrios.")
    mostrar(serie_temporal(times, p, spec, height=280), key="chirps_p")

    section_title("Resumen por barrio", "Estadísticos del periodo calculados sobre la serie zonal diaria.")
    filas = []
    for s in b["stats"]:
        v = np.array([np.nan if x is None else x for x in s["p"]], float)
        filas.append({
            "Barrio": s["nom"], "Píxeles": s["n_pix"],
            "Acumulado (mm)": np.nansum(v), "Máx. diario (mm)": np.nanmax(v) if np.isfinite(v).any() else np.nan,
            "Días ≥ 1 mm": int(np.sum(v >= 1)), "Precipitación diaria": s["p"],
        })
    df = pd.DataFrame(filas).sort_values("Acumulado (mm)", ascending=False)
    st.dataframe(
        df,
        hide_index=True,
        height=380,
        column_config={
            "Barrio": st.column_config.TextColumn(pinned=True),
            "Píxeles": st.column_config.NumberColumn(format="%d", width="small"),
            "Acumulado (mm)": st.column_config.ProgressColumn(
                format="%.1f", min_value=0, max_value=float(df["Acumulado (mm)"].max() or 1)),
            "Máx. diario (mm)": st.column_config.NumberColumn(format="%.1f"),
            "Días ≥ 1 mm": st.column_config.NumberColumn(format="%d"),
            "Precipitación diaria": st.column_config.BarChartColumn(y_min=0),
        },
    )


def _render_inventario(nombre, archivos):
    if not archivos:
        empty_state(f"{nombre} sin archivos",
                    "La carpeta existe pero aún no contiene NetCDF ni GeoTIFF para visualizar.")
        return
    data = pd.DataFrame([
        {"Archivo": a.name, "Formato": a.suffix.lstrip(".").upper(), "Tamaño (MB)": a.stat().st_size / 2**20}
        for a in archivos
    ])
    st.dataframe(data, hide_index=True,
                 column_config={"Tamaño (MB)": st.column_config.NumberColumn(format="%.2f")})
