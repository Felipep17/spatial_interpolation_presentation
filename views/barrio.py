import warnings
from pathlib import Path

import folium
import geopandas as gpd
import numpy as np
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from components.charts import mostrar, serie_vs_ciudad
from components.theme import COLORS, RASTER_VARS
from components.ui import boton_descarga, empty_state, metric_card, render_header, section_title, tabla_resumen
from datos import FUENTES_META, cargar_todas, resolucion, serie_area, serie_barrio
from utils import cargar_y_procesar_estaciones, grilla_1km_estaciones, mapa_base, preparar_barrios
from views.estaciones import _resumen_red

UTM = "EPSG:32618"

# (fuente, clave, agregación del periodo, etiqueta corta)
INDICADORES = [
    ("C3S", "rh", "media", "Humedad relativa"),
    ("C3S", "t", "media", "Temperatura máxima"),
    ("CHIRPS", "p", "suma", "Lluvia acumulada"),
    ("MSWEP", "p", "suma", "Lluvia acumulada"),
    ("GEE", "ndvi", "media", "NDVI"),
    ("GEE", "ndwi", "media", "NDWI"),
]


def _agregar(v: np.ndarray, modo: str) -> float:
    if not np.isfinite(v).any():
        return np.nan
    return float(np.nansum(v)) if modo == "suma" else float(np.nanmean(v))


def _fmt(valor: float, spec, modo: str) -> str:
    if not np.isfinite(valor):
        return "—"
    if modo == "suma":
        return f"{valor:,.1f} {spec.unidad}"
    return spec.fmt(round(valor, max(spec.decimales, 1)))


def render(gdf, inputs_path: Path):
    barrios = preparar_barrios(gdf)
    nombres = sorted(barrios["nombre_barrio"])

    # Selección sincronizada con la URL (?barrio=…) para compartir enlaces
    if "barrio_sel" not in st.session_state:
        qp = st.query_params.get("barrio")
        st.session_state.barrio_sel = qp if qp in nombres else nombres[0]

    render_header(
        title="Perfil de barrio",
        subtitle="Todas las fuentes para un barrio: valores frente al promedio de Cali, series diarias, "
                 "celdas que lo cubren y estaciones cercanas.",
        eyebrow="Módulo 03 · Barrio",
        badges=[("Barrios", "gray", f"{len(nombres):,}")],
    )
    sel = st.selectbox("Barrio", nombres, key="barrio_sel", placeholder="Escriba para buscar…",
                       help="Escriba parte del nombre para filtrar. El enlace de la página conserva el barrio.")
    st.query_params["barrio"] = sel
    k = int(barrios.loc[barrios["nombre_barrio"] == sel, "b_id"].iloc[0])  # posición en las series zonales
    geom = barrios.geometry.iloc[k]

    with st.spinner("Cargando fuentes…"):
        bundles = cargar_todas(gdf, inputs_path)
    csv = inputs_path / "climaticas_post_calidad.csv"
    df_sem, est_info = cargar_y_procesar_estaciones(csv) if csv.exists() else (None, None)

    # ---------------------------------------------------------------------
    # Geometría, celdas de 1 km y estaciones cercanas
    # ---------------------------------------------------------------------
    b_utm = gpd.GeoSeries([geom], crs="EPSG:4326").to_crs(UTM).iloc[0]
    gee = next(iter(sorted((inputs_path / "raster" / "GEE").glob("*ndvi*.nc"))), None)
    est_df = est_info if est_info is not None else pd.DataFrame(columns=["Estacion", "Latitud", "Longitud"])
    celdas, _, celdas_por_barrio = grilla_1km_estaciones(
        gdf, est_df, str(gee) if gee else None, gee.stat().st_mtime if gee else None
    )
    celdas_b = celdas[celdas.intersects(geom)]

    cercanas = pd.DataFrame()
    if est_info is not None and len(est_info):
        pts = gpd.GeoDataFrame(est_info, geometry=gpd.points_from_xy(est_info["Longitud"], est_info["Latitud"]),
                               crs="EPSG:4326").to_crs(UTM)
        dist = pts.distance(b_utm) / 1000
        cercanas = est_info.assign(dist_km=dist.values).nsmallest(5, "dist_km")

    c_mapa, c_ficha = st.columns([1.5, 1], gap="medium")
    with c_mapa:
        m = mapa_base(gdf)
        minx, miny, maxx, maxy = geom.bounds
        m.fit_bounds([[miny - 0.006, minx - 0.006], [maxy + 0.006, maxx + 0.006]])
        folium.GeoJson(
            barrios[["nombre_barrio", "geometry"]], name="Barrios",
            style_function=lambda f: {"fillOpacity": 0, "color": COLORS["ink_2"], "weight": 0.6, "opacity": 0.5},
            tooltip=folium.GeoJsonTooltip(fields=["nombre_barrio"], aliases=["Barrio"]),
        ).add_to(m)
        if len(celdas_b):
            folium.GeoJson(
                celdas_b[["celda", "pct_cali", "geometry"]], name="Celdas 1 km",
                style_function=lambda f: {"fillOpacity": 0, "color": COLORS["accent_dark"], "weight": 1, "opacity": 0.9,
                                          "dashArray": "4 3"},
                tooltip=folium.GeoJsonTooltip(fields=["celda", "pct_cali"], aliases=["Celda 1 km", "% dentro de Cali"]),
            ).add_to(m)
        folium.GeoJson(
            barrios.iloc[[k]][["nombre_barrio", "geometry"]], name=sel,
            style_function=lambda f: {"fillColor": COLORS["accent"], "fillOpacity": 0.18,
                                      "color": COLORS["accent_dark"], "weight": 2.5},
        ).add_to(m)
        for row in cercanas.itertuples():
            folium.CircleMarker(
                [row.Latitud, row.Longitud], radius=7, color=COLORS["surface"], weight=2,
                fill=True, fill_color=COLORS["highlight"], fill_opacity=0.95,
                tooltip=f"{row.Estacion} · {row.dist_km:.1f} km",
            ).add_to(m)
        st_folium(m, key="mapa_barrio", height=460, use_container_width=True, returned_objects=[])
        st.caption("Barrio resaltado, celdas de 1 km (línea discontinua) y las 5 estaciones más cercanas (naranja).")

    with c_ficha:
        section_title("Ficha del barrio")
        filas = [
            ("Área", f"{b_utm.area / 1e6:,.2f} km²"),
            ("Centro", f"{geom.centroid.y:.4f}°, {geom.centroid.x:.4f}°"),
            ("Celdas GEE de 1 km", f"{int(celdas_por_barrio[k])}"),
        ]
        for f, b in bundles.items():
            if f != "GEE":
                filas.append((f"Píxeles {FUENTES_META[f]['corto']} ({resolucion(b['res']).split(' · ')[1]})",
                              f"{b['stats'][k]['n_pix']}"))
        if len(cercanas):
            r0 = cercanas.iloc[0]
            filas.append(("Estación más cercana", f"{r0.Estacion} · {r0.dist_km:.1f} km"))
        tabla_resumen(filas)

    # ---------------------------------------------------------------------
    # Indicadores frente al promedio de Cali
    # ---------------------------------------------------------------------
    disponibles = [i for i in INDICADORES if i[0] in bundles]
    if not disponibles:
        empty_state("Sin fuentes raster", "No hay fuentes procesadas para construir el perfil.")
        return
    section_title("Indicadores del periodo", "Valor del barrio y diferencia frente al promedio de todos los barrios.")
    resumen = []
    for fila in range(0, len(disponibles), 2):
        cols = st.columns(2)
        for col, (f, clave, modo, etiqueta) in zip(cols, disponibles[fila:fila + 2], strict=False):
            spec = RASTER_VARS[clave]
            vb, vc = serie_barrio(bundles[f]["stats"], k, clave), serie_area(bundles[f]["stats"], clave)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=RuntimeWarning)
                val_b, val_c = _agregar(vb, modo), _agregar(vc, modo)
            dif = val_b - val_c
            dec = 3 if spec.unidad == "" else 1
            delta = f"{dif:+.{dec}f} {spec.unidad}".strip() if np.isfinite(dif) else None
            resumen.append({"Fuente": FUENTES_META[f]["corto"], "Indicador": f"{etiqueta} ({modo})",
                            "Barrio": val_b, "Promedio Cali": val_c, "Diferencia": dif, "Unidad": spec.unidad})
            with col:
                metric_card(
                    f"{etiqueta} · {FUENTES_META[f]['corto']}", _fmt(val_b, spec, modo),
                    delta=delta, delta_description="vs. promedio de Cali", delta_color="off", neutral_delta=True,
                    chart=[round(float(v), 3) for v in vb if np.isfinite(v)] or None,
                    chart_type="bar" if spec.forma == "barra" else "line",
                    help=f"{'Suma' if modo == 'suma' else 'Media'} del periodo "
                         f"{bundles[f]['times'][0]:%d/%m} – {bundles[f]['times'][-1]:%d/%m/%Y}.",
                )
    boton_descarga(pd.DataFrame(resumen), f"perfil_{sel.lower().replace(' ', '_')}", key="dl_perfil")

    # ---------------------------------------------------------------------
    # Series diarias del barrio frente a la ciudad
    # ---------------------------------------------------------------------
    section_title("Series diarias", "Barrio (azul) frente al promedio de todos los barrios (gris).")
    for fila in range(0, len(disponibles), 2):
        cols = st.columns(2)
        for col, (f, clave, _, etiqueta) in zip(cols, disponibles[fila:fila + 2], strict=False):
            spec = RASTER_VARS[clave]
            with col:
                st.markdown(f"**{etiqueta}** · {FUENTES_META[f]['corto']}")
                fig = serie_vs_ciudad(bundles[f]["times"], serie_barrio(bundles[f]["stats"], k, clave),
                                      serie_area(bundles[f]["stats"], clave), spec, sel)
                mostrar(fig, key=f"perfil_{f}_{clave}")

    # ---------------------------------------------------------------------
    # Estaciones cercanas
    # ---------------------------------------------------------------------
    if len(cercanas) and df_sem is not None:
        section_title("Estaciones cercanas", "Distancia al borde del barrio y registro semanal de precipitación.")
        red = _resumen_red(df_sem, "Precipitacion").set_index("Estación")
        tabla = cercanas[["Estacion", "dist_km"]].rename(columns={"Estacion": "Estación", "dist_km": "Distancia (km)"})
        tabla = tabla.join(red[["Media", "Completitud", "Último registro"]], on="Estación")
        st.dataframe(
            tabla, hide_index=True,
            column_config={
                "Distancia (km)": st.column_config.NumberColumn(format="%.1f"),
                "Media": st.column_config.NumberColumn("Precipitación media (mm/sem)", format="%.1f"),
                "Completitud": st.column_config.ProgressColumn(format="%.0f %%", min_value=0, max_value=100),
                "Último registro": st.column_config.DateColumn(format="DD/MM/YYYY"),
            },
        )
