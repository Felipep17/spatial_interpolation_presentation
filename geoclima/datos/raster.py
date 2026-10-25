"""Productos raster: lectura de NetCDF, estadísticas zonales por barrio y celdas de cada grilla sobre Cali."""

import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
import xarray as xr

from geoclima.datos.barrios import preparar_barrios

# Orden de presentación de las fuentes; las no listadas van al final en orden alfabético
ORDEN_FUENTES = ["C3S", "CHIRPS", "MSWEP", "GEE"]


def listar_fuentes(raster_dir: Path):
    fuentes = {}
    if raster_dir.exists():
        carpetas = [p for p in raster_dir.iterdir() if p.is_dir()]
        orden = {n: i for i, n in enumerate(ORDEN_FUENTES)}
        for d in sorted(carpetas, key=lambda c: (orden.get(c.name.upper(), len(orden)), c.name)):
            fuentes[d.name] = sorted(list(d.glob("*.nc")) + list(d.glob("*.tif")))
    return fuentes


def cargar_recorte_nc(nc_path: Path, bounds, res=0.1):
    minx, miny, maxx, maxy = bounds
    pad = res / 2
    with xr.open_dataset(nc_path) as ds:
        vars_validas = [
            v for v in ds.data_vars if len(ds[v].dims) >= 2 and v not in ["spatial_ref", "crs"]
        ]
        var_name = vars_validas[0] if vars_validas else list(ds.data_vars)[0]
        da = ds[var_name]
        lat_col = next(
            c for c in list(da.coords) + list(da.dims) if c.lower() in ["latitude", "lat", "y"]
        )
        lon_col = next(
            c for c in list(da.coords) + list(da.dims) if c.lower() in ["longitude", "lon", "x"]
        )
        lon_0_360 = float(ds[lon_col].min()) >= 0 and minx < 0
        minx_s, maxx_s = (minx + 360, maxx + 360) if lon_0_360 else (minx, maxx)
        lat_slice = (
            slice(maxy + pad, miny - pad)
            if da[lat_col].values[0] > da[lat_col].values[-1]
            else slice(miny - pad, maxy + pad)
        )
        lon_slice = slice(minx_s - pad, maxx_s + pad)
        da = da.sel({lat_col: lat_slice, lon_col: lon_slice}).load()
    if lon_0_360:
        da = da.assign_coords({lon_col: da[lon_col] - 360})
    if (
        "temp" in var_name.lower()
        or "t2m" in var_name.lower()
        or "mx2t" in var_name.lower()
    ) and float(da.mean().values) > 100:
        da = da - 273.15
    return da, lat_col, lon_col, pad


def cargar_grilla_nc(nc_path: Path, var: str | None = None):
    """NetCDF ya recortado (CHIRPS, MSWEP, GEE): variable, centros de píxel y medio paso."""
    with xr.open_dataset(nc_path) as ds:
        if var is None:
            var = next(v for v in ds.data_vars if len(ds[v].dims) >= 2 and v not in ("spatial_ref", "crs"))
        da_p = ds[var].load()
    lat_col = "lat" if "lat" in da_p.coords else "latitude"
    lon_col = "lon" if "lon" in da_p.coords else "longitude"
    # float64 y redondeo: algunos productos (MSWEP) guardan coordenadas float32 con ruido
    lats = np.round(da_p[lat_col].values.astype(float), 6)
    lons = np.round(da_p[lon_col].values.astype(float), 6)
    pad = (
        abs(float(lats[1] - lats[0])) / 2.0
        if len(lats) > 1
        else abs(float(lons[1] - lons[0])) / 2.0
    )
    return da_p, lats, lons, pad


def _pixeles_por_barrio(gdf_b, lats, lons, pad):
    """Índices planos (i * n_lon + j) de los píxeles que intersectan cada barrio (STRtree)."""
    ii, jj = np.divmod(np.arange(len(lats) * len(lons)), len(lons))
    cajas = shapely.box(lons[jj] - pad, lats[ii] - pad, lons[jj] + pad, lats[ii] + pad)
    barrio_idx, pixel_idx = shapely.STRtree(cajas).query(
        gdf_b.geometry.values, predicate="intersects"
    )
    orden = np.argsort(barrio_idx, kind="stable")
    cortes = np.cumsum(np.bincount(barrio_idx, minlength=len(gdf_b)))[:-1]
    return np.split(pixel_idx[orden], cortes)


def _series_zonales(arr: np.ndarray, por_barrio, decimales: int):
    plano = arr.reshape(arr.shape[0], -1)
    series = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)  # barrios sin píxeles válidos
        for idx in por_barrio:
            medias = np.nanmean(plano[:, idx], axis=1) if len(idx) else np.full(arr.shape[0], np.nan)
            series.append([None if np.isnan(v) else round(float(v), decimales) for v in medias])
    return series


def estadisticas_zonales(gdf: gpd.GeoDataFrame, arrays: dict, lats, lons, pad, decimales: int = 1):
    """Devuelve (gdf preparado con n_pixeles, lista de dicts por barrio con una serie por variable)."""
    gdf_b = preparar_barrios(gdf)
    por_barrio = _pixeles_por_barrio(gdf_b, lats, lons, pad)
    series = {k: _series_zonales(np.asarray(a, dtype=float), por_barrio, decimales) for k, a in arrays.items()}
    stats = [
        {"id": int(k), "nom": nom, "n_pix": int(len(por_barrio[k])), **{v: series[v][k] for v in arrays}}
        for k, nom in enumerate(gdf_b["nombre_barrio"])
    ]
    gdf_b["n_pixeles"] = [s["n_pix"] for s in stats]
    return gdf_b, stats


def calcular_estadisticas_zonales(gdf, da_rh, da_t, lat_col, lon_col, pad):
    lats = da_rh[lat_col].values
    lons = da_rh[lon_col].values
    time_vals = pd.to_datetime(da_rh.time.values)
    gdf_b, stats = estadisticas_zonales(gdf, {"rh": da_rh.values, "t": da_t.values}, lats, lons, pad)
    return gdf_b, stats, time_vals, lats, lons


def celdas_sobre_cali(barrios, lats, lons, pad):
    """Celdas de la grilla que tocan algún barrio, con % de su área dentro de Cali.

    Devuelve (celdas que tocan Cali, total de celdas del extent, celdas que toca cada barrio).
    """
    lats, lons = np.asarray(lats, float), np.asarray(lons, float)
    ii, jj = np.divmod(np.arange(len(lats) * len(lons)), len(lons))
    celdas = gpd.GeoDataFrame(
        {"fila": ii, "col": jj, "lat": lats[ii], "lon": lons[jj]},
        geometry=shapely.box(lons[jj] - pad, lats[ii] - pad, lons[jj] + pad, lats[ii] + pad),
        crs="EPSG:4326",
    )
    total = len(celdas)
    cali = barrios.geometry.union_all()
    celdas = celdas[celdas.intersects(cali)].copy()

    utm = "EPSG:32618"  # UTM 18N: áreas en m² para Cali
    celdas_utm = celdas.to_crs(utm)
    cali_utm = gpd.GeoSeries([cali], crs="EPSG:4326").to_crs(utm).iloc[0]
    celdas["pct_cali"] = (celdas_utm.intersection(cali_utm).area / celdas_utm.area * 100).round(0)

    b_idx, c_idx = shapely.STRtree(celdas.geometry.values).query(barrios.geometry.values, predicate="intersects")
    celdas["n_barrios"] = np.bincount(c_idx, minlength=len(celdas))
    # Mismo criterio "intersecta" de las estadísticas zonales
    celdas_por_barrio = np.bincount(b_idx, minlength=len(barrios))
    return celdas, total, celdas_por_barrio


def resumen_extent(gdf, lats, lons, pad) -> dict:
    """Conteo de celdas de una fuente raster: en el extent del archivo y sobre Cali."""
    celdas, total, por_barrio = celdas_sobre_cali(preparar_barrios(gdf), lats, lons, pad)
    return {
        "forma": (len(lats), len(lons)),
        "res": 2 * pad,
        "total": total,
        "tocan_cali": len(celdas),
        "dentro_50": int((celdas["pct_cali"] >= 50).sum()),
        "por_barrio_mediana": float(np.median(por_barrio)),
        "por_barrio_max": int(por_barrio.max()),
        "barrios_una_celda": int((por_barrio == 1).sum()),
        "n_barrios": len(por_barrio),
    }
