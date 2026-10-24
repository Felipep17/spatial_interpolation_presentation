import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from components.charts import mostrar, serie_temporal
from components.theme import MAP_HEIGHT, RASTER_VARS, VarSpec
from components.ui import empty_state, metric_card, render_header, section_title, tabla_resumen
from utils import (
    calcular_estadisticas_zonales,
    cargar_grilla_nc,
    cargar_recorte_nc,
    estadisticas_zonales,
    generar_mapa_dual,
    generar_mapa_interactivo,
    generar_mapa_simple,
    listar_fuentes,
    resumen_extent,
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
        "desc": "Precipitación diaria multi-fuente ponderada: satélite, reanálisis y pluviómetros (0.1°).",
        "url": "https://www.gloh2o.org/mswep/",
    },
    "GEE": {
        "nombre": "Google Earth Engine · MODIS 1 km",
        "desc": "NDVI y NDWI diarios de MOD09GA promediados a una grilla de 0.009° (~1 km), sin nubes.",
        "url": "https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD09GA",
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
    return {"html": mapa.get_root().render(), "stats": stats, "times": times, "res": 2 * pad,
            "extent": resumen_extent(_gdf, lats, lons, pad)}


@st.cache_data(show_spinner=False)
def _bundle_precip(_gdf, f_nc: str, mtime: float, titulo: str):
    da_p, lats, lons, pad = cargar_grilla_nc(Path(f_nc), "precipitation")
    times = pd.to_datetime(da_p.time.values)
    gdf_b, stats = estadisticas_zonales(_gdf, {"p": da_p.values}, lats, lons, pad, decimales=2)
    mapa = generar_mapa_simple(gdf_b, da_p.values, "p", titulo, "Precipitación diaria",
                               stats, times, lats, lons, pad)
    return {"html": mapa.get_root().render(), "stats": stats, "times": times, "res": 2 * pad,
            "extent": resumen_extent(_gdf, lats, lons, pad)}


@st.cache_data(show_spinner=False)
def _bundle_gee(_gdf, f_ndvi: str, f_ndwi: str, mtimes: tuple):
    da_v, lats, lons, pad = cargar_grilla_nc(Path(f_ndvi), "NDVI")
    da_w, *_ = cargar_grilla_nc(Path(f_ndwi), "NDWI")
    times = pd.to_datetime(da_v.time.values)
    gdf_b, stats = estadisticas_zonales(_gdf, {"ndvi": da_v.values, "ndwi": da_w.values}, lats, lons, pad,
                                        decimales=3)
    capas = [("ndvi", da_v.values, RASTER_VARS["ndvi"], "NDVI"), ("ndwi", da_w.values, RASTER_VARS["ndwi"], "NDWI")]
    mapa = generar_mapa_dual(gdf_b, capas, "GEE · MODIS 1 km", stats, times, lats, lons, pad)
    sin_nubes = np.isfinite(da_v.values).mean(axis=(1, 2)) * 100
    return {"html": mapa.get_root().render(), "stats": stats, "times": times, "res": 2 * pad,
            "forma": (len(lats), len(lons)), "sin_nubes": sin_nubes,
            "extent": resumen_extent(_gdf, lats, lons, pad)}


def _serie_area(stats, clave: str) -> np.ndarray:
    """Promedio diario entre barrios de las series zonales."""
    mat = np.array([[np.nan if v is None else v for v in s[clave]] for s in stats], dtype=float)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        return np.nanmean(mat, axis=0)


def _bloque_extent(r: dict, unidad: str = "píxeles"):
    """Cuántas celdas tiene la grilla de la fuente y cuántas cubren realmente a Cali."""
    ny, nx = r["forma"]
    section_title("Grilla de la fuente",
                  "Celdas del archivo frente a los barrios de Cali (criterio: la celda intersecta el barrio).")
    tabla_resumen([
        ("Resolución", _resolucion(r["res"])),
        ("Celdas en el extent del archivo", f"{r['total']:,} ({ny} × {nx})"),
        ("Celdas que tocan Cali", f"{r['tocan_cali']:,} ({100 * r['tocan_cali'] / max(r['total'], 1):.0f} % del extent)"),
        ("Celdas con ≥ 50 % dentro de Cali", f"{r['dentro_50']:,}"),
        (f"{unidad.capitalize()} por barrio", f"mediana {r['por_barrio_mediana']:.0f} · máx. {r['por_barrio_max']}"),
        ("Barrios dentro de una sola celda",
         f"{r['barrios_una_celda']:,} de {r['n_barrios']:,} ({100 * r['barrios_una_celda'] / r['n_barrios']:.0f} %)"),
    ])


def _resolucion(grados: float) -> str:
    km = grados * 111.32
    return f"{grados:.3f}° · ~{km:.1f} km" if grados < 0.05 else f"{grados:.2f}° · ~{km:.0f} km"


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

    fuente = nombre.upper()
    if fuente == "C3S":
        _render_c3s(gdf, archivos)
    elif fuente in ("CHIRPS", "MSWEP"):
        f_nc = next((f for f in archivos if fuente.lower() in f.name.lower() and f.suffix == ".nc"), None)
        if f_nc:
            _render_precip(gdf, f_nc, fuente)
        else:
            _faltante(fuente, archivos)
    elif fuente == "GEE":
        _render_gee(gdf, archivos)
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
    _bloque_extent(b["extent"])

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


def _render_precip(gdf, f_nc: Path, fuente: str):
    titulo = FUENTES_META[fuente]["nombre"]
    with st.spinner(f"Preparando visor {fuente}…"):
        b = _bundle_precip(gdf, str(f_nc), f_nc.stat().st_mtime, titulo)

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
    _bloque_extent(b["extent"])

    section_title("Precipitación diaria", "Promedio de las estadísticas zonales de todos los barrios.")
    mostrar(serie_temporal(times, p, spec, height=280), key=f"{fuente.lower()}_p")

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


COMANDOS_DESCARGA = {
    "GEE": "uv run --group descarga python -m descargas.gee --project <ID_PROYECTO_GCP>",
    "MSWEP": "uv run --group descarga python -m descargas.mswep --client-secret /ruta/client.json",
    "CHIRPS": None,
}


def _faltante(fuente: str, archivos):
    """Estado vacío con la instrucción exacta para descargar la fuente."""
    empty_state(f"{fuente}: aún no hay datos descargados",
                "Ejecute la descarga desde la raíz del proyecto; el periodo se toma del archivo de CHIRPS.")
    if COMANDOS_DESCARGA.get(fuente):
        st.code(COMANDOS_DESCARGA[fuente], language="bash")
    if archivos:
        _render_inventario(fuente, archivos)


def _render_gee(gdf, archivos):
    f_ndvi = next((f for f in archivos if "ndvi" in f.name.lower() and f.suffix == ".nc"), None)
    f_ndwi = next((f for f in archivos if "ndwi" in f.name.lower() and f.suffix == ".nc"), None)
    if not (f_ndvi and f_ndwi):
        _faltante("GEE", archivos)
        return

    with st.spinner("Preparando visor GEE…"):
        b = _bundle_gee(gdf, str(f_ndvi), str(f_ndwi), (f_ndvi.stat().st_mtime, f_ndwi.stat().st_mtime))

    times, sin_nubes = b["times"], b["sin_nubes"]
    ndvi, ndwi = _serie_area(b["stats"], "ndvi"), _serie_area(b["stats"], "ndwi")
    s_v, s_w = RASTER_VARS["ndvi"], RASTER_VARS["ndwi"]
    dias_validos = int(np.isfinite(ndvi).sum())
    ny, nx = b["forma"]

    def _rango(serie):
        return f"{np.nanmin(serie):.2f} a {np.nanmax(serie):.2f}" if np.isfinite(serie).any() else "sin datos"

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        metric_card("NDVI medio", s_v.fmt(np.nanmean(ndvi)) if dias_validos else "—", delta=_rango(ndvi),
                    delta_description="rango diario", neutral_delta=True,
                    chart=[round(float(v), 3) for v in ndvi if np.isfinite(v)], chart_type="line",
                    help="Promedio de las series zonales de todos los barrios (días sin nubes).")
    with k2:
        metric_card("NDWI medio", s_w.fmt(np.nanmean(ndwi)) if dias_validos else "—", delta=_rango(ndwi),
                    delta_description="rango diario", neutral_delta=True,
                    chart=[round(float(v), 3) for v in ndwi if np.isfinite(v)], chart_type="line")
    with k3:
        metric_card("Días con datos", f"{dias_validos} de {len(times)}",
                    delta=f"{np.mean(sin_nubes):.0f} % de celdas sin nubes en promedio", neutral_delta=True,
                    chart=np.round(sin_nubes, 0).tolist(), chart_type="bar",
                    help="Un día cuenta si al menos un barrio tiene píxeles despejados.")
    with k4:
        metric_card("Resolución espacial", _resolucion(b["res"]), delta=f"Grilla {ny} × {nx} celdas",
                    neutral_delta=True)

    st.iframe(b["html"], height=MAP_HEIGHT)
    st.caption("Las celdas vacías corresponden a nubes o sombras enmascaradas ese día. "
               "Desplace el cursor para leer la celda y el promedio zonal del barrio.")
    _bloque_extent(b["extent"], unidad="celdas 1 km")

    section_title("Series diarias", "Promedio de las estadísticas zonales de todos los barrios; los huecos son días nublados.")
    c1, c2, c3 = st.columns(3)
    for col, serie, spec, clave in ((c1, ndvi, s_v, "gee_ndvi"), (c2, ndwi, s_w, "gee_ndwi")):
        with col:
            st.markdown(f"**{spec.label}**")
            ref = float(np.nanmean(serie)) if dias_validos else None
            mostrar(serie_temporal(times, serie, spec, height=240, referencia=ref), key=clave)
    with c3:
        st.markdown("**Celdas sin nubes**")
        spec_c = VarSpec("Celdas sin nubes", "%", "diaria", "Blues_09", "barra", 0)
        mostrar(serie_temporal(times, sin_nubes, spec_c, height=240), key="gee_nubes")

    section_title("Resumen por barrio", "Estadísticos del periodo sobre los días con píxeles despejados.")
    filas = []
    for s in b["stats"]:
        v = np.array([np.nan if x is None else x for x in s["ndvi"]], float)
        w = np.array([np.nan if x is None else x for x in s["ndwi"]], float)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            filas.append({
                "Barrio": s["nom"], "Celdas 1 km": s["n_pix"], "Días válidos": int(np.isfinite(v).sum()),
                # Mini-gráficos solo con días despejados (no admiten huecos)
                "NDVI medio": np.nanmean(v), "NDVI diario": [x for x in s["ndvi"] if x is not None],
                "NDWI medio": np.nanmean(w), "NDWI diario": [x for x in s["ndwi"] if x is not None],
            })
    df = pd.DataFrame(filas).sort_values("NDVI medio", ascending=False)
    st.dataframe(
        df,
        hide_index=True,
        height=380,
        column_config={
            "Barrio": st.column_config.TextColumn(pinned=True),
            "Celdas 1 km": st.column_config.NumberColumn(format="%d", width="small"),
            "Días válidos": st.column_config.ProgressColumn(format="%d", min_value=0, max_value=len(times)),
            "NDVI medio": st.column_config.NumberColumn(format="%.3f"),
            "NDVI diario": st.column_config.LineChartColumn(),
            "NDWI medio": st.column_config.NumberColumn(format="%.3f"),
            "NDWI diario": st.column_config.LineChartColumn(),
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
