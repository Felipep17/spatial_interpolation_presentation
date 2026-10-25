"""Capa de barrios: lectura, comunas, barrio bajo un clic, puestos (ranking) y exportación GeoJSON."""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
import streamlit as st


@st.cache_data
def cargar_shapefile(carpeta: Path):
    formatos = ["*.parquet", "*.shp", "*.geojson", "*.gpkg"]
    arch = None
    for fmt in formatos:
        hits = sorted(carpeta.glob(fmt))
        if hits:
            arch = hits[0]
            break
    if not arch:
        raise FileNotFoundError(f"Sin vectores en {carpeta}")
    gdf = gpd.read_parquet(arch) if arch.suffix == ".parquet" else gpd.read_file(arch)
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    return gdf


def comuna_de(codigo) -> str:
    """Comuna a partir del código de barrio de Planeación Municipal (CCBB): 01–22 o 81 (área de expansión)."""
    cc = str(codigo)[:2]
    if cc == "81":
        return "Área de expansión"
    return f"Comuna {int(cc)}" if cc.isdigit() and 1 <= int(cc) <= 22 else "Sin comuna"


def preparar_barrios(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf_b = gdf.copy()
    col_nombre = next((c for c in gdf_b.columns if c.lower() == "nombre"), gdf_b.columns[0])
    gdf_b["b_id"] = np.arange(len(gdf_b))
    gdf_b["nombre_barrio"] = gdf_b[col_nombre].astype(str)
    gdf_b["comuna"] = gdf_b["id_sector"].map(comuna_de) if "id_sector" in gdf_b else "Sin comuna"
    return gdf_b


def barrio_en_clic(gdf_b, valor_mapa) -> str | None:
    """Barrio que contiene el punto clicado en un mapa de st_folium (`last_clicked`), o None.

    Se usa la coordenada y no el elemento SVG: un clic sobre el límite entre dos barrios puede
    caer en el grupo SVG y Leaflet lo reporta como clic en el mapa base, no en el barrio.
    """
    punto = (valor_mapa or {}).get("last_clicked")
    if not punto:
        return None
    dentro = gdf_b.geometry.contains(shapely.Point(punto["lng"], punto["lat"]))
    return gdf_b.loc[dentro, "nombre_barrio"].iat[0] if dentro.any() else None


def orden_comunas(comunas) -> list[str]:
    """Comuna 1 … Comuna 22 en orden numérico y el área de expansión al final."""
    def clave(c):
        partes = c.split()
        return (0, int(partes[-1])) if partes[-1].isdigit() else (1, c)
    return sorted(set(comunas), key=clave)


def puestos(valores) -> np.ndarray:
    """Puesto de cada barrio de mayor a menor (1 = valor más alto); 0 si no tiene dato."""
    v = pd.Series(np.asarray(valores, float))
    return v.rank(ascending=False, method="min").fillna(0).astype(int).to_numpy()


def geojson_barrios(gdf_b, tabla: pd.DataFrame, columna_nombre: str) -> bytes:
    """GeoJSON (EPSG:4326) con la geometría de cada barrio y las columnas numéricas/texto de la tabla.

    columna_nombre: columna de la tabla con el nombre del barrio (su encabezado depende del idioma).
    """
    cols = [c for c in tabla.columns
            if not tabla[c].map(lambda v: isinstance(v, (list, tuple, np.ndarray))).any()]
    geo = gdf_b[["nombre_barrio", "geometry"]].merge(
        tabla[cols], left_on="nombre_barrio", right_on=columna_nombre, how="right"
    )
    geo = gpd.GeoDataFrame(geo.drop(columns="nombre_barrio"), geometry="geometry", crs="EPSG:4326")
    geo["geometry"] = geo.geometry.set_precision(1e-6)  # ~0.1 m: archivos más livianos sin perder forma
    return geo.to_json(drop_id=True, na="null").encode("utf-8")
