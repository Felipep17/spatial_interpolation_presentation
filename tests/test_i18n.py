"""Pruebas del módulo de traducción (geoclima/ui/i18n.py)."""

import re
from pathlib import Path

import pandas as pd
import pytest

from geoclima.datos.fuentes import INDICADORES
from geoclima.ui.i18n import IDIOMAS, TEXTOS, locale_js, meses, rango_fechas, t, t_comuna
from geoclima.ui.tema import RASTER_VARS, VARIABLES

RAIZ = Path(__file__).resolve().parent.parent
FUENTES_PY = [RAIZ / "app.py", *sorted((RAIZ / "geoclima").rglob("*.py"))]


def test_todas_las_claves_tienen_ambos_idiomas():
    for clave, textos in TEXTOS.items():
        assert set(textos) == set(IDIOMAS), clave
        assert all(textos[lang].strip() for lang in IDIOMAS), f"texto vacío en {clave}"


def test_mismos_campos_de_formato_en_ambos_idiomas():
    campos = re.compile(r"\{(\w+)")
    for clave, textos in TEXTOS.items():
        assert set(campos.findall(textos["es"])) == set(campos.findall(textos["en"])), clave


def test_las_claves_usadas_en_el_codigo_existen():
    """Toda clave literal t("…") del código está definida (las dinámicas se prueban aparte)."""
    patron = re.compile(r"""\bt\(\s*["']([a-z_]+\.[\w.]+)["']""")
    usadas = {c for f in FUENTES_PY for c in patron.findall(f.read_text(encoding="utf-8"))}
    assert usadas, "no se encontraron claves: revise el patrón"
    faltantes = sorted(usadas - set(TEXTOS))
    assert not faltantes, faltantes


@pytest.mark.parametrize("lang", IDIOMAS)
def test_claves_dinamicas(lang):
    # Variables, etiquetas cortas, agregaciones, indicadores y modos se construyen con f-strings
    for spec in [*VARIABLES.values(), *RASTER_VARS.values()]:
        assert spec.texto(lang)
        assert t(f"agg.{spec.agregacion_id}", lang)
    for clave in VARIABLES.values():
        assert t(f"var_corta.{clave.id}", lang)
    for ind in INDICADORES:
        assert t(ind.texto, lang) and t(f"modo.{ind.modo}", lang) and t(f"bar.ayuda_{ind.modo}", lang, periodo="x")
        assert t(f"fuente.{ind.fuente}.variables", lang) and t(f"fuente.{ind.fuente}.desc", lang)


def test_terminos_clave_en_ingles():
    esperados = {
        "pan.titulo": "Hydrometeorological Overview of Cali",
        "nav.satelital": "Satellite Sources & Reanalysis",
        "nav.estaciones": "In-situ Weather Stations",
        "nav.barrio": "Neighborhood Profile",
        "graf.semana_epi": "Epidemiological Week",
        "ind.lluvia_acumulada": "Accumulated Rainfall",
        "var.hr": "Relative Humidity",
        "var.tmax": "Maximum Temperature",
    }
    for clave, texto in esperados.items():
        assert t(clave, "en") == texto
    assert t("bar.vecinos", "en", n=13) == "Neighboring Neighborhoods (13)"


def test_formato_y_clave_inexistente():
    assert t("gen.a_de_b", "es", a=3, b=357) == "3 de 357"
    assert t("gen.a_de_b", "en", a=3, b=357) == "3 of 357"
    with pytest.raises(KeyError):
        t("no.existe", "es")


def test_t_comuna():
    assert t_comuna("Comuna 19", "en") == "Commune 19"
    assert t_comuna("Comuna 19", "es") == "Comuna 19"
    assert t_comuna("Área de expansión", "en") == "Urban expansion area"
    assert t_comuna("Fuera del perímetro urbano", "en") == "Outside the urban perimeter"
    assert t_comuna("Barrio X", "en") == "Barrio X"  # valores desconocidos no se tocan


def test_fechas_y_locale():
    assert meses("en")[7] == "Aug" and meses("es")[7] == "ago"
    assert rango_fechas(pd.Timestamp("2026-08-01"), pd.Timestamp("2026-08-31"), "en") == "01–31 Aug 2026"
    assert rango_fechas(pd.Timestamp("2014-06-01"), pd.Timestamp("2025-01-31"), "en") == "Jun 2014 – Jan 2025"
    # Punto decimal en ambos idiomas, como el resto de la app
    assert locale_js("en") == locale_js("es") == "en-US"
