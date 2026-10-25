"""Pruebas de las funciones de apoyo (sin Streamlit en ejecución)."""

import json

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import shapely

from datos import agregar, rango_fechas
from utils import barrio_en_clic, comuna_de, geojson_barrios, orden_comunas, preparar_barrios, puestos


@pytest.fixture
def barrios():
    gdf = gpd.GeoDataFrame(
        {"id_sector": ["0101", "1902", "8105"], "nombre": ["A", "B", "C"]},
        geometry=[shapely.box(0, 0, 1, 1), shapely.box(1, 0, 2, 1), shapely.box(2, 0, 3, 1)],
        crs="EPSG:4326",
    )
    return preparar_barrios(gdf)


def test_comuna_de():
    assert comuna_de("0610") == "Comuna 6"
    assert comuna_de("2201") == "Comuna 22"
    assert comuna_de("8119") == "Área de expansión"
    assert comuna_de("9901") == "Sin comuna"


def test_orden_comunas():
    assert orden_comunas(["Comuna 10", "Área de expansión", "Comuna 2", "Comuna 2"]) == [
        "Comuna 2", "Comuna 10", "Área de expansión"]


def test_puestos_con_empates_y_huecos():
    # 1 = valor más alto; los empates comparten puesto; sin dato → 0
    assert puestos([5.0, 9.0, 9.0, np.nan, 1.0]).tolist() == [3, 1, 1, 0, 4]


def test_agregar():
    assert agregar([1.0, np.nan, 3.0], "media") == 2.0
    assert agregar([1.0, np.nan, 3.0], "suma") == 4.0
    assert np.isnan(agregar([np.nan, np.nan], "suma"))  # sin datos no es 0 mm
    m = np.array([[1.0, 2.0], [np.nan, np.nan]])
    assert agregar(m, "suma", axis=1)[0] == 3.0 and np.isnan(agregar(m, "suma", axis=1)[1])


def test_rango_fechas():
    assert rango_fechas(pd.Timestamp("2026-08-01"), pd.Timestamp("2026-08-31")) == "01–31 ago 2026"
    assert rango_fechas(pd.Timestamp("2026-08-28"), pd.Timestamp("2026-09-05")) == "28 ago – 05 sep 2026"
    assert rango_fechas(pd.Timestamp("2014-06-01"), pd.Timestamp("2025-01-31")) == "jun 2014 – ene 2025"


def test_barrio_en_clic(barrios):
    assert barrio_en_clic(barrios, {"last_clicked": {"lat": 0.5, "lng": 1.5}}) == "B"
    assert barrio_en_clic(barrios, {"last_clicked": {"lat": 5, "lng": 5}}) is None
    assert barrio_en_clic(barrios, {"last_clicked": None}) is None
    assert barrio_en_clic(barrios, None) is None


def test_preparar_barrios_agrega_comuna(barrios):
    assert barrios["comuna"].tolist() == ["Comuna 1", "Comuna 19", "Área de expansión"]


def test_geojson_barrios(barrios):
    tabla = pd.DataFrame({"Barrio": ["B", "A"], "Valor": [2.5, 1.0], "Serie": [[1, 2], [3, 4]]})
    geo = json.loads(geojson_barrios(barrios, tabla, "Barrio"))
    assert [f["properties"]["Barrio"] for f in geo["features"]] == ["B", "A"]
    assert "Serie" not in geo["features"][0]["properties"]  # sin columnas de mini-gráficos
    assert geo["features"][0]["geometry"]["type"] == "Polygon"
