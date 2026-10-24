"""Acceso cacheado a las fuentes raster procesadas, compartido por todas las páginas.

Cada fuente se procesa una sola vez (clave de caché: rutas + fecha de modificación)
y devuelve un "bundle" con el mapa HTML, las series zonales por barrio y la grilla.
"""

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from components.theme import RASTER_VARS
from utils import (
    calcular_estadisticas_zonales,
    cargar_grilla_nc,
    cargar_recorte_nc,
    estadisticas_zonales,
    generar_mapa_dual,
    generar_mapa_interactivo,
    generar_mapa_simple,
    listar_fuentes,
    resumen_extent,
)

FUENTES_META = {
    "C3S": {
        "nombre": "Copernicus C3S · AgERA5",
        "corto": "AgERA5",
        "variables": "Humedad relativa · Temperatura máxima",
        "desc": "Indicadores agrometeorológicos diarios derivados del reanálisis ERA5 (0.1°).",
        "url": "https://cds.climate.copernicus.eu/datasets/sis-agrometeorological-indicators?tab=overview",
    },
    "CHIRPS": {
        "nombre": "CHIRPS v3.0",
        "corto": "CHIRPS",
        "variables": "Precipitación",
        "desc": "Precipitación diaria cuasi-global combinando satélite y estaciones (0.05°).",
        "url": "https://www.chc.ucsb.edu/data/chirps3",
    },
    "MSWEP": {
        "nombre": "MSWEP",
        "corto": "MSWEP",
        "variables": "Precipitación",
        "desc": "Precipitación diaria multi-fuente ponderada: satélite, reanálisis y pluviómetros (0.1°).",
        "url": "https://www.gloh2o.org/mswep/",
    },
    "GEE": {
        "nombre": "Google Earth Engine · MODIS 1 km",
        "corto": "GEE · MODIS",
        "variables": "NDVI · NDWI",
        "desc": "NDVI y NDWI diarios de MOD09GA promediados a una grilla de 0.009° (~1 km), sin nubes.",
        "url": "https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD09GA",
    },
}


# =========================================================================
# Procesamiento cacheado
# =========================================================================
@st.cache_data(show_spinner=False)
def bundle_c3s(_gdf, f_rh: str, f_t: str, bounds: tuple, mtimes: tuple):
    da_rh, lat_c, lon_c, pad = cargar_recorte_nc(Path(f_rh), bounds)
    da_t, _, _, _ = cargar_recorte_nc(Path(f_t), bounds)
    gdf_b, stats, times, lats, lons = calcular_estadisticas_zonales(_gdf, da_rh, da_t, lat_c, lon_c, pad)
    mapa = generar_mapa_interactivo(gdf_b, da_rh, da_t, stats, times, lats, lons, pad)
    return {"html": mapa.get_root().render(), "stats": stats, "times": times, "res": 2 * pad,
            "extent": resumen_extent(_gdf, lats, lons, pad)}


@st.cache_data(show_spinner=False)
def bundle_precip(_gdf, f_nc: str, mtime: float, titulo: str):
    da_p, lats, lons, pad = cargar_grilla_nc(Path(f_nc), "precipitation")
    times = pd.to_datetime(da_p.time.values)
    gdf_b, stats = estadisticas_zonales(_gdf, {"p": da_p.values}, lats, lons, pad, decimales=2)
    mapa = generar_mapa_simple(gdf_b, da_p.values, "p", titulo, "Precipitación diaria",
                               stats, times, lats, lons, pad)
    return {"html": mapa.get_root().render(), "stats": stats, "times": times, "res": 2 * pad,
            "extent": resumen_extent(_gdf, lats, lons, pad)}


@st.cache_data(show_spinner=False)
def bundle_gee(_gdf, f_ndvi: str, f_ndwi: str, mtimes: tuple):
    da_v, lats, lons, pad = cargar_grilla_nc(Path(f_ndvi), "NDVI")
    da_w, *_ = cargar_grilla_nc(Path(f_ndwi), "NDWI")
    times = pd.to_datetime(da_v.time.values)
    gdf_b, stats = estadisticas_zonales(_gdf, {"ndvi": da_v.values, "ndwi": da_w.values}, lats, lons, pad,
                                        decimales=3)
    capas = [("ndvi", da_v.values, RASTER_VARS["ndvi"], "NDVI"), ("ndwi", da_w.values, RASTER_VARS["ndwi"], "NDWI")]
    mapa = generar_mapa_dual(gdf_b, capas, "GEE · MODIS 1 km", stats, times, lats, lons, pad)
    sin_nubes = np.isfinite(da_v.values).mean(axis=(1, 2)) * 100
    return {"html": mapa.get_root().render(), "stats": stats, "times": times, "res": 2 * pad,
            "forma": (len(lats), len(lons)), "sin_nubes": sin_nubes,
            "extent": resumen_extent(_gdf, lats, lons, pad)}


# =========================================================================
# Localización de archivos y carga por nombre de fuente
# =========================================================================
def archivos(fuente: str, lista: list[Path]) -> dict | None:
    """Archivos que necesita cada fuente, o None si faltan."""
    f = fuente.upper()
    if f == "C3S":
        rh = next((a for a in lista if "relative_humidity" in a.name), None)
        t = next((a for a in lista if "temperature_maximu" in a.name or "t2m" in a.name), None)
        return {"rh": rh, "t": t} if rh and t else None
    if f in ("CHIRPS", "MSWEP"):
        nc = next((a for a in lista if f.lower() in a.name.lower() and a.suffix == ".nc"), None)
        return {"nc": nc} if nc else None
    if f == "GEE":
        v = next((a for a in lista if "ndvi" in a.name.lower() and a.suffix == ".nc"), None)
        w = next((a for a in lista if "ndwi" in a.name.lower() and a.suffix == ".nc"), None)
        return {"ndvi": v, "ndwi": w} if v and w else None
    return None


def cargar(fuente: str, gdf, rutas: dict) -> dict:
    f = fuente.upper()
    if f == "C3S":
        return bundle_c3s(gdf, str(rutas["rh"]), str(rutas["t"]), tuple(gdf.total_bounds),
                          (rutas["rh"].stat().st_mtime, rutas["t"].stat().st_mtime))
    if f in ("CHIRPS", "MSWEP"):
        return bundle_precip(gdf, str(rutas["nc"]), rutas["nc"].stat().st_mtime, FUENTES_META[f]["nombre"])
    return bundle_gee(gdf, str(rutas["ndvi"]), str(rutas["ndwi"]),
                      (rutas["ndvi"].stat().st_mtime, rutas["ndwi"].stat().st_mtime))


def cargar_todas(gdf, inputs_path: Path) -> dict:
    """Bundles de todas las fuentes disponibles, en el orden de presentación."""
    salida = {}
    for nombre, lista in listar_fuentes(inputs_path / "raster").items():
        rutas = archivos(nombre, lista)
        if rutas:
            salida[nombre.upper()] = cargar(nombre, gdf, rutas)
    return salida


# =========================================================================
# Utilidades de series
# =========================================================================
def serie_barrio(stats, k: int, clave: str) -> np.ndarray:
    return np.array([np.nan if v is None else v for v in stats[k][clave]], dtype=float)


def serie_area(stats, clave: str) -> np.ndarray:
    """Promedio diario entre barrios de las series zonales."""
    mat = np.array([[np.nan if v is None else v for v in s[clave]] for s in stats], dtype=float)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        return np.nanmean(mat, axis=0)


def resolucion(grados: float) -> str:
    km = grados * 111.32
    return f"{grados:.3f}° · ~{km:.1f} km" if grados < 0.05 else f"{grados:.2f}° · ~{km:.0f} km"
