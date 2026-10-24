from pathlib import Path

import folium
import numpy as np
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from components.charts import mostrar, serie_temporal
from components.theme import COLORS, VARIABLES, colormap, escala_robusta, leyenda_html
from components.ui import empty_state, metric_card, render_header, section_title
from utils import capa_barrios, cargar_y_procesar_estaciones, mapa_base, preparar_barrios

ETIQUETAS_CORTAS = {
    "Precipitacion": "Precipitación",
    "Tmin": "T. mínima",
    "Tmax": "T. máxima",
    "Humedad relativa": "Humedad",
    "Velocidad del viento": "Viento",
    "Radiación solar": "Radiación",
}
MAPA_ALTO = 560
_PENDIENTE = "_estacion_pendiente"


@st.cache_data(show_spinner=False)
def _resumen_red(df_semanal: pd.DataFrame, variable: str) -> pd.DataFrame:
    """Estadísticos por estación para la variable activa (solo presentación)."""
    filas = []
    for est, g in df_semanal.groupby("Estacion"):
        s = g.set_index("Fecha")[variable].dropna()
        if s.empty:
            continue
        semanas = (g["Fecha"].max() - g["Fecha"].min()).days // 7 + 1
        filas.append({
            "Estación": est,
            "Media": s.mean(),
            "Máximo": s.max(),
            "Semanas con dato": len(s),
            "Completitud": 100 * len(s) / max(semanas, 1),
            "Último registro": s.index.max(),
            "Últimas 52 semanas": s.iloc[-52:].round(2).tolist(),
        })
    return pd.DataFrame(filas)


def _seleccionar(estacion: str):
    """Programa el cambio de estación para el próximo rerun (los widgets ya se crearon)."""
    if estacion and estacion != st.session_state.get("estacion_sel"):
        st.session_state[_PENDIENTE] = estacion
        st.rerun()


def render(gdf, inputs_path: Path):
    csv_file = inputs_path / "climaticas_post_calidad.csv"
    if not csv_file.exists():
        render_header("Red de estaciones meteorológicas", "Series temporales in situ.", eyebrow="Módulo 02 · In situ")
        empty_state("Sin datos de estaciones", f"No se encontró {csv_file.name} en la carpeta inputs.")
        return

    df_semanal, estaciones_info = cargar_y_procesar_estaciones(csv_file)

    render_header(
        title="Red de estaciones meteorológicas",
        subtitle="Series temporales in situ agregadas por semana, con control de completitud por estación.",
        eyebrow="Módulo 02 · In situ",
        badges=[
            ("Estaciones", "green", str(estaciones_info["Estacion"].nunique())),
            ("Periodo", "gray", f"{df_semanal['Fecha'].min():%Y} – {df_semanal['Fecha'].max():%Y}"),
            ("Agregación", "blue", "semanal"),
        ],
    )

    # ---------------------------------------------------------------------
    # Filtros
    # ---------------------------------------------------------------------
    f1, f2 = st.columns([3, 2], vertical_alignment="bottom")
    with f1:
        variable_sel = st.segmented_control(
            "Variable",
            list(VARIABLES),
            default="Precipitacion",
            required=True,
            key="variable_estaciones",
            format_func=ETIQUETAS_CORTAS.get,
        )
    spec = VARIABLES[variable_sel]

    conteos = df_semanal.groupby("Estacion")[variable_sel].count()
    con_datos = sorted(set(conteos[conteos > 0].index) & set(estaciones_info["Estacion"]))
    if not con_datos:
        empty_state("Sin registros", f"Ninguna estación tiene datos válidos de {spec.label.lower()}.")
        return

    pendiente = st.session_state.pop(_PENDIENTE, None)
    if pendiente in con_datos:
        st.session_state.estacion_sel = pendiente
    if st.session_state.get("estacion_sel") not in con_datos:
        st.session_state.estacion_sel = con_datos[0]

    with f2:
        estacion_sel = st.selectbox(
            "Estación",
            con_datos,
            key="estacion_sel",
            help="También puede seleccionarla con un clic en el mapa o en la tabla de la red.",
        )

    df_est = df_semanal[df_semanal["Estacion"] == estacion_sel].sort_values("Fecha")
    serie = df_est.set_index("Fecha")[variable_sel].dropna()
    resumen = _resumen_red(df_semanal, variable_sel)

    # ---------------------------------------------------------------------
    # KPIs con contexto comparativo
    # ---------------------------------------------------------------------
    media = float(serie.mean())
    semanas = (df_est["Fecha"].max() - df_est["Fecha"].min()).days // 7 + 1
    completitud = 100 * len(serie) / max(semanas, 1)
    tipo_chart = "bar" if spec.forma == "barra" else "line"

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        metric_card(
            "Última semana registrada", spec.fmt(serie.iloc[-1]),
            delta=round(float(serie.iloc[-1] - media), spec.decimales), delta_description="vs. media histórica",
            delta_color="off", chart=serie.iloc[-26:].round(2).tolist(), chart_type=tipo_chart,
            help=f"Semana que cierra el {serie.index[-1]:%d/%m/%Y}. Micro-gráfico: últimas 26 semanas.",
        )
    with k2:
        anual = serie.groupby(serie.index.year).mean()
        metric_card(
            "Media histórica", spec.fmt(media), delta=f"{len(serie):,} semanas", neutral_delta=True,
            chart=anual.round(2).tolist(), chart_type="line",
            help=f"{spec.agregacion.capitalize()}. Micro-gráfico: media por año.",
        )
    with k3:
        metric_card(
            "Máximo semanal", spec.fmt(serie.max()), delta=f"Semana del {serie.idxmax():%d/%m/%Y}",
            neutral_delta=True,
        )
    with k4:
        cobertura_anual = serie.groupby(serie.index.year).size() / 52 * 100
        metric_card(
            "Completitud", f"{completitud:.0f} %", delta=f"{len(serie):,} de {semanas:,} semanas",
            neutral_delta=True, chart=cobertura_anual.clip(upper=100).round(0).tolist(), chart_type="bar",
            help="Semanas con dato sobre las semanas del periodo de operación. Micro-gráfico: % por año.",
        )

    # ---------------------------------------------------------------------
    # Mapa + serie temporal
    # ---------------------------------------------------------------------
    c_mapa, c_serie = st.columns([1, 1.35], gap="medium")

    with c_mapa:
        section_title("Red de sensores", f"Color: media de {spec.label.lower()} por estación.")
        medias = resumen.set_index("Estación")["Media"]
        cm = colormap(spec.cmap, *escala_robusta(medias.values))

        m = mapa_base(gdf)
        capa_barrios(preparar_barrios(gdf), con_pixeles=False).add_to(m)

        fg = folium.FeatureGroup(name="Estaciones")
        info = estaciones_info[estaciones_info["Estacion"].isin(con_datos)]
        # La seleccionada se dibuja al final para quedar por encima
        info = info.assign(es_sel=info["Estacion"] == estacion_sel).sort_values("es_sel")
        for row in info.itertuples():
            nombre = row.Estacion
            sel = row.es_sel
            folium.CircleMarker(
                location=[row.Latitud, row.Longitud],
                radius=11 if sel else 7,
                color=COLORS["ink"] if sel else COLORS["surface"],
                weight=2.5 if sel else 2,
                fill=True,
                fill_color=cm.rgb_hex_str(medias.get(nombre, np.nan)) if nombre in medias else COLORS["muted"],
                fill_opacity=0.95,
                tooltip=nombre,
            ).add_to(fg)

        salida = st_folium(
            m,
            key="mapa_estaciones",
            height=MAPA_ALTO,
            use_container_width=True,
            feature_group_to_add=fg,
            returned_objects=["last_object_clicked_tooltip"],
        )
        st.html(leyenda_html(cm, spec, f"Media por estación · {spec.label}"))

        clic = (salida or {}).get("last_object_clicked_tooltip")
        if clic and clic != st.session_state.get("_ultimo_clic"):
            st.session_state["_ultimo_clic"] = clic
            _seleccionar(clic)

    with c_serie:
        section_title(f"{spec.label} · {estacion_sel}", f"{spec.agregacion.capitalize()} ({spec.unidad}).")
        if serie.empty:
            empty_state("Sin datos suficientes", "No hay registros para graficar esta serie.")
        else:
            fig = serie_temporal(
                df_est["Fecha"], df_est[variable_sel], spec,
                height=MAPA_ALTO - 10, referencia=media, ref_label="Media histórica", selector_rango=True,
            )
            mostrar(fig, key="serie_estacion")

    # ---------------------------------------------------------------------
    # Tabla de la red
    # ---------------------------------------------------------------------
    section_title("Resumen de la red", "Seleccione una fila para enfocar la estación.")
    tabla = resumen.sort_values("Estación").reset_index(drop=True)
    evento = st.dataframe(
        tabla,
        hide_index=True,
        height=420,
        on_select="rerun",
        selection_mode="single-row",
        key="tabla_red",
        column_config={
            "Estación": st.column_config.TextColumn(pinned=True),
            "Media": st.column_config.NumberColumn(f"Media ({spec.unidad})", format="%.1f"),
            "Máximo": st.column_config.NumberColumn(f"Máximo ({spec.unidad})", format="%.1f"),
            "Semanas con dato": st.column_config.NumberColumn(format="%d"),
            "Completitud": st.column_config.ProgressColumn(format="%.0f %%", min_value=0, max_value=100),
            "Último registro": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "Últimas 52 semanas": (
                st.column_config.BarChartColumn(y_min=0) if spec.forma == "barra"
                else st.column_config.LineChartColumn()
            ),
        },
    )
    filas = evento.selection.rows if evento else []
    if filas:
        elegido = tabla.iloc[filas[0]]["Estación"]
        if elegido != st.session_state.get("_ultima_fila"):
            st.session_state["_ultima_fila"] = elegido
            _seleccionar(elegido)
