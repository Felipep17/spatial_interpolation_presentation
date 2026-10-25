"""Estaciones in situ: agregación por semana epidemiológica y grilla de 1 km con las estaciones que contiene."""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import streamlit as st

from geoclima.datos.barrios import preparar_barrios
from geoclima.datos.grilla import RES_1KM, grilla_1km
from geoclima.datos.raster import cargar_grilla_nc, celdas_sobre_cali
from geoclima.ui.i18n import t


def cargar_y_procesar_estaciones(csv_path: Path):
    """Registros semanales por estación e información de cada estación (con aviso traducido mientras procesa)."""
    with st.spinner(t("gen.procesando_estaciones")):
        return _estaciones_semanales(csv_path)


@st.cache_data(show_spinner=False)
def _estaciones_semanales(csv_path: Path):
    cols = [
        "Estacion",
        "Fecha",
        "Precipitacion",
        "Tmin",
        "Tmax",
        "Humedad relativa",
        "Velocidad del viento",
        "Radiación solar",
        "Latitud",
        "Longitud",
    ]
    df = pd.read_csv(csv_path, usecols=cols)
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    df = df.sort_values(["Estacion", "Fecha"])

    reglas = {
        "Precipitacion": "sum",
        "Tmin": "mean",
        "Tmax": "mean",
        "Humedad relativa": "mean",
        "Velocidad del viento": "mean",
        "Radiación solar": "mean",
        "Latitud": "first",
        "Longitud": "first",
    }

    # Semana epidemiológica INS Colombia / CDC (MMWR): domingo a sábado.
    # "W-SAT" agrupa (sábado anterior, sábado] = domingo..sábado y etiqueta con el sábado de cierre.
    df_semanal = (
        df.groupby(["Estacion", pd.Grouper(key="Fecha", freq="W-SAT")])
        .agg(reglas)
        .reset_index()
    )
    # Año y número de semana epidemiológica: la semana 1 es la primera con >= 4 días en enero,
    # es decir, la que contiene el primer miércoles del año.
    miercoles = df_semanal["Fecha"] - pd.Timedelta(days=3)
    df_semanal["Año epi"] = miercoles.dt.year
    df_semanal["Semana epi"] = (miercoles.dt.day_of_year - 1) // 7 + 1

    # Primero se descartan filas sin coordenadas: algunas estaciones (Compartir) empiezan sin ellas
    estaciones_info = (
        df[["Estacion", "Latitud", "Longitud"]].dropna().drop_duplicates("Estacion")
    )

    return df_semanal, estaciones_info


@st.cache_data(show_spinner=False)
def grilla_1km_estaciones(_gdf, estaciones: pd.DataFrame, gee_nc: str | None, mtime: float | None):
    """Celdas de 1 km que tocan Cali con sus estaciones, barrios y fracción de área dentro de la ciudad,
    más el número de celdas que toca cada barrio (en el orden de la capa de barrios).

    Si existe el NetCDF de GEE se usan sus coordenadas; si no, la grilla teórica idéntica.
    """
    if gee_nc:
        _, lats, lons, pad = cargar_grilla_nc(Path(gee_nc))
        origen = "GEE"
    else:
        lats, lons, _ = grilla_1km(tuple(_gdf.total_bounds))
        pad, origen = RES_1KM / 2, "teórica"

    barrios = preparar_barrios(_gdf)
    celdas, total, celdas_por_barrio = celdas_sobre_cali(barrios, lats, lons, pad)

    pts = gpd.GeoDataFrame(estaciones, geometry=gpd.points_from_xy(estaciones["Longitud"], estaciones["Latitud"]),
                           crs="EPSG:4326")
    unidas = gpd.sjoin(pts, celdas[["geometry"]], predicate="within", how="inner")
    por_celda = unidas.groupby("index_right")["Estacion"].agg(list)
    celdas["n_est"] = celdas.index.map(por_celda.str.len()).fillna(0).astype(int)
    celdas["estaciones"] = celdas.index.map(lambda k: ", ".join(por_celda.get(k, [])) or "—")
    celdas["celda"] = celdas.apply(lambda r: f"F{r.fila + 1:02d} · C{r.col + 1:02d}", axis=1)
    celdas["centro"] = celdas.apply(lambda r: f"{r.lat:.4f}°, {r.lon:.4f}°", axis=1)

    resumen = {
        "origen": origen,
        "forma": (len(lats), len(lons)),
        "res": 2 * pad,
        "total": total,
        "tocan_cali": len(celdas),
        "dentro_50": int((celdas["pct_cali"] >= 50).sum()),
        "con_estacion": int((celdas["n_est"] > 0).sum()),
        "max_est": int(celdas["n_est"].max()) if len(celdas) else 0,
        "fuera": int(len(pts) - len(unidas)),
        "celdas_por_barrio_mediana": float(np.median(celdas_por_barrio)),
        "celdas_por_barrio_max": int(celdas_por_barrio.max()),
    }
    cols = ["celda", "centro", "n_est", "estaciones", "n_barrios", "pct_cali", "geometry"]
    return celdas[cols].reset_index(drop=True), resumen, celdas_por_barrio


@st.cache_data(show_spinner=False)
def periodo_estaciones(csv: str, mtime: float) -> tuple:
    """Primer y último día de los registros diarios (solo lee la columna de fechas)."""
    fechas = pd.to_datetime(pd.read_csv(csv, usecols=["Fecha"])["Fecha"])
    return fechas.min(), fechas.max()
