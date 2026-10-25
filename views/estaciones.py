import warnings
from pathlib import Path

import folium
import geopandas as gpd
import numpy as np
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from components.charts import calendario_semanal, climatologia_semanal, mostrar, serie_temporal
from components.i18n import conservar, t, t_comuna
from components.nav import enlace_barrio
from components.theme import COLORS, VARIABLES, colormap, escala_robusta, leyenda_html
from components.ui import boton_descarga, empty_state, metric_card, render_header, section_title, tabla_resumen
from utils import (
    capa_barrios,
    capa_comunas,
    cargar_y_procesar_estaciones,
    control_capas,
    grilla_1km_estaciones,
    mapa_base,
    preparar_barrios,
)

MAPA_ALTO = 640
_PENDIENTE = "_estacion_pendiente"
_CLAVE_ESTACION = "estacion"  # también es el parámetro de la URL


@st.cache_data(show_spinner=False)
def _resumen_red(df_semanal: pd.DataFrame, variable: str) -> pd.DataFrame:
    """Estadísticos por estación para la variable activa.

    Las columnas tienen nombres internos fijos (no dependen del idioma): se traducen al mostrarlas.
    """
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
    if estacion and estacion != st.session_state.get(_CLAVE_ESTACION):
        st.session_state[_PENDIENTE] = estacion
        st.rerun()


def _grilla(gdf, estaciones_info, inputs_path: Path):
    gee = next(iter(sorted((inputs_path / "raster" / "GEE").glob("*ndvi*.nc"))), None)
    return grilla_1km_estaciones(
        gdf, estaciones_info, str(gee) if gee else None, gee.stat().st_mtime if gee else None
    )


@st.cache_data(show_spinner=False)
def _ubicar_estaciones(_gdf, estaciones: pd.DataFrame) -> pd.DataFrame:
    """Barrio y comuna donde cae cada estación; las de fuera del perímetro urbano quedan como rurales."""
    barrios = preparar_barrios(_gdf)
    pts = gpd.GeoDataFrame(estaciones[["Estacion"]], crs="EPSG:4326",
                           geometry=gpd.points_from_xy(estaciones["Longitud"], estaciones["Latitud"]))
    unidas = gpd.sjoin(pts, barrios[["nombre_barrio", "comuna", "geometry"]], predicate="within", how="left")
    unidas = unidas.drop_duplicates("Estacion")
    return pd.DataFrame({
        "Estación": unidas["Estacion"].to_numpy(),
        "Barrio": unidas["nombre_barrio"].fillna("—").to_numpy(),
        "Comuna": unidas["comuna"].fillna("Fuera del perímetro urbano").to_numpy(),
    })


def _ciclo_anual(df_est: pd.DataFrame, variable: str):
    """Tabla año epidemiológico × semana epidemiológica (1–53) de la variable."""
    return (df_est.pivot_table(index="Año epi", columns="Semana epi", values=variable, aggfunc="mean")
            .reindex(columns=range(1, 54)).sort_index())


def _bloque_estacional(df_est: pd.DataFrame, variable: str, spec, estacion: str):
    """Ciclo anual (banda p10–p90 y mediana) con el año elegido, y calendario año × semana."""
    tabla = _ciclo_anual(df_est, variable)
    con_dato = tabla.notna().sum(axis=1)
    anios = [int(a) for a in tabla.index[con_dato > 0]]
    if len(anios) < 2:
        return
    section_title(t("est.estacional"), t("est.estacional_cap", v=spec.label, e=estacion))
    completos = [int(a) for a in tabla.index[con_dato >= 26]]
    defecto = completos[-1] if completos else anios[-1]
    c_g, c_c = st.columns([1.1, 1], gap="medium")
    with c_g:
        anio = st.selectbox(t("est.anio"), anios[::-1], index=anios[::-1].index(defecto), key="anio_epi",
                            help=t("est.anio_ayuda"))
        valores = tabla.to_numpy(dtype=float)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            p10, p50, p90 = (np.nanpercentile(valores, q, axis=0) for q in (10, 50, 90))
        semanas = list(tabla.columns)
        mostrar(climatologia_semanal(semanas, p10, p50, p90, tabla.loc[anio].to_numpy(dtype=float), spec,
                                     etiqueta_actual=t("est.anio_n", a=anio), height=360), key="ciclo_anual")
    with c_c:
        st.markdown(f"**{t('est.calendario')}**")
        mostrar(calendario_semanal(tabla.to_numpy(dtype=float), anios=list(tabla.index), semanas=semanas,
                                   spec=spec, height=max(300, 70 + 24 * len(tabla))), key="calendario")
        st.caption(t("est.calendario_cap"))


def _capa_grilla(celdas) -> folium.FeatureGroup:
    """Celdas transparentes (solo contorno); el detalle aparece al pasar el cursor."""
    fg = folium.FeatureGroup(name=t("mapa.grilla"))
    folium.GeoJson(
        celdas,
        style_function=lambda f: {
            "fillColor": COLORS["accent"],
            "fillOpacity": 0.0,
            "color": COLORS["accent_dark"],
            "weight": 0.8,
            "opacity": 0.8,
        },
        highlight_function=lambda f: {"weight": 2.2, "fillOpacity": 0.12},
        tooltip=folium.GeoJsonTooltip(
            fields=["celda", "centro", "n_est", "estaciones", "n_barrios", "pct_cali"],
            aliases=[t("mapa.celda"), t("mapa.centro"), t("gen.estaciones"), t("mapa.nombres"),
                     t("mapa.barrios_toca"), t("mapa.pct_cali")],
            sticky=True,
        ),
    ).add_to(fg)
    return fg


def _resumen_grilla(celdas, r: dict):
    ny, nx = r["forma"]
    filas = [
        (t("est.origen"), t("est.origen_gee") if r["origen"] == "GEE" else t("est.origen_teorica")),
        (t("est.tamano_celda"), f"{r['res']:.3f}° · ~{r['res'] * 111.32:.2f} km"),
        (t("est.celdas_extension"), f"{r['total']:,} ({ny} × {nx})"),
        (t("sat.celdas_tocan"), f"{r['tocan_cali']:,}"),
        (t("sat.celdas_50"), f"{r['dentro_50']:,}"),
        (t("est.celdas_estacion"), t("gen.a_de_b_pct", a=f"{r['con_estacion']:,}", b=f"{r['tocan_cali']:,}",
                                     pct=f"{100 * r['con_estacion'] / max(r['tocan_cali'], 1):.0f}")),
        (t("est.max_est_celda"), f"{r['max_est']}"),
        (t("pan.celdas_barrio"), t("gen.mediana_max", m=f"{r['celdas_por_barrio_mediana']:.0f}",
                                   x=r["celdas_por_barrio_max"])),
    ]
    if r["fuera"]:
        filas.append((t("est.rurales"), f"{r['fuera']}"))
    tabla_resumen(filas)
    # Encabezados traducidos para la tabla y para la descarga
    nombres = {"celda": t("mapa.celda"), "centro": t("mapa.centro"), "n_est": t("gen.estaciones"),
               "estaciones": t("mapa.nombres"), "n_barrios": t("gen.barrios"), "pct_cali": t("est.pct_en_cali")}
    vista = celdas.drop(columns="geometry").rename(columns=nombres)
    con_est = vista[vista[nombres["n_est"]] > 0].sort_values(nombres["n_est"], ascending=False)
    with st.expander(t("est.celdas_con_est", n=len(con_est))):
        st.dataframe(con_est, hide_index=True,
                     column_config={nombres["pct_cali"]: st.column_config.NumberColumn(format="%d %%")})
        boton_descarga(vista, "grilla_1km_celdas_cali", key="dl_grilla")


def render(gdf, inputs_path: Path):
    csv_file = inputs_path / "climaticas_post_calidad.csv"
    if not csv_file.exists():
        render_header(t("est.titulo"), t("est.subtitulo_corto"), eyebrow=t("est.eyebrow"))
        empty_state(t("est.sin_datos"), t("est.sin_csv", f=csv_file.name))
        return

    df_semanal, estaciones_info = cargar_y_procesar_estaciones(csv_file)

    render_header(
        title=t("est.titulo"),
        subtitle=t("est.subtitulo"),
        eyebrow=t("est.eyebrow"),
        badges=[
            (t("gen.estaciones"), "green", str(estaciones_info["Estacion"].nunique())),
            (t("gen.periodo"), "gray", f"{df_semanal['Fecha'].min():%Y} – {df_semanal['Fecha'].max():%Y}"),
            (t("est.agregacion"), "blue", t("est.semanal")),
        ],
    )

    # ---------------------------------------------------------------------
    # Filtros
    # ---------------------------------------------------------------------
    f1, f2 = st.columns([3, 2], vertical_alignment="bottom")
    conservar("variable")
    with f1:
        variable_sel = st.segmented_control(
            t("est.variable"),
            list(VARIABLES),
            default="Precipitacion",
            required=True,
            key="variable",
            bind="query-params",
            format_func=lambda k: VARIABLES[k].corta,
        )
    spec = VARIABLES[variable_sel]

    conteos = df_semanal.groupby("Estacion")[variable_sel].count()
    con_datos = sorted(set(conteos[conteos > 0].index) & set(estaciones_info["Estacion"]))
    if not con_datos:
        empty_state(t("est.sin_registros"), t("est.sin_registros_cuerpo", v=spec.label.lower()))
        return

    pendiente = st.session_state.pop(_PENDIENTE, None)
    if pendiente in con_datos:
        st.session_state[_CLAVE_ESTACION] = pendiente
    if st.session_state.get(_CLAVE_ESTACION) not in con_datos:
        st.session_state[_CLAVE_ESTACION] = con_datos[0]

    with f2:
        estacion_sel = st.selectbox(
            t("gen.estacion"),
            con_datos,
            key=_CLAVE_ESTACION,
            bind="query-params",
            help=t("est.estacion_ayuda"),
        )

    df_est = df_semanal[df_semanal["Estacion"] == estacion_sel].sort_values("Fecha")
    serie = df_est.set_index("Fecha")[variable_sel].dropna()
    resumen = _resumen_red(df_semanal, variable_sel)
    ubicacion = _ubicar_estaciones(gdf, estaciones_info)

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
            t("est.kpi_ultima"), spec.fmt(serie.iloc[-1]),
            delta=f"{float(serie.iloc[-1] - media):+.{spec.decimales}f} {spec.unidad}".strip(),
            delta_description=t("est.vs_media_hist"), delta_color="off", neutral_delta=True,
            chart=serie.iloc[-26:].round(2).tolist(), chart_type=tipo_chart,
            help=t("est.kpi_ultima_ayuda", fecha=f"{serie.index[-1]:%d/%m/%Y}"),
        )
    with k2:
        anual = serie.groupby(serie.index.year).mean()
        metric_card(
            t("est.kpi_media"), spec.fmt(media), delta=t("gen.n_semanas", n=f"{len(serie):,}"), neutral_delta=True,
            chart=anual.round(2).tolist(), chart_type="line",
            help=t("est.kpi_media_ayuda", agg=spec.agregacion.capitalize()),
        )
    with k3:
        metric_card(
            t("est.kpi_max"), spec.fmt(serie.max()), delta=t("est.semana_del", fecha=f"{serie.idxmax():%d/%m/%Y}"),
            neutral_delta=True,
        )
    with k4:
        cobertura_anual = serie.groupby(serie.index.year).size() / 52 * 100
        metric_card(
            t("est.kpi_completitud"), f"{completitud:.0f} %",
            delta=t("est.kpi_completitud_delta", a=f"{len(serie):,}", b=f"{semanas:,}"),
            neutral_delta=True, chart=cobertura_anual.clip(upper=100).round(0).tolist(), chart_type="bar",
            help=t("est.kpi_completitud_ayuda"),
        )

    # ---------------------------------------------------------------------
    # Mapa + serie temporal
    # ---------------------------------------------------------------------
    c_mapa, c_serie = st.columns([1.2, 1.3], gap="medium")

    with c_mapa:
        t1, t2 = st.columns([3, 2], vertical_alignment="bottom")
        with t1:
            section_title(t("est.red"), t("est.red_cap", v=spec.label.lower()))
        with t2:
            ver_grilla = st.toggle(t("est.grilla_toggle"), key="grilla_1km", help=t("est.grilla_ayuda"))
        medias = resumen.set_index("Estación")["Media"]
        cm = colormap(spec.cmap, *escala_robusta(medias.values))

        m = mapa_base(gdf)
        # El tooltip de cada barrio indica cuántas celdas de 1 km (GEE) toca
        celdas, info_grilla, celdas_por_barrio = _grilla(gdf, estaciones_info, inputs_path)
        barrios = preparar_barrios(gdf).assign(n_pixeles=celdas_por_barrio)
        capa_barrios(barrios, alias_pixeles=t("mapa.celdas_gee")).add_to(m)
        capa_comunas(barrios).add_to(m)

        fg = folium.FeatureGroup(name=t("gen.estaciones"))
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
                tooltip=nombre,  # el clic se identifica por este texto: solo el nombre de la estación
            ).add_to(fg)

        grupos = [fg]
        if ver_grilla:
            grupos = [_capa_grilla(celdas), fg]  # la grilla debajo de los marcadores

        control_capas(m)
        salida = st_folium(
            m,
            key="mapa_estaciones",
            height=MAPA_ALTO,
            use_container_width=True,
            feature_group_to_add=grupos,
            returned_objects=["last_object_clicked_tooltip"],
        )
        st.html(leyenda_html(cm, spec, t("est.leyenda", v=spec.label)))
        if ver_grilla:
            _resumen_grilla(celdas, info_grilla)

        clic = (salida or {}).get("last_object_clicked_tooltip")
        if clic in con_datos and clic != st.session_state.get("_ultimo_clic"):
            st.session_state["_ultimo_clic"] = clic
            _seleccionar(clic)

    with c_serie:
        lugar = ubicacion.set_index("Estación").loc[estacion_sel] if estacion_sel in set(ubicacion["Estación"]) else None
        donde = (f" · {lugar['Barrio']}, {t_comuna(lugar['Comuna'])}" if lugar is not None and lugar["Barrio"] != "—"
                 else f" · {t('est.fuera_perimetro')}")
        section_title(f"{spec.label} · {estacion_sel}", f"{spec.agregacion.capitalize()} ({spec.unidad}){donde}.")
        if serie.empty:
            empty_state(t("est.sin_suficientes"), t("est.sin_suficientes_cuerpo"))
        else:
            fig = serie_temporal(
                df_est["Fecha"], df_est[variable_sel], spec,
                height=MAPA_ALTO - 10, referencia=media, ref_label=t("est.kpi_media"), selector_rango=True,
            )
            mostrar(fig, key="serie_estacion")

    if not serie.empty:
        _bloque_estacional(df_est, variable_sel, spec, estacion_sel)

    # ---------------------------------------------------------------------
    # Tabla de la red (nombres internos → encabezados traducidos)
    # ---------------------------------------------------------------------
    section_title(t("est.resumen"), t("est.resumen_cap"))
    tabla = resumen.merge(ubicacion, on="Estación", how="left").sort_values("Estación").reset_index(drop=True)
    tabla["Comuna"] = tabla["Comuna"].map(t_comuna)
    col = {
        "Estación": t("gen.estacion"), "Barrio": t("gen.barrio"), "Comuna": t("gen.comuna"),
        "Media": t("est.col_media", u=spec.unidad), "Máximo": t("est.col_maximo", u=spec.unidad),
        "Semanas con dato": t("est.col_semanas"), "Completitud": t("est.kpi_completitud"),
        "Último registro": t("est.col_ultimo"), "Últimas 52 semanas": t("est.col_52"),
    }
    tabla = tabla[list(col)].rename(columns=col)
    evento = st.dataframe(
        tabla,
        hide_index=True,
        height=420,
        on_select="rerun",
        selection_mode="single-row",
        key="tabla_red",
        column_config={
            col["Estación"]: st.column_config.TextColumn(pinned=True),
            col["Barrio"]: st.column_config.TextColumn(help=t("est.barrio_ayuda")),
            col["Media"]: st.column_config.NumberColumn(format="%.1f"),
            col["Máximo"]: st.column_config.NumberColumn(format="%.1f"),
            col["Semanas con dato"]: st.column_config.NumberColumn(format="%d"),
            col["Completitud"]: st.column_config.ProgressColumn(format="%.0f %%", min_value=0, max_value=100),
            col["Último registro"]: st.column_config.DateColumn(format="DD/MM/YYYY"),
            col["Últimas 52 semanas"]: (
                st.column_config.BarChartColumn(y_min=0) if spec.forma == "barra"
                else st.column_config.LineChartColumn()
            ),
        },
    )
    boton_descarga(tabla, f"red_estaciones_{variable_sel.lower().replace(' ', '_')}", key="dl_red")
    filas = evento.selection.rows if evento else []
    if filas and tabla.iloc[filas[0]][col["Barrio"]] != "—":
        enlace_barrio(tabla.iloc[filas[0]][col["Barrio"]])
    if filas:
        elegido = tabla.iloc[filas[0]][col["Estación"]]
        if elegido != st.session_state.get("_ultima_fila"):
            st.session_state["_ultima_fila"] = elegido
            _seleccionar(elegido)
