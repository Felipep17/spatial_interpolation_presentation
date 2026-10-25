"""Elementos compartidos por los scripts de descarga.

La grilla de 1 km se define en geoclima/datos/grilla.py (la usa también la app) y las rutas en geoclima/rutas.py.
"""

from datetime import date
from pathlib import Path

import geopandas as gpd
import pandas as pd
import xarray as xr

from geoclima.datos.grilla import MARGEN, RES_1KM  # noqa: F401 (reexportados para gee.py y mswep.py)
from geoclima.datos.grilla import grilla_1km as _grilla_1km
from geoclima.rutas import INPUTS, RASTER  # noqa: F401 (RASTER se reexporta para gee.py y mswep.py)


def bounds_cali() -> tuple[float, float, float, float]:
    capa = next((INPUTS / "shapefiles").glob("*.parquet"), None)
    if capa is None:
        raise FileNotFoundError("No se encontró la capa de barrios en inputs/shapefiles/*.parquet")
    gdf = gpd.read_parquet(capa).to_crs(epsg=4326)
    return tuple(float(v) for v in gdf.total_bounds)


def grilla_1km(bounds=None):
    """Grilla de 1 km sobre `bounds` o, si no se indican, sobre la extensión de la capa de barrios."""
    return _grilla_1km(bounds or bounds_cali())


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
