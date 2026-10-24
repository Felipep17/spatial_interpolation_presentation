from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from components.charts import barras_h, mostrar, series_multiples
from components.theme import RASTER_VARS
from components.ui import empty_state, metric_card, render_header, section_title, tabla_resumen, tarjetas_fuentes
from datos import FUENTES_META, cargar_todas, resolucion, serie_area
from utils import cargar_y_procesar_estaciones


def _periodo(times) -> str:
    return f"{times[0]:%d/%m} – {times[-1]:%d/%m/%Y}"


def render(gdf, inputs_path: Path, paginas: dict | None = None):
    with st.spinner("Preparando el panorama de fuentes…"):
        bundles = cargar_todas(gdf, inputs_path)
    csv = inputs_path / "climaticas_post_calidad.csv"
    df_sem, est_info = cargar_y_procesar_estaciones(csv) if csv.exists() else (None, None)

    render_header(
        title="Panorama hidrometeorológico de Cali",
        subtitle="Resumen de las fuentes integradas, su capacidad de distinguir barrios y la concordancia "
                 "entre productos de precipitación.",
        eyebrow="Proyecto Dengue.IA Cali",
        badges=[("Fuentes raster", "violet", str(len(bundles))), ("Barrios", "gray", f"{len(gdf):,}"),
                ("Estaciones", "green", str(est_info["Estacion"].nunique()) if est_info is not None else "—")],
    )
    if not bundles:
        empty_state("Sin fuentes procesadas", "Agregue NetCDF en inputs/raster para ver el panorama.")
        return

    # ---------------------------------------------------------------------
    # Indicadores principales
    # ---------------------------------------------------------------------
    p_ch = serie_area(bundles["CHIRPS"]["stats"], "p") if "CHIRPS" in bundles else None
    p_ms = serie_area(bundles["MSWEP"]["stats"], "p") if "MSWEP" in bundles else None
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        metric_card("Barrios analizados", f"{len(gdf):,}", delta="Unidad de análisis zonal", neutral_delta=True)
    with k2:
        metric_card("Fuentes raster", str(len(bundles)),
                    delta=" · ".join(FUENTES_META[f]["corto"] for f in bundles), neutral_delta=True)
    with k3:
        if est_info is not None:
            metric_card("Estaciones in situ", str(est_info["Estacion"].nunique()),
                        delta=f"{df_sem['Fecha'].min():%Y} – {df_sem['Fecha'].max():%Y}", neutral_delta=True)
    with k4:
        if p_ch is not None and p_ms is not None:
            r = float(pd.Series(p_ch).corr(pd.Series(p_ms)))
            metric_card("Concordancia CHIRPS–MSWEP", f"r = {r:.2f}", delta="Correlación diaria del promedio de barrios",
                        neutral_delta=True,
                        help="Correlación de Pearson entre las series diarias de precipitación promedio de los barrios.")

    # ---------------------------------------------------------------------
    # Tarjetas de fuentes
    # ---------------------------------------------------------------------
    section_title("Fuentes de datos", "Resolución, periodo y cuántas celdas de cada grilla cubren realmente a Cali.")
    tarjetas = []
    for f, b in bundles.items():
        ext = b["extent"]
        distingue = 100 - 100 * ext["barrios_una_celda"] / ext["n_barrios"]
        tarjetas.append({
            "nombre": FUENTES_META[f]["corto"], "etiqueta": resolucion(b["res"]).split(" · ")[1],
            "tono": "green" if b["res"] < 0.05 else "blue", "variables": FUENTES_META[f]["variables"],
            "filas": [("Periodo", _periodo(b["times"])), ("Días", f"{len(b['times'])}"),
                      ("Celdas sobre Cali", f"{ext['tocan_cali']:,}"),
                      ("Celdas por barrio", f"mediana {ext['por_barrio_mediana']:.0f}")],
            "medidor": distingue, "medidor_label": "Barrios con más de una celda",
        })
    if est_info is not None:
        tarjetas.append({
            "nombre": "Estaciones", "etiqueta": "puntual", "tono": "gray",
            "variables": "Precipitación · Temperatura · Humedad · Viento · Radiación",
            "filas": [("Periodo", f"{df_sem['Fecha'].min():%m/%Y} – {df_sem['Fecha'].max():%m/%Y}"),
                      ("Agregación", "semana epidemiológica"),
                      ("Estaciones", f"{est_info['Estacion'].nunique()}"),
                      ("Registros semanales", f"{len(df_sem):,}")],
        })
    tarjetas_fuentes(tarjetas)

    if paginas:
        enlaces = st.columns(len(paginas))
        for col, (texto, (pagina, icono)) in zip(enlaces, paginas.items(), strict=True):
            with col:
                st.page_link(pagina, label=texto, icon=icono, width="stretch")

    # ---------------------------------------------------------------------
    # Resolución efectiva sobre Cali
    # ---------------------------------------------------------------------
    section_title("¿Cuánto distingue cada fuente entre barrios?",
                  "Una fuente gruesa asigna el mismo valor a muchos barrios vecinos; la grilla de 1 km los separa.")
    nombres = [FUENTES_META[f]["corto"] for f in bundles]
    gee = FUENTES_META["GEE"]["corto"] if "GEE" in bundles else None
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Celdas de la grilla que tocan Cali**")
        mostrar(barras_h(nombres, [b["extent"]["tocan_cali"] for b in bundles.values()],
                         height=60 + 42 * len(nombres), destacar=gee), key="pan_celdas")
    with c2:
        st.markdown("**Barrios que caen en una sola celda**")
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
            section_title("Precipitación: CHIRPS frente a MSWEP",
                          f"Promedio diario de los barrios · {_periodo(comunes)}.")
            g, t = st.columns([2.2, 1], gap="medium")
            with g:
                mostrar(series_multiples(comunes, {"CHIRPS": sc.values, "MSWEP": sm.values}, RASTER_VARS["p"],
                                         height=320, forma="barra"), key="pan_precip")
            with t:
                dif = sm - sc
                tabla_resumen([
                    ("Acumulado CHIRPS", f"{sc.sum():,.1f} mm"),
                    ("Acumulado MSWEP", f"{sm.sum():,.1f} mm"),
                    ("Diferencia (MSWEP − CHIRPS)", f"{sm.sum() - sc.sum():+,.1f} mm"),
                    ("Días ≥ 1 mm", f"CHIRPS {(sc >= 1).sum()} · MSWEP {(sm >= 1).sum()}"),
                    ("Día más lluvioso", f"CHIRPS {sc.idxmax():%d/%m} · MSWEP {sm.idxmax():%d/%m}"),
                    ("Correlación diaria", f"{sc.corr(sm):.2f}"),
                    ("Error absoluto medio", f"{np.mean(np.abs(dif)):.2f} mm/día"),
                ])
                st.caption("Las dos fuentes no son independientes: CHIRPS y MSWEP incorporan pluviómetros, "
                           "por lo que la concordancia no equivale a validación.")
