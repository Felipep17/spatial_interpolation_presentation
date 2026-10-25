"""Rutas del proyecto: una sola definición para la app, las pruebas y los scripts de descarga."""

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
INPUTS = RAIZ / "inputs"
RASTER = INPUTS / "raster"
SHAPEFILES = INPUTS / "shapefiles"
CSV_ESTACIONES = INPUTS / "climaticas_post_calidad.csv"
ASSETS = RAIZ / "assets"
