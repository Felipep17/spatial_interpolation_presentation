from functools import partial
from pathlib import Path

import folium
import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
import streamlit as st
from streamlit_folium import st_folium

from geoclima.datos.barrios import barrio_en_clic, geojson_barrios, preparar_barrios, puestos
from geoclima.datos.estaciones import cargar_y_procesar_estaciones, grilla_1km_estaciones
from geoclima.datos.fuentes import (
    FUENTES_META,
    cargar_todas,
    indicadores_disponibles,
    resolucion,
    serie_area,
    serie_barrio,
    valores_periodo,
)
from geoclima.mapas.base import control_capas, mapa_base, para_mapa
from geoclima.paginas.estaciones import _resumen_red
from geoclima.ui.componentes import (
    boton_descarga,
    empty_state,
    metric_card,
    pista,
    render_header,
    section_title,
    tabla_resumen,
)
from geoclima.ui.graficos import mostrar, posicion_barrio, serie_vs_ciudad
from geoclima.ui.i18n import t, t_comuna
from geoclima.ui.navegacion import CLAVE_BARRIO
from geoclima.ui.tema import COLORS, SERIE_COLORES

UTM = "EPSG:32618"
CLAVE_COMPARAR = "comparar"


@st.cache_data(show_spinner=False)
def _vecinos(_gdf, n: int) -> list[list[int]]:
    """Barrios que comparten límite con cada barrio (tolerancia de ~1 m por digitalización)."""
    geoms = _gdf.geometry.values
    i, j = shapely.STRtree(geoms).query(shapely.buffer(geoms, 1e-5), predicate="intersects")
    vec = [[] for _ in range(n)]
    for a, b in zip(i, j, strict=True):
        if a != b:
            vec[a].append(int(b))
    return vec


def _al_clic_mapa(barrios):
    """Clic en un barrio del mapa: pasa a ser el barrio activo (callback, antes de dibujar el selector)."""
    nombre = barrio_en_clic(barrios, st.session_state.get("mapa_barrio"))
    if nombre and nombre != st.session_state.get(CLAVE_BARRIO):
        st.session_state[CLAVE_BARRIO] = nombre


def _al_elegir_vecino(clave: str):
    nombre = st.session_state.get(clave)
    if nombre:
        st.session_state[CLAVE_BARRIO] = nombre


def render(gdf, inputs_path: Path):
    barrios = preparar_barrios(gdf)
    nombres = sorted(barrios["nombre_barrio"])

    render_header(
        title=t("bar.titulo"),
        subtitle=t("bar.subtitulo"),
        eyebrow=t("bar.eyebrow"),
        badges=[(t("gen.barrios"), "gray", f"{len(nombres):,}")],
    )

    # Selector sincronizado con la URL (?barrio=…): los enlaces conservan el barrio
    c_sel, c_cmp = st.columns([1.2, 1], vertical_alignment="bottom")
    with c_sel:
        sel = st.selectbox(t("gen.barrio"), nombres, key=CLAVE_BARRIO, bind="query-params",
                           placeholder=t("bar.placeholder"), help=t("bar.selector_ayuda"))
    # El barrio activo no puede estar también en la comparación
    if sel in (st.session_state.get(CLAVE_COMPARAR) or []):
        st.session_state[CLAVE_COMPARAR] = [c for c in st.session_state[CLAVE_COMPARAR] if c != sel]
    with c_cmp:
        comparar = st.multiselect(t("bar.comparar"), [n for n in nombres if n != sel], key=CLAVE_COMPARAR,
                                  bind="query-params", max_selections=2, placeholder=t("bar.comparar_placeholder"),
                                  help=t("bar.comparar_ayuda"))
    k = int(barrios.loc[barrios["nombre_barrio"] == sel, "b_id"].iloc[0])  # posición en las series zonales
    ks = [k] + [int(barrios.loc[barrios["nombre_barrio"] == c, "b_id"].iloc[0]) for c in comparar]
    geom = barrios.geometry.iloc[k]
    comuna = barrios["comuna"].iat[k]

    with st.spinner(t("gen.cargando_fuentes")):
        bundles = cargar_todas(gdf, inputs_path)
    csv = inputs_path / "climaticas_post_calidad.csv"
    df_sem, est_info = cargar_y_procesar_estaciones(csv) if csv.exists() else (None, None)

    # ---------------------------------------------------------------------
    # Geometría, celdas de 1 km, vecinos y estaciones cercanas
    # ---------------------------------------------------------------------
    b_utm = gpd.GeoSeries([geom], crs="EPSG:4326").to_crs(UTM).iloc[0]
    gee = next(iter(sorted((inputs_path / "raster" / "GEE").glob("*ndvi*.nc"))), None)
    est_df = est_info if est_info is not None else pd.DataFrame(columns=["Estacion", "Latitud", "Longitud"])
    celdas, _, celdas_por_barrio = grilla_1km_estaciones(
        gdf, est_df, str(gee) if gee else None, gee.stat().st_mtime if gee else None
    )
    celdas_b = celdas[celdas.intersects(geom)]
    vecinos = sorted(barrios["nombre_barrio"].iat[j] for j in _vecinos(gdf, len(gdf))[k])

    cercanas = pd.DataFrame()
    if est_info is not None and len(est_info):
        pts = gpd.GeoDataFrame(est_info, geometry=gpd.points_from_xy(est_info["Longitud"], est_info["Latitud"]),
                               crs="EPSG:4326").to_crs(UTM)
        dist = pts.distance(b_utm) / 1000
        cercanas = est_info.assign(dist_km=dist.values).nsmallest(5, "dist_km")

    c_mapa, c_ficha = st.columns([1.5, 1], gap="medium")
    with c_mapa:
        m = mapa_base(gdf)
        sel_bounds = gpd.GeoSeries(barrios.geometry.iloc[ks]).total_bounds
        minx, miny, maxx, maxy = sel_bounds
        m.fit_bounds([[miny - 0.006, minx - 0.006], [maxy + 0.006, maxx + 0.006]])
        folium.GeoJson(
            para_mapa(barrios[["nombre_barrio", "comuna", "geometry"]]).assign(comuna=barrios["comuna"].map(t_comuna)),
            name=t("gen.barrios"),
            style_function=lambda f: {"fillColor": COLORS["ink"], "fillOpacity": 0.0, "color": COLORS["ink_2"],
                                      "weight": 0.6, "opacity": 0.5},
            highlight_function=lambda f: {"fillOpacity": 0.08, "weight": 1.6, "color": COLORS["ink"]},
            tooltip=folium.GeoJsonTooltip(fields=["nombre_barrio", "comuna"],
                                          aliases=[t("gen.barrio"), t("gen.comuna")], class_name="gc-tooltip"),
        ).add_to(m)
        if len(celdas_b):
            folium.GeoJson(
                celdas_b[["celda", "geometry"]], name=t("mapa.celdas_1km"), interactive=False,
                style_function=lambda f: {"fillOpacity": 0, "color": COLORS["accent_dark"], "weight": 1,
                                          "opacity": 0.9, "dashArray": "4 3"},
            ).add_to(m)
        for kk, color in reversed(list(zip(ks, SERIE_COLORES, strict=False))):
            folium.GeoJson(
                barrios.iloc[[kk]][["nombre_barrio", "geometry"]], name=barrios["nombre_barrio"].iat[kk],
                interactive=False,
                style_function=lambda f, c=color: {"fillColor": c, "fillOpacity": 0.2, "color": c, "weight": 2.5},
            ).add_to(m)
        for row in cercanas.itertuples():
            folium.CircleMarker(
                [row.Latitud, row.Longitud], radius=7, color=COLORS["surface"], weight=2,
                fill=True, fill_color=COLORS["ink_2"], fill_opacity=0.95,
                tooltip=f"{row.Estacion} · {row.dist_km:.1f} km",
            ).add_to(m)
        control_capas(m)
        st_folium(m, key="mapa_barrio", height=470, use_container_width=True,
                  returned_objects=["last_clicked"], on_change=partial(_al_clic_mapa, barrios))
        st.caption(t("bar.mapa_cap"))

    with c_ficha:
        section_title(t("bar.ficha"))
        filas = [
            (t("gen.comuna"), t_comuna(comuna)),
            (t("bar.area"), f"{b_utm.area / 1e6:,.2f} km²"),
            (t("bar.centro"), f"{geom.centroid.y:.4f}°, {geom.centroid.x:.4f}°"),
            (t("bar.celdas_gee"), f"{int(celdas_por_barrio[k])}"),
        ]
        for f, b in bundles.items():
            if f != "GEE":
                filas.append((t("bar.pixeles_fuente", f=FUENTES_META[f]["corto"],
                                r=resolucion(b["res"]).split(" · ")[1]), f"{b['stats'][k]['n_pix']}"))
        if len(cercanas):
            r0 = cercanas.iloc[0]
            filas.append((t("bar.estacion_cercana"), f"{r0.Estacion} · {r0.dist_km:.1f} km"))
        tabla_resumen(filas)
        if vecinos:
            st.pills(t("bar.vecinos", n=len(vecinos)), vecinos, key=f"vecinos_{k}", wrap=True,
                     on_change=_al_elegir_vecino, args=(f"vecinos_{k}",), help=t("bar.vecinos_ayuda"))

    # ---------------------------------------------------------------------
    # Indicadores frente al promedio de Cali
    # ---------------------------------------------------------------------
    disponibles = indicadores_disponibles(bundles)
    if not disponibles:
        empty_state(t("gen.sin_fuentes_raster"), t("bar.sin_fuentes_cuerpo"))
        return
    section_title(t("bar.indicadores"), t("bar.indicadores_cap"))
    valores = {ind.id: valores_periodo(bundles[ind.fuente], ind) for ind in disponibles}
    col_cali, col_dif = t("bar.col_promedio"), t("bar.col_diferencia")
    resumen, por_barrio_geo = [], {t("gen.barrio"): sel, t("gen.comuna"): t_comuna(comuna)}
    for fila in range(0, len(disponibles), 2):
        cols = st.columns(2)
        for col, ind in zip(cols, disponibles[fila:fila + 2], strict=False):
            spec, vals = ind.spec, valores[ind.id]
            val_b, val_c = float(vals[k]), float(np.nanmean(vals))
            dif = val_b - val_c
            n_val = int(np.isfinite(vals).sum())
            puesto = int(puestos(vals)[k])
            dec = 3 if spec.unidad == "" else 1
            delta = f"{dif:+.{dec}f} {spec.unidad}".strip() if np.isfinite(dif) else None
            fila_res = {t("bar.col_fuente"): FUENTES_META[ind.fuente]["corto"],
                        t("bar.col_indicador"): f"{ind.etiqueta} ({t(f'modo.{ind.modo}')})",
                        t("bar.col_unidad"): spec.unidad, sel: val_b, col_cali: val_c, col_dif: dif,
                        t("bar.col_puesto"): puesto or None, t("bar.col_de"): n_val}
            for c, kk in zip(comparar, ks[1:], strict=True):
                fila_res[c] = float(vals[kk])
            resumen.append(fila_res)
            por_barrio_geo[ind.nombre] = round(val_b, 4) if np.isfinite(val_b) else None
            serie = serie_barrio(bundles[ind.fuente]["stats"], k, ind.clave)
            tiempos = bundles[ind.fuente]["times"]
            with col:
                metric_card(
                    ind.nombre, ind.fmt(val_b),
                    delta=delta,
                    delta_description=t("bar.vs_cali_puesto", p=puesto, n=n_val) if puesto else t("gen.vs_cali"),
                    delta_color="off", neutral_delta=True,
                    chart=[round(float(v), 3) for v in serie if np.isfinite(v)] or None,
                    chart_type="bar" if spec.forma == "barra" else "line",
                    help=t(f"bar.ayuda_{ind.modo}", periodo=f"{tiempos[0]:%d/%m} – {tiempos[-1]:%d/%m/%Y}"),
                )

    # ---------------------------------------------------------------------
    # Posición frente a todos los barrios
    # ---------------------------------------------------------------------
    section_title(t("bar.posicion"), t("bar.posicion_cap"))
    leyenda = " · ".join(
        f'<span style="color:{c};font-weight:600">●</span> {n}' for n, c in zip([sel, *comparar], SERIE_COLORES,
                                                                                 strict=False)
    )
    st.html(f'<div class="gc-legend-inline">{leyenda}</div>')
    mostrar(posicion_barrio([
        {"titulo": ind.nombre, "valores": valores[ind.id], "media": float(np.nanmean(valores[ind.id])),
         "fmt": ind.fmt,
         "marcas": [(barrios["nombre_barrio"].iat[kk], float(valores[ind.id][kk]), c)
                    for kk, c in zip(ks, SERIE_COLORES, strict=False)]}
        for ind in disponibles
    ]), key="perfil_posicion")

    tabla = pd.DataFrame(resumen)
    with st.expander(t("bar.tabla")):
        st.dataframe(
            tabla, hide_index=True,
            column_config={c: st.column_config.NumberColumn(format="%.3f") for c in [sel, col_cali, col_dif, *comparar]},
        )
    slug = sel.lower().replace(" ", "_")
    boton_descarga(tabla, f"perfil_{slug}", key="dl_perfil",
                   geojson=geojson_barrios(barrios, pd.DataFrame([por_barrio_geo]), t("gen.barrio")))

    # ---------------------------------------------------------------------
    # Series diarias del barrio (y comparados) frente a la ciudad
    # ---------------------------------------------------------------------
    section_title(t("gen.series_diarias"), t("bar.series_cap_cmp") if comparar else t("bar.series_cap"))
    for fila in range(0, len(disponibles), 2):
        cols = st.columns(2)
        for col, ind in zip(cols, disponibles[fila:fila + 2], strict=False):
            stats = bundles[ind.fuente]["stats"]
            with col:
                st.markdown(f"**{ind.nombre}**")
                fig = serie_vs_ciudad(
                    bundles[ind.fuente]["times"],
                    {barrios["nombre_barrio"].iat[kk]: serie_barrio(stats, kk, ind.clave) for kk in ks},
                    serie_area(stats, ind.clave), ind.spec,
                )
                mostrar(fig, key=f"perfil_{ind.fuente}_{ind.clave}")
    if "GEE" in bundles:
        st.caption(t("bar.nota_gee"))

    # ---------------------------------------------------------------------
    # Estaciones cercanas
    # ---------------------------------------------------------------------
    if len(cercanas) and df_sem is not None:
        section_title(t("bar.cercanas"), t("bar.cercanas_cap"))
        red = _resumen_red(df_sem, "Precipitacion").set_index("Estación")
        tabla = cercanas[["Estacion", "dist_km"]].join(red[["Media", "Completitud", "Último registro"]], on="Estacion")
        col = {"Estacion": t("gen.estacion"), "dist_km": t("bar.col_distancia"), "Media": t("bar.col_precip_media"),
               "Completitud": t("est.kpi_completitud"), "Último registro": t("est.col_ultimo")}
        st.dataframe(
            tabla.rename(columns=col), hide_index=True,
            column_config={
                col["dist_km"]: st.column_config.NumberColumn(format="%.1f"),
                col["Media"]: st.column_config.NumberColumn(format="%.1f"),
                col["Completitud"]: st.column_config.ProgressColumn(format="%.0f %%", min_value=0, max_value=100),
                col["Último registro"]: st.column_config.DateColumn(format="DD/MM/YYYY"),
            },
        )
    elif not len(cercanas):
        pista(t("bar.sin_estaciones"), icono="info")
