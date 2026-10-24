"""NDVI y NDWI diarios de MODIS (MOD09GA) a 1 km desde Google Earth Engine.

Uso:
    uv run --group descarga python -m descargas.gee --project <ID_PROYECTO_GCP>

- Periodo: el mismo del NetCDF de CHIRPS (se puede forzar con --inicio/--fin).
- Índices (mismas fórmulas que climate_data_downloader):
    NDVI = (NIR − RED) / (NIR + RED)   = (b02 − b01) / (b02 + b01)
    NDWI = (NIR − SWIR) / (NIR + SWIR) = (b02 − b06) / (b02 + b06)   (Gao, 1996)
- Resolución: los píxeles de 500 m se promedian sobre la grilla fija de 0.009° (~1 km)
  definida en descargas/comun.py.
- Nubes: por defecto se enmascaran con la banda QA state_1km (nube, sombra y nube interna).
  --sin-mascara-nubes reproduce el comportamiento original del repositorio (sin máscara).

Salida: inputs/raster/GEE/{ndvi,ndwi}_modis_1km_<AAAA_MM>_cali.nc  (time, lat, lon)
"""

import argparse
import os
from datetime import date, timedelta

import ee
import numpy as np
import pandas as pd
import xarray as xr

from descargas.comun import RASTER, RES_1KM, grilla_1km, guardar_netcdf, periodo_chirps

COLECCION = "MODIS/061/MOD09GA"
NODATA = -9999.0


def inicializar(project: str):
    try:
        ee.Initialize(project=project)
    except Exception:
        print("Autenticación de Earth Engine requerida: se abrirá el navegador…")
        ee.Authenticate()
        ee.Initialize(project=project)
    print(f"Earth Engine inicializado (proyecto: {project})")


def _mascara_cielo_despejado(img):
    qa = img.select("state_1km")
    despejado = qa.bitwiseAnd(0b11).eq(0)          # bits 0-1: estado de nubes = despejado
    sin_sombra = qa.bitwiseAnd(1 << 2).eq(0)        # bit 2: sombra de nube
    sin_nube_interna = qa.bitwiseAnd(1 << 10).eq(0)  # bit 10: bandera interna de nube
    return despejado.And(sin_sombra).And(sin_nube_interna)


def _indices(img, enmascarar_nubes: bool):
    b01, b02, b06 = (img.select(b).toFloat() for b in ("sur_refl_b01", "sur_refl_b02", "sur_refl_b06"))
    valido = b01.gt(-100).And(b02.gt(-100)).And(b06.gt(-100))
    if enmascarar_nubes:
        valido = valido.And(_mascara_cielo_despejado(img))
    ndvi = b02.subtract(b01).divide(b02.add(b01))
    ndwi = b02.subtract(b06).divide(b02.add(b06))
    return ndvi.addBands(ndwi).rename(["NDVI", "NDWI"]).updateMask(valido)


def descargar(project: str, inicio: date, fin: date, enmascarar_nubes: bool = True):
    inicializar(project)
    lats, lons, (x0, y1) = grilla_1km()
    transform = [RES_1KM, 0, x0, 0, -RES_1KM, y1]
    grid = {
        "dimensions": {"width": len(lons), "height": len(lats)},
        "affineTransform": {"scaleX": RES_1KM, "shearX": 0, "translateX": x0,
                            "shearY": 0, "scaleY": -RES_1KM, "translateY": y1},
        "crsCode": "EPSG:4326",
    }
    region = ee.Geometry.Rectangle([x0, y1 - RES_1KM * len(lats), x0 + RES_1KM * len(lons), y1])
    coleccion = ee.ImageCollection(COLECCION).filterBounds(region)

    fechas = pd.date_range(inicio, fin, freq="D")
    datos = {k: np.full((len(fechas), len(lats), len(lons)), np.nan, dtype="float32") for k in ("NDVI", "NDWI")}

    for t, dia in enumerate(fechas):
        del_dia = coleccion.filterDate(dia.strftime("%Y-%m-%d"), (dia + timedelta(days=1)).strftime("%Y-%m-%d"))
        if del_dia.size().getInfo() == 0:
            print(f"{dia:%Y-%m-%d}: sin imagen MODIS")
            continue
        proyeccion = del_dia.first().select("sur_refl_b01").projection()
        img = _indices(del_dia.mosaic().setDefaultProjection(proyeccion), enmascarar_nubes)
        img_1km = (img.reduceResolution(ee.Reducer.mean(), maxPixels=64)
                   .reproject(crs="EPSG:4326", crsTransform=transform)
                   .unmask(NODATA))
        px = ee.data.computePixels({"expression": img_1km, "fileFormat": "NUMPY_NDARRAY", "grid": grid})
        for k in datos:
            arr = np.asarray(px[k], dtype="float32")
            arr[(arr <= NODATA + 1) | (arr < -1) | (arr > 1)] = np.nan
            datos[k][t] = arr
        validos = np.isfinite(datos["NDVI"][t]).mean() * 100
        print(f"{dia:%Y-%m-%d}: {validos:5.1f} % de celdas sin nubes")

    sufijo = f"{inicio:%Y_%m}" if (inicio.year, inicio.month) == (fin.year, fin.month) else f"{inicio:%Y%m%d}_{fin:%Y%m%d}"
    for k, arr in datos.items():
        ds = xr.Dataset(
            {k: (("time", "lat", "lon"), arr)},
            coords={"time": fechas, "lat": lats, "lon": lons},
            attrs={
                "title": f"{k} diario MODIS MOD09GA a 1 km (0.009°) recortado a Cali",
                "source": f"Google Earth Engine · {COLECCION}",
                "formula": "NDVI=(b02-b01)/(b02+b01)" if k == "NDVI" else "NDWI=(b02-b06)/(b02+b06) (Gao)",
                "cloud_mask": "state_1km (nube, sombra, nube interna)" if enmascarar_nubes else "ninguna",
                "aggregation": "media de píxeles de 500 m dentro de cada celda de 0.009°",
                "crs": "EPSG:4326",
            },
        )
        destino = RASTER / "GEE" / f"{k.lower()}_modis_1km_{sufijo}_cali.nc"
        guardar_netcdf(ds, destino)
        print(f"Guardado: {destino.relative_to(RASTER.parent.parent)}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--project", default=os.environ.get("EE_PROJECT"),
                   help="ID del proyecto de Google Cloud registrado en Earth Engine (o variable EE_PROJECT)")
    p.add_argument("--inicio", type=date.fromisoformat, help="AAAA-MM-DD (por defecto: inicio de CHIRPS)")
    p.add_argument("--fin", type=date.fromisoformat, help="AAAA-MM-DD (por defecto: fin de CHIRPS)")
    p.add_argument("--sin-mascara-nubes", action="store_true", help="No enmascarar nubes (como el repositorio original)")
    a = p.parse_args()
    if not a.project:
        p.error("Indique --project o defina la variable de entorno EE_PROJECT")
    ini, fin = periodo_chirps()
    descargar(a.project, a.inicio or ini, a.fin or fin, enmascarar_nubes=not a.sin_mascara_nubes)


if __name__ == "__main__":
    main()
