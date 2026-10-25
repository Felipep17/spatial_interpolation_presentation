"""Acceso cacheado a las fuentes raster procesadas, compartido por todas las páginas.

Dos niveles de caché:
- `cargar` → "bundle" de datos de cada fuente (lectura de NetCDF, estadísticas zonales, series y grilla).
  Clave: rutas + fecha de modificación. No depende del idioma.
- `mapa_html` → HTML del visor diario en un idioma. Se construye a partir del bundle ya cacheado,
  así que cambiar de idioma solo regenera textos: no relee NetCDF ni recalcula estadísticas.
"""

import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from geoclima.datos.barrios import preparar_barrios
from geoclima.datos.raster import (
    calcular_estadisticas_zonales,
    cargar_grilla_nc,
    cargar_recorte_nc,
    estadisticas_zonales,
    listar_fuentes,
    resumen_extent,
)
from geoclima.mapas.visor import generar_mapa_dual, generar_mapa_interactivo, generar_mapa_simple
from geoclima.ui.i18n import idioma, t
from geoclima.ui.tema import RASTER_VARS

# "variables" y "desc" son claves de traducción (geoclima/ui/i18n.py): usar meta_txt()
FUENTES_META = {
    "C3S": {
        "nombre": "Copernicus C3S · AgERA5",
        "corto": "AgERA5",
        "variables": "fuente.C3S.variables",
        "desc": "fuente.C3S.desc",
        "url": "https://cds.climate.copernicus.eu/datasets/sis-agrometeorological-indicators?tab=overview",
    },
    "CHIRPS": {
        "nombre": "CHIRPS v3.0",
        "corto": "CHIRPS",
        "variables": "fuente.CHIRPS.variables",
        "desc": "fuente.CHIRPS.desc",
        "url": "https://www.chc.ucsb.edu/data/chirps3",
    },
    "MSWEP": {
        "nombre": "MSWEP",
        "corto": "MSWEP",
        "variables": "fuente.MSWEP.variables",
        "desc": "fuente.MSWEP.desc",
        "url": "https://www.gloh2o.org/mswep/",
    },
    "GEE": {
        "nombre": "Google Earth Engine · MODIS 1 km",
        "corto": "GEE · MODIS",
        "variables": "fuente.GEE.variables",
        "desc": "fuente.GEE.desc",
        "url": "https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD09GA",
    },
}


def meta_txt(fuente: str, campo: str, lang: str | None = None) -> str:
    """Texto traducido de FUENTES_META ("variables" o "desc")."""
    return t(FUENTES_META[fuente][campo], lang)


# =========================================================================
# Procesamiento cacheado (independiente del idioma)
# =========================================================================
def _bundle(stats, times, lats, lons, pad, gdf, arrays: dict, **extra) -> dict:
    """Datos de una fuente: series zonales, grilla y arreglos raster (para construir el visor sin releer)."""
    return {"stats": stats, "times": times, "res": 2 * pad, "extent": resumen_extent(gdf, lats, lons, pad),
            "lats": np.asarray(lats, float), "lons": np.asarray(lons, float), "pad": float(pad),
            "arrays": {k: np.asarray(v, float) for k, v in arrays.items()}, **extra}


@st.cache_data(show_spinner=False)
def bundle_c3s(_gdf, f_rh: str, f_t: str, bounds: tuple, mtimes: tuple):
    da_rh, lat_c, lon_c, pad = cargar_recorte_nc(Path(f_rh), bounds)
    da_t, _, _, _ = cargar_recorte_nc(Path(f_t), bounds)
    _, stats, times, lats, lons = calcular_estadisticas_zonales(_gdf, da_rh, da_t, lat_c, lon_c, pad)
    return _bundle(stats, times, lats, lons, pad, _gdf, {"rh": da_rh.values, "t": da_t.values})


@st.cache_data(show_spinner=False)
def bundle_precip(_gdf, f_nc: str, mtime: float):
    da_p, lats, lons, pad = cargar_grilla_nc(Path(f_nc), "precipitation")
    times = pd.to_datetime(da_p.time.values)
    _, stats = estadisticas_zonales(_gdf, {"p": da_p.values}, lats, lons, pad, decimales=2)
    return _bundle(stats, times, lats, lons, pad, _gdf, {"p": da_p.values})


@st.cache_data(show_spinner=False)
def bundle_gee(_gdf, f_ndvi: str, f_ndwi: str, mtimes: tuple):
    da_v, lats, lons, pad = cargar_grilla_nc(Path(f_ndvi), "NDVI")
    da_w, *_ = cargar_grilla_nc(Path(f_ndwi), "NDWI")
    times = pd.to_datetime(da_v.time.values)
    _, stats = estadisticas_zonales(_gdf, {"ndvi": da_v.values, "ndwi": da_w.values}, lats, lons, pad,
                                    decimales=3)
    sin_nubes = np.isfinite(da_v.values).mean(axis=(1, 2)) * 100
    return _bundle(stats, times, lats, lons, pad, _gdf, {"ndvi": da_v.values, "ndwi": da_w.values},
                   forma=(len(lats), len(lons)), sin_nubes=sin_nubes)


# =========================================================================
# Visor diario (HTML) por idioma, construido sobre el bundle cacheado
# =========================================================================
@st.cache_data(show_spinner=False, max_entries=16)
def _mapa_html(_gdf, fuente: str, rutas: tuple, mtimes: tuple, lang: str) -> str:
    b = cargar(fuente, _gdf, {k: Path(v) for k, v in rutas})  # acierto de caché: no relee NetCDF
    gdf_b = preparar_barrios(_gdf).assign(n_pixeles=[s["n_pix"] for s in b["stats"]])
    a, geo = b["arrays"], (b["times"], b["lats"], b["lons"], b["pad"])
    if fuente == "C3S":
        mapa = generar_mapa_interactivo(gdf_b, a["rh"], a["t"], b["stats"], *geo, lang=lang)
    elif fuente in ("CHIRPS", "MSWEP"):
        mapa = generar_mapa_simple(gdf_b, a["p"], "p", FUENTES_META[fuente]["nombre"], t("mapa.precip_diaria", lang),
                                   b["stats"], *geo, lang=lang)
    else:
        capas = [("ndvi", a["ndvi"], RASTER_VARS["ndvi"], "NDVI"), ("ndwi", a["ndwi"], RASTER_VARS["ndwi"], "NDWI")]
        mapa = generar_mapa_dual(gdf_b, capas, "GEE · MODIS 1 km", b["stats"], *geo, lang=lang)
    return mapa.get_root().render()


def mapa_html(fuente: str, gdf, rutas: dict, lang: str | None = None) -> str:
    """HTML del visor diario de una fuente en el idioma activo (o en `lang`)."""
    pares = tuple(sorted((k, str(v)) for k, v in rutas.items()))
    mtimes = tuple(Path(v).stat().st_mtime for _, v in pares)
    return _mapa_html(gdf, fuente.upper(), pares, mtimes, lang or idioma())


# =========================================================================
# Localización de archivos y carga por nombre de fuente
# =========================================================================
def archivos_fuente(fuente: str, lista: list[Path]) -> dict | None:
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
        return bundle_precip(gdf, str(rutas["nc"]), rutas["nc"].stat().st_mtime)
    return bundle_gee(gdf, str(rutas["ndvi"]), str(rutas["ndwi"]),
                      (rutas["ndvi"].stat().st_mtime, rutas["ndwi"].stat().st_mtime))


@st.cache_data(show_spinner=False)
def _fechas_nc(ruta: str, mtime: float) -> tuple:
    import xarray as xr

    with xr.open_dataset(ruta) as ds:
        t = pd.to_datetime(ds.time.values)
    return t.min(), t.max()


def periodos_fuentes(inputs_path: Path) -> dict:
    """Primer y último día de cada fuente raster, leyendo solo la coordenada de tiempo (rápido)."""
    salida = {}
    for nombre, lista in listar_fuentes(inputs_path / "raster").items():
        rutas = archivos_fuente(nombre, lista)
        if rutas:
            ruta = next(iter(rutas.values()))
            salida[nombre.upper()] = _fechas_nc(str(ruta), ruta.stat().st_mtime)
    return salida


def cargar_todas(gdf, inputs_path: Path) -> dict:
    """Bundles de todas las fuentes disponibles, en el orden de presentación."""
    salida = {}
    for nombre, lista in listar_fuentes(inputs_path / "raster").items():
        rutas = archivos_fuente(nombre, lista)
        if rutas:
            salida[nombre.upper()] = cargar(nombre, gdf, rutas)
    return salida


# =========================================================================
# Utilidades de series
# =========================================================================
def serie_barrio(stats, k: int, clave: str) -> np.ndarray:
    return np.array([np.nan if v is None else v for v in stats[k][clave]], dtype=float)


def matriz(stats, clave: str) -> np.ndarray:
    """Series zonales como matriz barrios × días (NaN donde no hay dato)."""
    return np.array([[np.nan if v is None else v for v in s[clave]] for s in stats], dtype=float)


def serie_area(stats, clave: str) -> np.ndarray:
    """Promedio diario entre barrios de las series zonales."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        return np.nanmean(matriz(stats, clave), axis=0)


# =========================================================================
# Indicadores del periodo por barrio (comunes a Panorama, Fuentes y Perfil)
# =========================================================================
@dataclass(frozen=True)
class Indicador:
    fuente: str
    clave: str
    modo: str  # "media" | "suma" del periodo
    texto: str  # clave de traducción de la etiqueta

    @property
    def etiqueta(self) -> str:
        return t(self.texto)

    @property
    def id(self) -> str:
        return f"{self.fuente}:{self.clave}"

    @property
    def spec(self):
        return RASTER_VARS[self.clave]

    @property
    def nombre(self) -> str:
        return f"{self.etiqueta} · {FUENTES_META[self.fuente]['corto']}"

    def fmt(self, v) -> str:
        if v is None or not np.isfinite(v):
            return "—"
        if self.modo == "suma":
            return f"{v:,.1f} {self.spec.unidad}"
        return self.spec.fmt(round(float(v), max(self.spec.decimales, 1)))


INDICADORES = [
    Indicador("C3S", "rh", "media", "var.hr"),
    Indicador("C3S", "t", "media", "var.tmax"),
    Indicador("CHIRPS", "p", "suma", "ind.lluvia_acumulada"),
    Indicador("MSWEP", "p", "suma", "ind.lluvia_acumulada"),
    Indicador("GEE", "ndvi", "media", "var.ndvi"),
    Indicador("GEE", "ndwi", "media", "var.ndwi"),
]


def agregar(v: np.ndarray, modo: str, axis=None):
    """Media o suma ignorando huecos; NaN si no hay ningún dato."""
    v = np.asarray(v, float)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        if modo == "suma":
            return np.where(np.isfinite(v).any(axis=axis), np.nansum(v, axis=axis), np.nan)
        return np.nanmean(v, axis=axis)


def valores_periodo(bundle: dict, ind: Indicador) -> np.ndarray:
    """Valor del periodo de cada barrio (en el orden de la capa de barrios)."""
    return agregar(matriz(bundle["stats"], ind.clave), ind.modo, axis=1)


def indicadores_disponibles(bundles: dict) -> list[Indicador]:
    return [i for i in INDICADORES if i.fuente in bundles]


def periodo_txt(times) -> str:
    return f"{times[0]:%d/%m} – {times[-1]:%d/%m/%Y}"


def resolucion(grados: float) -> str:
    km = grados * 111.32
    return f"{grados:.3f}° · ~{km:.1f} km" if grados < 0.05 else f"{grados:.2f}° · ~{km:.0f} km"
