from pathlib import Path
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from utils import cargar_y_procesar_estaciones

def render(gdf, inputs_path: Path):
    st.title("🌡️ Estaciones Meteorológicas")
    st.markdown("Visualización de registros in-situ agregados por **semana epidemiológica**.")
    
    csv_file = inputs_path / "climaticas_post_calidad.csv"
    if not csv_file.exists():
        st.error(f"❌ No se encontró el archivo de estaciones en: {csv_file}")
        return

    # Cargar datos cacheados
    df_semanal, estaciones_info = cargar_y_procesar_estaciones(csv_file)

    # 1. SELECCIÓN DE VARIABLE PRIMERO
    variables_disponibles = ['Precipitacion', 'Tmin', 'Tmax', 'Humedad relativa', 'Velocidad del viento', 'Radiación solar']
    variable_sel = st.selectbox("📌 Seleccionar Variable a Analizar:", variables_disponibles)

    # Filtrar estaciones que tienen al menos un dato válido (no NaN) para la variable seleccionada
    estaciones_con_datos = []
    for est in estaciones_info['Estacion'].unique():
        subset = df_semanal[df_semanal['Estacion'] == est]
        if not subset.empty and subset[variable_sel].notna().sum() > 0:
            estaciones_con_datos.append(est)

    if not estaciones_con_datos:
        st.warning(f"No hay estaciones con datos válidos para la variable '{variable_sel}'.")
        return

    # Gestionar selección de estación en session_state
    if 'estacion_sel' not in st.session_state or st.session_state.estacion_sel not in estaciones_con_datos:
        st.session_state.estacion_sel = estaciones_con_datos[0]

    col_mapa, col_grafico = st.columns([1.1, 0.9])

    with col_grafico:
        st.subheader("📈 Serie de Tiempo Semanal")
        # 2. SELECCIÓN DE ESTACIÓN (Filtrada por las disponibles para la variable)
        estacion_sel = st.selectbox(
            "📍 Seleccionar Estación:", 
            estaciones_con_datos, 
            index=estaciones_con_datos.index(st.session_state.estacion_sel)
        )
        st.session_state.estacion_sel = estacion_sel
        
        # Filtrar datos para graficar
        df_plot = df_semanal[df_semanal['Estacion'] == estacion_sel].copy().set_index('Fecha')
        
        unidades = {
            'Precipitacion': 'mm (Acumulado Semanal)',
            'Tmin': '°C', 'Tmax': '°C',
            'Humedad relativa': '%',
            'Velocidad del viento': 'm/s',
            'Radiación solar': 'MJ/m²'
        }
        
        st.line_chart(df_plot[[variable_sel]], y=variable_sel, use_container_width=True)
        st.caption(f"Unidad: {unidades.get(variable_sel, '')}")

    with col_mapa:
        st.subheader("🗺️ Mapa de Estaciones Disponibles")
        
        minx, miny, maxx, maxy = gdf.total_bounds
        m = folium.Map(location=[(miny + maxy)/2, (minx + maxx)/2], zoom_start=11, tiles="OpenStreetMap")
        
        folium.GeoJson(
            gdf, 
            name="Límites Cali",
            style_function=lambda x: {"fillColor": "#ffffff", "fillOpacity": 0.05, "color": "#333333", "weight": 1}
        ).add_to(m)

        # Dibujar solo las estaciones que tienen datos para la variable actual
        est_info_filtrada = estaciones_info[estaciones_info['Estacion'].isin(estaciones_con_datos)]
        
        for _, row in est_info_filtrada.iterrows():
            est_nombre = row['Estacion']
            lat, lon = row['Latitud'], row['Longitud']
            
            is_selected = est_nombre == estacion_sel
            color_marker = 'red' if is_selected else 'blue'
            radius = 9 if is_selected else 6

            folium.CircleMarker(
                location=[lat, lon],
                radius=radius,
                color=color_marker,
                fill=True,
                fill_color=color_marker,
                fill_opacity=0.8,
                popup=est_nombre,
                tooltip=f"{est_nombre} {'(Seleccionada)' if is_selected else ''}"
            ).add_to(m)

        # Renderizado rápido del mapa usando st_folium con zoom y centrado estables
        st_folium(m, height=450, use_container_width=True, returned_objects=[])