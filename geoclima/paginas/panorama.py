from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from geoclima.datos.barrios import orden_comunas, preparar_barrios
from geoclima.datos.estaciones import cargar_y_procesar_estaciones, periodo_estaciones
from geoclima.datos.fuentes import (
    FUENTES_META,
    cargar_todas,
    indicadores_disponibles,
    meta_txt,
    resolucion,
    serie_area,
)
from geoclima.paginas.explorador import TODA_CALI, explorador
from geoclima.ui.componentes import (
    empty_state,
    metric_card,
    render_header,
    section_title,
    tabla_resumen,
    tarjetas_fuentes,
)
from geoclima.ui.graficos import barras_comunas, barras_h, cobertura_temporal, mostrar, series_multiples
from geoclima.ui.i18n import rango_fechas, t, t_comuna
from geoclima.ui.tema import COLORS, RASTER_VARS, SERIE_COLORES

# Accesos a los módulos: (clave en `paginas`, clave del título, clave de la descripción)
MODULOS = [
    ("satelital", "nav.satelital", "pan.mod_fuentes"),
    ("estaciones", "nav.estaciones", "pan.mod_estaciones"),
    ("barrio", "nav.barrio", "pan.mod_barrio"),
]


@st.fragment
def _mapa_y_comunas(barrios, bundles: dict):
    """Explorador de barrios y promedio por comuna del indicador elegido.

    Es un fragmento: elegir indicador, ámbito o barrio solo vuelve a ejecutar este bloque, no toda la página.
    """
    ind, vals, ambito, foco = explorador(barrios, bundles, indicadores_disponibles(bundles), key="pan")

    # Promedio por comuna con la misma escala de color del mapa
    comunas = orden_comunas(barrios["comuna"])
    por_comuna = pd.Series(vals).groupby(barrios["comuna"].to_numpy()).mean().reindex(comunas)
    section_title(t("pan.por_comuna", ind=ind.etiqueta), t("pan.por_comuna_cap"))
    mostrar(barras_comunas([t_comuna(c) for c in por_comuna.index], por_comuna.to_numpy(), ind.spec,
                           unidad=ind.spec.unidad, destacar=None if ambito == TODA_CALI else t_comuna(ambito),
                           referencia=float(np.nanmean(vals))),
            key="pan_comunas")


def render(gdf, inputs_path: Path, paginas: dict | None = None):
    with st.spinner(t("pan.preparando")):
        bundles = cargar_todas(gdf, inputs_path)
    csv = inputs_path / "climaticas_post_calidad.csv"
    df_sem, est_info = cargar_y_procesar_estaciones(csv) if csv.exists() else (None, None)
    # Periodo de los registros diarios (las fechas semanales llevan el sábado de cierre)
    est_periodo = rango_fechas(*periodo_estaciones(str(csv), csv.stat().st_mtime)) if csv.exists() else ""
    barrios = preparar_barrios(gdf)
    n_comunas = len([c for c in set(barrios["comuna"]) if c.startswith("Comuna")])

    render_header(
        title=t("pan.titulo"),
        subtitle=t("pan.subtitulo"),
        eyebrow=t("pan.eyebrow"),
        badges=[(t("gen.fuentes_raster"), "violet", str(len(bundles))), (t("gen.barrios"), "gray", f"{len(gdf):,}"),
                (t("gen.estaciones"), "green", str(est_info["Estacion"].nunique()) if est_info is not None else "—")],
    )
    if not bundles:
        empty_state(t("pan.sin_fuentes"), t("pan.sin_fuentes_cuerpo"))
        return

    # ---------------------------------------------------------------------
    # Indicadores principales
    # ---------------------------------------------------------------------
    p_ch = serie_area(bundles["CHIRPS"]["stats"], "p") if "CHIRPS" in bundles else None
    p_ms = serie_area(bundles["MSWEP"]["stats"], "p") if "MSWEP" in bundles else None
    resoluciones = [b["res"] * 111.32 for b in bundles.values()]
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        metric_card(t("pan.kpi_barrios"), f"{len(gdf):,}",
                    delta=t("pan.kpi_barrios_delta", n=n_comunas) if n_comunas else t("pan.kpi_barrios_unidad"),
                    neutral_delta=True, height="content")
    with k2:
        metric_card(t("gen.fuentes_raster"), str(len(bundles)),
                    delta=t("pan.kpi_resolucion", a=f"{min(resoluciones):.0f}", b=f"{max(resoluciones):.0f}"),
                    neutral_delta=True,
                    height="content", help=" · ".join(FUENTES_META[f]["nombre"] for f in bundles))
    with k3:
        if est_info is not None:
            metric_card(t("pan.kpi_estaciones"), str(est_info["Estacion"].nunique()),
                        delta=est_periodo, neutral_delta=True,
                        height="content")
    with k4:
        if p_ch is not None and p_ms is not None:
            r = float(pd.Series(p_ch).corr(pd.Series(p_ms)))
            metric_card(t("pan.kpi_concordancia"), f"r = {r:.2f}", delta=t("pan.kpi_concordancia_delta"),
                        neutral_delta=True, height="content", help=t("pan.kpi_concordancia_ayuda"))

    # ---------------------------------------------------------------------
    # Mapa de barrios
    # ---------------------------------------------------------------------
    section_title(t("pan.mapa"), t("pan.mapa_cap"))
    _mapa_y_comunas(barrios, bundles)

    # ---------------------------------------------------------------------
    # Fuentes de datos
    # ---------------------------------------------------------------------
    section_title(t("pan.fuentes"), t("pan.fuentes_cap"))
    tarjetas = []
    for f, b in bundles.items():
        ext = b["extent"]
        distingue = 100 - 100 * ext["barrios_una_celda"] / ext["n_barrios"]
        tarjetas.append({
            "nombre": FUENTES_META[f]["corto"], "etiqueta": resolucion(b["res"]).split(" · ")[1],
            "tono": "green" if b["res"] < 0.05 else "blue", "variables": meta_txt(f, "variables"),
            "filas": [(t("gen.periodo"), rango_fechas(b["times"][0], b["times"][-1])),
                      (t("gen.dias"), f"{len(b['times'])}"),
                      (t("pan.celdas_cali"), f"{ext['tocan_cali']:,}"),
                      (t("pan.celdas_barrio"), t("gen.mediana", n=f"{ext['por_barrio_mediana']:.0f}"))],
            "medidor": distingue, "medidor_label": t("pan.mas_de_una"),
        })
    # Las estaciones ya tienen su KPI y su nota de cobertura: la rejilla queda solo con las fuentes raster
    tarjetas_fuentes(tarjetas)

    # Cobertura temporal: deja ver de un vistazo qué fuentes comparten periodo
    # El mes que comparten más fuentes va en azul; las que cubren otro mes, en naranja
    mes = {f: (b["times"][0].year, b["times"][0].month) for f, b in bundles.items()}
    mes_comun = pd.Series(list(mes.values())).mode().iloc[0]
    filas = [{"fuente": FUENTES_META[f]["corto"], "inicio": b["times"][0], "fin": b["times"][-1],
              "color": SERIE_COLORES[0] if mes[f] == mes_comun else COLORS["highlight"],
              "texto": rango_fechas(b["times"][0], b["times"][-1])} for f, b in bundles.items()]
    st.markdown(f"**{t('pan.cobertura')}**")
    mostrar(cobertura_temporal(filas), key="pan_cobertura")
    notas = []
    if len(set(mes.values())) > 1:
        notas.append(t("pan.nota_otro_mes"))
    if df_sem is not None:
        notas.append(t("pan.nota_estaciones", periodo=est_periodo))
    if notas:
        st.caption(" ".join(notas))

    # ---------------------------------------------------------------------
    # Resolución efectiva sobre Cali
    # ---------------------------------------------------------------------
    section_title(t("pan.distingue"), t("pan.distingue_cap"))
    nombres = [FUENTES_META[f]["corto"] for f in bundles]
    gee = FUENTES_META["GEE"]["corto"] if "GEE" in bundles else None
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**{t('pan.celdas_tocan')}**")
        mostrar(barras_h(nombres, [b["extent"]["tocan_cali"] for b in bundles.values()],
                         height=60 + 42 * len(nombres), destacar=gee), key="pan_celdas")
    with c2:
        st.markdown(f"**{t('pan.una_celda')}**")
        pct = [100 * b["extent"]["barrios_una_celda"] / b["extent"]["n_barrios"] for b in bundles.values()]
        mostrar(barras_h(nombres, pct, sufijo=" %", height=60 + 42 * len(nombres), destacar=gee, rango=(0, 112)),
                key="pan_unacelda")

    # ---------------------------------------------------------------------
    # CHIRPS frente a MSWEP
    # ---------------------------------------------------------------------
    if p_ch is not None and p_ms is not None:
        t_ch, t_ms = bundles["CHIRPS"]["times"], bundles["MSWEP"]["times"]
        comunes = t_ch.intersection(t_ms)
        if len(comunes):
            sc = pd.Series(p_ch, index=t_ch).loc[comunes]
            sm = pd.Series(p_ms, index=t_ms).loc[comunes]
            section_title(t("pan.chirps_mswep"),
                          t("pan.chirps_mswep_cap", periodo=rango_fechas(comunes[0], comunes[-1])))
            g, c_tabla = st.columns([2.2, 1], gap="medium")
            with g:
                mostrar(series_multiples(comunes, {"CHIRPS": sc.values, "MSWEP": sm.values}, RASTER_VARS["p"],
                                         height=320, forma="barra"), key="pan_precip")
            with c_tabla:
                dif = sm - sc
                tabla_resumen([
                    (t("pan.acum", f="CHIRPS"), f"{sc.sum():,.1f} mm"),
                    (t("pan.acum", f="MSWEP"), f"{sm.sum():,.1f} mm"),
                    (t("pan.diferencia"), f"{sm.sum() - sc.sum():+,.1f} mm"),
                    (t("pan.dias_1mm"), f"CHIRPS {(sc >= 1).sum()} · MSWEP {(sm >= 1).sum()}"),
                    (t("pan.dia_lluvioso"), f"CHIRPS {sc.idxmax():%d/%m} · MSWEP {sm.idxmax():%d/%m}"),
                    (t("pan.correlacion"), f"{sc.corr(sm):.2f}"),
                    (t("pan.mae"), t("pan.mm_dia", v=f"{np.mean(np.abs(dif)):.2f}")),
                ])
                st.caption(t("pan.no_independientes"))

    # ---------------------------------------------------------------------
    # Accesos a los módulos
    # ---------------------------------------------------------------------
    if paginas:
        section_title(t("pan.explorar"))
        cols = st.columns(len(MODULOS))
        for n, (col, (clave, titulo, desc)) in enumerate(zip(cols, MODULOS, strict=True)):
            if clave not in paginas:
                continue
            pagina, icono = paginas[clave]
            with col, st.container(border=True, key=f"gc_nav_{n}", height="stretch"):
                st.page_link(pagina, label=f"**{t(titulo)}**", icon=icono)
                st.html(f'<p class="gc-nav-desc">{t(desc)}</p>')
