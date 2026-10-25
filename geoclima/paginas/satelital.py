import warnings
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from geoclima.datos.barrios import geojson_barrios, orden_comunas, preparar_barrios
from geoclima.datos.fuentes import (
    FUENTES_META,
    INDICADORES,
    archivos_fuente,
    cargar,
    mapa_html,
    meta_txt,
    resolucion,
    serie_area,
)
from geoclima.datos.raster import listar_fuentes
from geoclima.paginas.explorador import TODA_CALI, explorador, nombre_ambito
from geoclima.ui.componentes import (
    boton_descarga,
    empty_state,
    metric_card,
    render_header,
    section_title,
    tabla_resumen,
)
from geoclima.ui.graficos import mostrar, serie_temporal
from geoclima.ui.i18n import conservar, t, t_comuna
from geoclima.ui.navegacion import enlace_barrio
from geoclima.ui.tema import MAP_HEIGHT, RASTER_VARS, VarSpec

# Las etiquetas también van en la URL (?fuente=…&vista=…): cortas y sin símbolos
VISTAS = {"diario": "sat.vista_diario", "periodo": "sat.vista_periodo"}
ETIQUETA_FUENTE = {"C3S": "AgERA5", "CHIRPS": "CHIRPS", "MSWEP": "MSWEP", "GEE": "MODIS"}


@st.fragment
def _explorador_fuente(gdf, b: dict, fuente: str):
    """Mapa por barrio de la fuente. Fragmento: sus controles y clics no vuelven a ejecutar toda la página."""
    indicadores = [i for i in INDICADORES if i.fuente == fuente]
    explorador(preparar_barrios(gdf), {fuente: b}, indicadores, key=f"sat_{fuente.lower()}", alto=MAP_HEIGHT)


def _visor(gdf, b: dict, fuente: str, rutas: dict, ayuda: str):
    """Visor diario (raster por píxel) o coropleta del periodo por barrio, a elección del usuario."""
    conservar("vista")
    vista = st.segmented_control(t("sat.vista"), list(VISTAS), format_func=lambda v: t(VISTAS[v]), default="diario",
                                 required=True, key="vista", bind="query-params", label_visibility="collapsed",
                                 help=t("sat.vista_ayuda"))
    if vista == "periodo":
        _explorador_fuente(gdf, b, fuente)
        return
    html = mapa_html(fuente, gdf, rutas)  # HTML por idioma, sobre el bundle ya cacheado
    st.iframe(html, height=MAP_HEIGHT)
    c_txt, c_dl = st.columns([4, 1], vertical_alignment="center")
    with c_txt:
        st.caption(ayuda)
    with c_dl:
        st.download_button(t("dl.html"), partial(str.encode, html, "utf-8"), file_name=f"visor_{fuente.lower()}.html",
                           mime="text/html", on_click="ignore", icon=":material/download:", type="tertiary",
                           key=f"dl_html_{fuente}", help=t("dl.html_ayuda"))


def _enlaces_oficiales(activa: str):
    """Sitio oficial de cada fuente, con la elegida resaltada."""
    with st.container(horizontal=True, vertical_alignment="center", gap="small"):
        st.caption(t("sat.sitios_oficiales"))
        for f, meta in FUENTES_META.items():
            st.link_button(meta["corto"], meta["url"], icon=":material/open_in_new:", icon_position="right",
                           type="primary" if f == activa else "secondary",
                           help=t("sat.sitio_oficial_ayuda", n=meta["nombre"]))


@st.fragment
def _tabla_barrios(gdf, df: pd.DataFrame, column_config: dict, nombre: str, key: str):
    """Tabla por barrio con comuna, filtro por comuna, enlace al perfil y descargas CSV/GeoJSON.

    `df` trae la columna del barrio con el encabezado traducido (t("gen.barrio")). Es un fragmento: filtrar o
    elegir una fila no vuelve a ejecutar la página ni a enviar el visor de arriba.
    """
    barrio, comuna = t("gen.barrio"), t("gen.comuna")
    barrios = preparar_barrios(gdf)
    df = df.merge(barrios[["nombre_barrio", "comuna"]].rename(columns={"nombre_barrio": barrio, "comuna": "_comuna"}),
                  on=barrio, how="left")
    df.insert(1, comuna, df["_comuna"].map(t_comuna))
    c_fil, c_link = st.columns([1, 2], vertical_alignment="bottom")
    conservar(f"{key}_comuna")
    with c_fil:
        ambito = st.selectbox(comuna, [TODA_CALI, *orden_comunas(barrios["comuna"])], key=f"{key}_comuna",
                              format_func=nombre_ambito)
    if ambito != TODA_CALI:
        df = df[df["_comuna"] == ambito]
    df = df.drop(columns="_comuna")
    evento = st.dataframe(
        df, hide_index=True, height=380, on_select="rerun", selection_mode="single-row", key=f"{key}_tabla",
        column_config={barrio: st.column_config.TextColumn(pinned=True), comuna: st.column_config.TextColumn(),
                       **column_config},
    )
    filas = evento.selection.rows if evento else []
    with c_link:
        if filas:
            enlace_barrio(df.iloc[filas[0]][barrio])
        else:
            st.caption(f":material/touch_app: {t('sat.fila_pista')}")
    boton_descarga(df, nombre, key=key, geojson=partial(geojson_barrios, barrios, df, barrio))


def _bloque_extent(r: dict, clave_unidad: str = "sat.pixeles_barrio"):
    """Cuántas celdas tiene la grilla de la fuente y cuántas cubren realmente a Cali."""
    ny, nx = r["forma"]
    section_title(t("sat.grilla"), t("sat.grilla_cap"))
    tabla_resumen([
        (t("gen.resolucion"), resolucion(r["res"])),
        (t("sat.celdas_extent"), f"{r['total']:,} ({ny} × {nx})"),
        (t("sat.celdas_tocan"), t("sat.celdas_tocan_val", n=f"{r['tocan_cali']:,}",
                                  pct=f"{100 * r['tocan_cali'] / max(r['total'], 1):.0f}")),
        (t("sat.celdas_50"), f"{r['dentro_50']:,}"),
        (t(clave_unidad), t("gen.mediana_max", m=f"{r['por_barrio_mediana']:.0f}", x=r["por_barrio_max"])),
        (t("sat.barrios_una_celda"), t("gen.a_de_b_pct", a=f"{r['barrios_una_celda']:,}", b=f"{r['n_barrios']:,}",
                                       pct=f"{100 * r['barrios_una_celda'] / r['n_barrios']:.0f}")),
    ])


# =========================================================================
# Render
# =========================================================================
def render(gdf, inputs_path: Path):
    fuentes = listar_fuentes(inputs_path / "raster")

    render_header(
        title=t("sat.titulo"),
        subtitle=t("sat.subtitulo"),
        eyebrow=t("sat.eyebrow"),
        badges=[(t("gen.fuentes"), "violet", str(len(fuentes))), (t("gen.barrios"), "gray", f"{len(gdf):,}")],
    )

    if not fuentes:
        empty_state(t("gen.sin_fuentes_raster"), t("sat.sin_carpetas"))
        return

    opciones = list(fuentes)
    nombre = st.segmented_control(
        t("sat.fuente"),
        opciones,
        default=opciones[0],
        required=True,
        key="fuente",
        bind="query-params",
        format_func=lambda k: ETIQUETA_FUENTE.get(k.upper(), k),
        label_visibility="collapsed",
    )
    lista = fuentes[nombre]
    fuente = nombre.upper()
    if fuente in FUENTES_META:
        section_title(FUENTES_META[fuente]["nombre"], meta_txt(fuente, "desc"))
    _enlaces_oficiales(fuente)

    rutas = archivos_fuente(fuente, lista)
    if fuente == "C3S":
        if rutas:
            _render_c3s(gdf, rutas)
        else:
            empty_state(t("sat.incompletos"), t("sat.incompletos_cuerpo"))
    elif fuente in ("CHIRPS", "MSWEP"):
        if rutas:
            _render_precip(gdf, rutas, fuente)
        else:
            _faltante(fuente, lista)
    elif fuente == "GEE":
        if rutas:
            _render_gee(gdf, rutas)
        else:
            _faltante(fuente, lista)
    else:
        _render_inventario(nombre, lista)


def _render_c3s(gdf, rutas: dict):
    with st.spinner(t("sat.preparando", f="C3S")):
        b = cargar("C3S", gdf, rutas)

    times = b["times"]
    rh, tx = serie_area(b["stats"], "rh"), serie_area(b["stats"], "t")
    s_rh, s_t = RASTER_VARS["rh"], RASTER_VARS["t"]
    periodo = f"{times[0]:%d/%m/%Y} – {times[-1]:%d/%m/%Y}"

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        metric_card(t("sat.kpi_hr"), s_rh.fmt(np.nanmean(rh)),
                    delta=f"{np.nanmin(rh):.0f}–{np.nanmax(rh):.0f} %", delta_description=t("gen.rango_diario"),
                    neutral_delta=True, chart=np.round(rh, 1).tolist(), chart_type="area",
                    help=t("gen.promedio_series_todos"))
    with k2:
        metric_card(t("sat.kpi_tmax"), s_t.fmt(np.nanmean(tx)),
                    delta=f"{np.nanmin(tx):.1f}–{np.nanmax(tx):.1f} °C", delta_description=t("gen.rango_diario"),
                    neutral_delta=True, chart=np.round(tx, 1).tolist(), chart_type="area")
    with k3:
        metric_card(t("sat.kpi_ultimo"), s_t.fmt(tx[-1]),
                    delta=f"{float(tx[-1] - np.nanmean(tx)):+.1f} °C", delta_description=t("sat.vs_media_periodo"),
                    delta_color="off", neutral_delta=True, help=f"{times[-1]:%d/%m/%Y}")
    with k4:
        metric_card(t("sat.kpi_cobertura"), t("gen.n_dias", n=len(times)), delta=periodo, neutral_delta=True,
                    help=t("gen.resolucion_de", r=resolucion(b["res"])))

    _visor(gdf, b, "C3S", rutas, t("sat.ayuda_visor"))
    _bloque_extent(b["extent"])

    section_title(t("gen.series_diarias"), t("gen.promedio_zonal_todos"))
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**{s_rh.label}**")
        mostrar(serie_temporal(times, rh, s_rh, height=260, referencia=float(np.nanmean(rh))), key="c3s_rh")
    with c2:
        st.markdown(f"**{s_t.label}**")
        mostrar(serie_temporal(times, tx, s_t, height=260, referencia=float(np.nanmean(tx))), key="c3s_t")

    section_title(t("sat.resumen"), t("sat.resumen_cap"))
    c = {k: t(f"col.{k}") for k in ("pixeles", "hr_media", "hr_diaria", "tmax_media", "tmax_max", "tmax_diaria")}
    filas = []
    for s in b["stats"]:
        v_rh = np.array([np.nan if v is None else v for v in s["rh"]], float)
        v_t = np.array([np.nan if v is None else v for v in s["t"]], float)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            filas.append({
                t("gen.barrio"): s["nom"], c["pixeles"]: s["n_pix"],
                c["hr_media"]: np.nanmean(v_rh), c["hr_diaria"]: s["rh"],
                c["tmax_media"]: np.nanmean(v_t), c["tmax_max"]: np.nanmax(v_t), c["tmax_diaria"]: s["t"],
            })
    df = pd.DataFrame(filas).sort_values(c["tmax_media"], ascending=False)
    _tabla_barrios(gdf, df, {
        c["pixeles"]: st.column_config.NumberColumn(format="%d", width="small"),
        c["hr_media"]: st.column_config.NumberColumn(format="%.1f"),
        c["hr_diaria"]: st.column_config.LineChartColumn(),
        c["tmax_media"]: st.column_config.NumberColumn(format="%.1f"),
        c["tmax_max"]: st.column_config.NumberColumn(format="%.1f"),
        c["tmax_diaria"]: st.column_config.LineChartColumn(),
    }, "barrios_agera5_c3s", key="dl_c3s")


def _render_precip(gdf, rutas: dict, fuente: str):
    with st.spinner(t("sat.preparando", f=fuente)):
        b = cargar(fuente, gdf, rutas)

    times = b["times"]
    p = serie_area(b["stats"], "p")
    spec = RASTER_VARS["p"]
    i_max = int(np.nanargmax(p))
    dias_lluvia = int(np.sum(p >= 1))

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        metric_card(t("sat.kpi_acum"), f"{np.nansum(p):,.1f} mm",
                    delta=f"{times[0]:%d/%m} – {times[-1]:%d/%m/%Y}", neutral_delta=True,
                    chart=np.round(p, 2).tolist(), chart_type="bar", help=t("sat.kpi_acum_ayuda"))
    with k2:
        metric_card(t("sat.kpi_dias_lluvia"), t("gen.a_de_b", a=dias_lluvia, b=len(times)),
                    delta=t("sat.kpi_dias_lluvia_delta", pct=f"{100 * dias_lluvia / len(times):.0f}"),
                    neutral_delta=True, help=t("sat.kpi_dias_lluvia_ayuda"))
    with k3:
        metric_card(t("sat.kpi_max_diario"), spec.fmt(p[i_max]), delta=f"{times[i_max]:%d/%m/%Y}",
                    neutral_delta=True)
    with k4:
        metric_card(t("gen.resolucion_espacial"), resolucion(b["res"]), delta=t("sat.grilla_nativa"),
                    neutral_delta=True)

    _visor(gdf, b, fuente, rutas, t("sat.ayuda_visor"))
    _bloque_extent(b["extent"])

    section_title(t("mapa.precip_diaria"), t("gen.promedio_zonal_todos"))
    mostrar(serie_temporal(times, p, spec, height=280), key=f"{fuente.lower()}_p")

    section_title(t("sat.resumen"), t("sat.resumen_cap"))
    c = {k: t(f"col.{k}") for k in ("pixeles", "acumulado", "max_diario", "dias_1mm", "precip_diaria")}
    filas = []
    for s in b["stats"]:
        v = np.array([np.nan if x is None else x for x in s["p"]], float)
        filas.append({
            t("gen.barrio"): s["nom"], c["pixeles"]: s["n_pix"],
            c["acumulado"]: np.nansum(v), c["max_diario"]: np.nanmax(v) if np.isfinite(v).any() else np.nan,
            c["dias_1mm"]: int(np.sum(v >= 1)), c["precip_diaria"]: s["p"],
        })
    df = pd.DataFrame(filas).sort_values(c["acumulado"], ascending=False)
    _tabla_barrios(gdf, df, {
        c["pixeles"]: st.column_config.NumberColumn(format="%d", width="small"),
        c["acumulado"]: st.column_config.ProgressColumn(
            format="%.1f", min_value=0, max_value=float(df[c["acumulado"]].max() or 1)),
        c["max_diario"]: st.column_config.NumberColumn(format="%.1f"),
        c["dias_1mm"]: st.column_config.NumberColumn(format="%d"),
        c["precip_diaria"]: st.column_config.BarChartColumn(y_min=0),
    }, f"barrios_{fuente.lower()}_precipitacion", key=f"dl_{fuente.lower()}")


COMANDOS_DESCARGA = {
    "GEE": "uv run --group descarga python -m descargas.gee --project <ID_PROYECTO_GCP>",
    "MSWEP": "uv run --group descarga python -m descargas.mswep --client-secret /ruta/client.json",
    "CHIRPS": None,
}


def _faltante(fuente: str, archivos):
    """Estado vacío con la instrucción exacta para descargar la fuente."""
    empty_state(t("sat.faltante", f=fuente), t("sat.faltante_cuerpo"))
    if COMANDOS_DESCARGA.get(fuente):
        st.code(COMANDOS_DESCARGA[fuente], language="bash")
    if archivos:
        _render_inventario(fuente, archivos)


def _render_gee(gdf, rutas: dict):
    with st.spinner(t("sat.preparando", f="GEE")):
        b = cargar("GEE", gdf, rutas)

    times, sin_nubes = b["times"], b["sin_nubes"]
    ndvi, ndwi = serie_area(b["stats"], "ndvi"), serie_area(b["stats"], "ndwi")
    s_v, s_w = RASTER_VARS["ndvi"], RASTER_VARS["ndwi"]
    dias_validos = int(np.isfinite(ndvi).sum())
    ny, nx = b["forma"]

    def _rango(serie):
        if not np.isfinite(serie).any():
            return t("gen.sin_datos")
        return t("gen.rango_a_b", a=f"{np.nanmin(serie):.2f}", b=f"{np.nanmax(serie):.2f}")

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        metric_card(t("sat.kpi_ndvi"), s_v.fmt(np.nanmean(ndvi)) if dias_validos else "—", delta=_rango(ndvi),
                    delta_description=t("gen.rango_diario"), neutral_delta=True,
                    chart=[round(float(v), 3) for v in ndvi if np.isfinite(v)], chart_type="line",
                    help=t("sat.kpi_ndvi_ayuda"))
    with k2:
        metric_card(t("sat.kpi_ndwi"), s_w.fmt(np.nanmean(ndwi)) if dias_validos else "—", delta=_rango(ndwi),
                    delta_description=t("gen.rango_diario"), neutral_delta=True,
                    chart=[round(float(v), 3) for v in ndwi if np.isfinite(v)], chart_type="line")
    with k3:
        metric_card(t("sat.kpi_dias_datos"), t("gen.a_de_b", a=dias_validos, b=len(times)),
                    delta=t("sat.kpi_despejadas", pct=f"{np.mean(sin_nubes):.0f}"), neutral_delta=True,
                    chart=np.round(sin_nubes, 0).tolist(), chart_type="bar", help=t("sat.kpi_dias_datos_ayuda"))
    with k4:
        metric_card(t("gen.resolucion_espacial"), resolucion(b["res"]), delta=t("sat.kpi_grilla", ny=ny, nx=nx),
                    neutral_delta=True)

    _visor(gdf, b, "GEE", rutas, t("sat.ayuda_visor_gee"))
    _bloque_extent(b["extent"], clave_unidad="sat.celdas1km_barrio")

    section_title(t("gen.series_diarias"), t("sat.series_gee_cap"))
    c1, c2, c3 = st.columns(3)
    for col, serie, spec, clave in ((c1, ndvi, s_v, "gee_ndvi"), (c2, ndwi, s_w, "gee_ndwi")):
        with col:
            st.markdown(f"**{spec.label}**")
            ref = float(np.nanmean(serie)) if dias_validos else None
            mostrar(serie_temporal(times, serie, spec, height=240, referencia=ref), key=clave)
    with c3:
        spec_c = VarSpec("celdas_despejadas", "%", "diaria", "Blues_09", "barra", 0)
        st.markdown(f"**{spec_c.label}**")
        mostrar(serie_temporal(times, sin_nubes, spec_c, height=240), key="gee_nubes")

    section_title(t("sat.resumen"), t("sat.resumen_cap_gee"))
    c = {k: t(f"col.{k}") for k in ("celdas_1km", "dias_validos", "ndvi_medio", "ndvi_diario", "ndwi_medio",
                                    "ndwi_diario")}
    filas = []
    for s in b["stats"]:
        v = np.array([np.nan if x is None else x for x in s["ndvi"]], float)
        w = np.array([np.nan if x is None else x for x in s["ndwi"]], float)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            filas.append({
                t("gen.barrio"): s["nom"], c["celdas_1km"]: s["n_pix"], c["dias_validos"]: int(np.isfinite(v).sum()),
                # Mini-gráficos solo con días despejados (no admiten huecos)
                c["ndvi_medio"]: np.nanmean(v), c["ndvi_diario"]: [x for x in s["ndvi"] if x is not None],
                c["ndwi_medio"]: np.nanmean(w), c["ndwi_diario"]: [x for x in s["ndwi"] if x is not None],
            })
    df = pd.DataFrame(filas).sort_values(c["ndvi_medio"], ascending=False)
    _tabla_barrios(gdf, df, {
        c["celdas_1km"]: st.column_config.NumberColumn(format="%d", width="small"),
        c["dias_validos"]: st.column_config.ProgressColumn(format="%d", min_value=0, max_value=len(times)),
        c["ndvi_medio"]: st.column_config.NumberColumn(format="%.3f"),
        c["ndvi_diario"]: st.column_config.LineChartColumn(),
        c["ndwi_medio"]: st.column_config.NumberColumn(format="%.3f"),
        c["ndwi_diario"]: st.column_config.LineChartColumn(),
    }, "barrios_gee_ndvi_ndwi", key="dl_gee")


def _render_inventario(nombre, archivos):
    if not archivos:
        empty_state(t("sat.sin_archivos", f=nombre), t("sat.sin_archivos_cuerpo"))
        return
    tamano = t("col.tamano")
    data = pd.DataFrame([
        {t("col.archivo"): a.name, t("col.formato"): a.suffix.lstrip(".").upper(), tamano: a.stat().st_size / 2**20}
        for a in archivos
    ])
    st.dataframe(data, hide_index=True, column_config={tamano: st.column_config.NumberColumn(format="%.2f")})
