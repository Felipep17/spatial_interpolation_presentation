"""Elementos compartidos por los scripts de descarga y por la app.

La grilla de 1 km se define aquí una sola vez: los NetCDF de GEE se descargan
sobre ella y la vista de estaciones la dibuja.
"""

from datetime import date
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr

RAIZ = Path(__file__).resolve().parent.parent
INPUTS = RAIZ / "inputs"
RASTER = INPUTS / "raster"

# 0.009° ≈ 1.002 km en latitud y ≈ 1.000 km en longitud a la latitud de Cali (3.4° N)
RES_1KM = 0.009
# Margen alrededor de la extensión de Cali (grados)
MARGEN = 0.02


def bounds_cali() -> tuple[float, float, float, float]:
    capa = next((INPUTS / "shapefiles").glob("*.parquet"), None)
    if capa is None:
        raise FileNotFoundError("No se encontró la capa de barrios en inputs/shapefiles/*.parquet")
    gdf = gpd.read_parquet(capa).to_crs(epsg=4326)
    return tuple(float(v) for v in gdf.total_bounds)


def grilla_1km(bounds=None):
    """Centros (lats descendentes, lons ascendentes) de la grilla fija de 1 km que cubre Cali."""
    minx, miny, maxx, maxy = bounds or bounds_cali()
    x0 = np.floor((minx - MARGEN) / RES_1KM) * RES_1KM
    x1 = np.ceil((maxx + MARGEN) / RES_1KM) * RES_1KM
    y0 = np.floor((miny - MARGEN) / RES_1KM) * RES_1KM
    y1 = np.ceil((maxy + MARGEN) / RES_1KM) * RES_1KM
    nx = int(round((x1 - x0) / RES_1KM))
    ny = int(round((y1 - y0) / RES_1KM))
    lons = np.round(x0 + RES_1KM * (np.arange(nx) + 0.5), 6)
    lats = np.round(y1 - RES_1KM * (np.arange(ny) + 0.5), 6)
    return lats, lons, (round(float(x0), 6), round(float(y1), 6))


def periodo_chirps() -> tuple[date, date]:
    """Primer y último día del NetCDF de CHIRPS: periodo de referencia de las descargas."""
    archivo = next((RASTER / "CHIRPS").glob("*.nc"), None)
    if archivo is None:
        raise FileNotFoundError("No hay NetCDF de CHIRPS en inputs/raster/CHIRPS para tomar el periodo")
    with xr.open_dataset(archivo) as ds:
        t = pd.to_datetime(ds.time.values)
    return t.min().date(), t.max().date()


def guardar_netcdf(ds: xr.Dataset, destino: Path):
    """Escritura atómica: nunca deja un NetCDF a medias en inputs/."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".nc.tmp")
    try:
        ds.to_netcdf(tmp, engine="netcdf4",
                     encoding={v: {"zlib": True, "complevel": 4} for v in ds.data_vars})
        tmp.replace(destino)
    finally:
        tmp.unlink(missing_ok=True)
