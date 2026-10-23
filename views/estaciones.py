from pathlib import Path
import folium
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium
from components.ui import render_header, render_kpi_card
from utils import cargar_y_procesar_estaciones

UNIDADES = {
    "Precipitacion": "mm (Acumulado)",
    "Tmin": "°C",
    "Tmax": "°C",
    "Humedad relativa": "%",
    "Velocidad del viento": "m/s",
    "Radiación solar": "MJ/m²",
}


def render(gdf, inputs_path: Path):
    render_header(
        title="🌡️ Red de Estaciones Meteorológicas",
        subtitle="Visualización de series temporales in-situ agregadas por semana epidemiológica.",
        badge_text="Datos In-Situ",
        badge_type="blue",
    )

    csv_file = inputs_path / "climaticas_post_calidad.csv"
    if not csv_file.exists():
        st.error(f"❌ No se encontró el archivo de estaciones en: {csv_file}")
        return

    # Cargar datos cacheados
    df_semanal, estaciones_info = cargar_y_procesar_estaciones(csv_file)

    # 1. Selector de Variable
    variables_disponibles = [
        "Precipitacion",
        "Tmin",
        "Tmax",
        "Humedad relativa",
        "Velocidad del viento",
        "Radiación solar",
    ]

    col_filtro1, col_filtro2 = st.columns([1, 1])

    with col_filtro1:
        variable_sel = st.selectbox(
            "📌 Variable Meteorológica:",
            variables_disponibles,
            index=0,
            help="Seleccione la variable a analizar a nivel semanal.",
        )

    # Filtrar estaciones que tienen al menos un dato válido
    estaciones_con_datos = []
    for est in sorted(estaciones_info["Estacion"].unique()):
        subset = df_semanal[df_semanal["Estacion"] == est]
        if not subset.empty and subset[variable_sel].notna().sum() > 0:
            estaciones_con_datos.append(est)

    if not estaciones_con_datos:
        st.warning(f"No hay estaciones con registros válidos para '{variable_sel}'.")
        return

    if (
        "estacion_sel" not in st.session_state
        or st.session_state.estacion_sel not in estaciones_con_datos
    ):
        st.session_state.estacion_sel = estaciones_con_datos[0]

    with col_filtro2:
        estacion_sel = st.selectbox(
            "📍 Estación Seleccionada:",
            estaciones_con_datos,
            index=estaciones_con_datos.index(st.session_state.estacion_sel),
            help="Seleccione la estación meteorológica para visualizar su serie temporal.",
        )
        st.session_state.estacion_sel = estacion_sel

    # Datos de la estación y variable seleccionada
    df_estacion = df_semanal[df_semanal["Estacion"] == estacion_sel].sort_values("Fecha")
    serie_var = df_estacion[variable_sel].dropna()

    # Métricas KPI en tarjetas modernas
    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
    with col_kpi1:
        val_prom = f"{serie_var.mean():.1f} {UNIDADES.get(variable_sel, '')}" if not serie_var.empty else "--"
        render_kpi_card("Promedio Histórico", val_prom, "Media de semanas con registro")
    with col_kpi2:
        val_max = f"{serie_var.max():.1f} {UNIDADES.get(variable_sel, '')}" if not serie_var.empty else "--"
        render_kpi_card("Valor Máximo", val_max, "Pico observado en el periodo")
    with col_kpi3:
        val_min = f"{serie_var.min():.1f} {UNIDADES.get(variable_sel, '')}" if not serie_var.empty else "--"
        render_kpi_card("Valor Mínimo", val_min, "Mínimo observado")
    with col_kpi4:
        ult_reg = (
            f"{serie_var.iloc[-1]:.1f} {UNIDADES.get(variable_sel, '')}"
            if not serie_var.empty
            else "--"
        )
        render_kpi_card("Último Registro", ult_reg, "Semana más reciente")

    # Layout de dos columnas: Mapa y Gráfico interactivo
    col_mapa, col_grafico = st.columns([1, 1.2])

    with col_mapa:
        st.markdown("##### 🗺️ Red de Sensores en Santiago de Cali")
        minx, miny, maxx, maxy = gdf.total_bounds
        m = folium.Map(
            location=[(miny + maxy) / 2, (minx + maxx) / 2],
            zoom_start=11,
            tiles="CartoDB positron",
        )

        folium.GeoJson(
            gdf,
            name="Límites Cali",
            style_function=lambda x: {
                "fillColor": "#3b82f6",
                "fillOpacity": 0.04,
                "color": "#64748b",
                "weight": 1.1,
            },
        ).add_to(m)

        est_info_filtrada = estaciones_info[
            estaciones_info["Estacion"].isin(estaciones_con_datos)
        ]

        for _, row in est_info_filtrada.iterrows():
            est_nombre = row["Estacion"]
            lat, lon = row["Latitud"], row["Longitud"]
            is_selected = est_nombre == estacion_sel
            color_marker = "#ef4444" if is_selected else "#2563eb"
            radius = 9 if is_selected else 6

            folium.CircleMarker(
                location=[lat, lon],
                radius=radius,
                color=color_marker,
                fill=True,
                fill_color=color_marker,
                fill_opacity=0.85,
                weight=2 if is_selected else 1,
                popup=est_nombre,
                tooltip=f"<b>{est_nombre}</b> {'(Seleccionada)' if is_selected else ''}",
            ).add_to(m)

        st_folium(m, height=480, use_container_width=True, returned_objects=[])

    with col_grafico:
        st.markdown(f"##### 📈 Serie Temporal: {variable_sel}")
        if df_estacion.empty or serie_var.empty:
            st.info("No hay datos suficientes para graficar esta serie.")
        else:
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=df_estacion["Fecha"],
                    y=df_estacion[variable_sel],
                    mode="lines+markers",
                    name=variable_sel,
                    line=dict(color="#2563eb", width=2),
                    marker=dict(size=4, color="#1d4ed8"),
                    fill="tozeroy",
                    fillcolor="rgba(37, 99, 235, 0.08)",
                    hovertemplate=(
                        "<b>Semana:</b> %{x|%Y-%m-%d}<br>"
                        + f"<b>{variable_sel}:</b> "
                        + "%{y:.2f} "
                        + f"{UNIDADES.get(variable_sel, '')}<extra></extra>"
                    ),
                )
            )

            fig.update_layout(
                margin=dict(l=10, r=10, t=25, b=10),
                height=480,
                hovermode="x unified",
                xaxis=dict(
                    title="Fecha (Semana Epidemiológica)",
                    showgrid=True,
                    gridcolor="#f1f5f9",
                    rangeslider=dict(visible=True, thickness=0.06),
                ),
                yaxis=dict(
                    title=f"{variable_sel} ({UNIDADES.get(variable_sel, '')})",
                    showgrid=True,
                    gridcolor="#f1f5f9",
                ),
                plot_bgcolor="white",
                paper_bgcolor="white",
            )
            st.plotly_chart(fig, use_container_width=True)
