"""Pruebas de humo: cada página se ejecuta completa con los datos de inputs/ sin excepciones,
en español y en inglés.

Ejecutar: uv run pytest
"""

from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from geoclima.datos import fuentes, raster
from geoclima.ui.i18n import CLAVE_IDIOMA, t

RAIZ = Path(__file__).resolve().parent.parent
TIEMPO = 300  # la primera ejecución procesa todas las fuentes raster

# Cada vista se ejecuta como la ejecuta app.py: mismo GeoDataFrame y misma carpeta de entradas
PLANTILLA = """
from pathlib import Path
import streamlit as st
from geoclima.datos.barrios import cargar_shapefile
from geoclima.paginas import {modulo}
from geoclima.ui.componentes import apply_custom_css

apply_custom_css()
INPUTS = Path(r"{raiz}") / "inputs"
gdf = cargar_shapefile(INPUTS / "shapefiles")
{modulo}.render(gdf, INPUTS)
"""


def _pagina(modulo: str, lang: str = "es", **query) -> AppTest:
    at = AppTest.from_string(PLANTILLA.format(modulo=modulo, raiz=RAIZ), default_timeout=TIEMPO)
    # En la app el idioma lo fija el selector de la barra lateral; aquí se fija directamente en la sesión
    at.session_state[CLAVE_IDIOMA] = lang
    for k, v in query.items():
        at.query_params[k] = v
    return at.run()


def _sin_errores(at: AppTest):
    assert not at.exception, [e.message for e in at.exception]
    assert not at.error, [e.value for e in at.error]


def _textos_html(at: AppTest) -> str:
    return " ".join(str(h.proto.body) for h in at.get("html"))


@pytest.mark.parametrize("lang", ["es", "en"])
def test_panorama(lang):
    at = _pagina("panorama", lang)
    _sin_errores(at)
    assert len(at.metric) >= 4
    assert t("pan.titulo", lang) in _textos_html(at)
    # Explorador de barrios: selector de indicador y de ámbito (comuna)
    assert at.segmented_control(key="pan_ind").value
    assert at.selectbox(key="pan_ambito").value == "Toda Cali"  # valor interno; se muestra traducido


@pytest.mark.parametrize("lang", ["es", "en"])
@pytest.mark.parametrize(("indicador", "ambito"), [("C3S:rh", "Toda Cali"), ("CHIRPS:p", "Comuna 19"),
                                                  ("GEE:ndvi", "Área de expansión")])
def test_panorama_animacion_diaria(lang, indicador, ambito):
    at = AppTest.from_string(PLANTILLA.format(modulo="panorama", raiz=RAIZ), default_timeout=TIEMPO)
    at.session_state[CLAVE_IDIOMA] = lang
    at.session_state["pan_modo"] = "animacion"
    at.session_state["pan_ind"] = indicador
    at.session_state["pan_ambito"] = ambito
    at.run()
    _sin_errores(at)
    assert at.segmented_control(key="pan_modo").value == "animacion"
    assert at.segmented_control(key="pan_ind").value == indicador


@pytest.mark.parametrize("lang", ["es", "en"])
def test_panorama_por_comuna(lang):
    at = _pagina("panorama", lang)
    # Opciones: [Toda Cali, Comuna 1 … Comuna 22, Área de expansión]. AppTest compara con la etiqueta visible
    # («Commune 19» en inglés), así que se elige por posición.
    at.selectbox(key="pan_ambito").select_index(19).run()
    _sin_errores(at)
    assert at.selectbox(key="pan_ambito").value == "Comuna 19"


@pytest.mark.parametrize(("fuente", "carpeta"), [("AgERA5", "C3S"), ("CHIRPS", "CHIRPS"), ("MSWEP", "MSWEP"),
                                               ("MODIS", "GEE")])
@pytest.mark.parametrize(("lang", "vista", "clave"), [
    ("es", "Visor diario", "diario"), ("es", "Mapa por barrio", "periodo"),
    ("en", "Daily viewer", "diario"), ("en", "Map by neighborhood", "periodo"),
])
def test_fuentes_satelitales(fuente, carpeta, lang, vista, clave):
    # Los enlaces usan la etiqueta visible en el idioma del enlace (?lang=en&vista=Map+by+neighborhood)
    at = _pagina("satelital", lang, fuente=fuente, vista=vista)
    _sin_errores(at)
    assert at.segmented_control(key="fuente").value == carpeta
    assert at.segmented_control(key="vista").value == clave
    assert len(at.metric) == 4
    # Enlace al sitio oficial de cada fuente; la elegida resaltada
    enlaces = {b.proto.label: b.proto for b in at.get("link_button")}
    assert {m["corto"] for m in fuentes.FUENTES_META.values()} <= set(enlaces)
    assert enlaces[fuentes.FUENTES_META[carpeta]["corto"]].type == "primary"


@pytest.mark.parametrize("fuente", ["AgERA5", "CHIRPS", "MODIS"])
def test_fuentes_animacion_por_barrio(fuente):
    at = AppTest.from_string(PLANTILLA.format(modulo="satelital", raiz=RAIZ), default_timeout=TIEMPO)
    clave = {"AgERA5": "sat_c3s", "CHIRPS": "sat_chirps", "MODIS": "sat_gee"}[fuente]
    at.session_state[f"{clave}_modo"] = "animacion"
    at.query_params["fuente"] = fuente
    at.query_params["vista"] = "Mapa por barrio"
    at.run()
    _sin_errores(at)
    assert at.segmented_control(key=f"{clave}_modo").value == "animacion"


@pytest.mark.parametrize("lang", ["es", "en"])
def test_estaciones(lang):
    at = _pagina("estaciones", lang)
    _sin_errores(at)
    assert at.selectbox(key="estacion").value
    # Ciclo anual y calendario por semana epidemiológica
    assert at.selectbox(key="anio_epi").value
    assert t("est.titulo", lang) in _textos_html(at)


@pytest.mark.parametrize("lang", ["es", "en"])
def test_estaciones_grillas(lang):
    """Grillas de 1 km (GEE) y 11 km (AgERA5) activas a la vez: cada una con su resumen."""
    at = _pagina("estaciones", lang)
    at.toggle(key="grilla_1km").set_value(True)
    at.toggle(key="grilla_agera5").set_value(True).run()
    _sin_errores(at)
    html = _textos_html(at)
    assert t("est.origen_gee", lang) in html and t("est.origen_agera5", lang) in html
    assert "0.100°" in html  # tamaño de celda de AgERA5


@pytest.mark.parametrize(("lang", "variable", "columna"), [
    ("es", "Precipitación", "Precipitacion"), ("es", "T. máxima", "Tmax"), ("es", "Humedad", "Humedad relativa"),
    ("en", "Precipitation", "Precipitacion"), ("en", "Max. temp.", "Tmax"),
])
def test_estaciones_variables(lang, variable, columna):
    at = _pagina("estaciones", lang, variable=variable)
    _sin_errores(at)
    assert at.segmented_control(key="variable").value == columna


@pytest.mark.parametrize("lang", ["es", "en"])
def test_perfil_barrio_desde_url(lang):
    at = _pagina("barrio", lang, barrio="Nueva Floresta")
    _sin_errores(at)
    assert at.selectbox(key="barrio").value == "Nueva Floresta"
    assert len(at.metric) == 6


def test_perfil_barrio_comparado():
    at = _pagina("barrio", "en", barrio="Nueva Floresta")
    at.multiselect(key="comparar").select("Belalcázar").select("El Ingenio").run()
    _sin_errores(at)
    assert at.multiselect(key="comparar").value == ["Belalcázar", "El Ingenio"]


# =========================================================================
# Aplicación completa: selector de idioma ligado a la URL
# =========================================================================
@pytest.mark.parametrize("lang", ["es", "en"])
def test_app_idioma_desde_url(lang):
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=TIEMPO)
    at.query_params[CLAVE_IDIOMA] = lang
    at.run()
    _sin_errores(at)
    assert at.segmented_control(key=CLAVE_IDIOMA).value == lang
    html = _textos_html(at)
    assert t("pan.titulo", lang) in html  # Panorama es la página por defecto
    assert t("side.ir_barrio", lang) in html  # barra lateral


# El cambio de idioma dentro de una misma sesión (conservando selecciones) se verifica en el navegador:
# AppTest vuelve a aplicar format_func fuera de la ejecución del script, donde no hay idioma de sesión.


# =========================================================================
# Eficiencia: cambiar de idioma no relee NetCDF ni recalcula estadísticas zonales
# =========================================================================
def test_cambio_de_idioma_no_recalcula_datos(monkeypatch):
    llamadas = {"netcdf": 0, "zonales": 0}

    def contar(nombre, funcion):
        def envoltura(*args, **kwargs):
            llamadas[nombre] += 1
            return funcion(*args, **kwargs)
        return envoltura

    # fuentes.py usa estas funciones de raster.py: se cuentan donde las llama
    monkeypatch.setattr(fuentes, "cargar_grilla_nc", contar("netcdf", raster.cargar_grilla_nc))
    monkeypatch.setattr(fuentes, "cargar_recorte_nc", contar("netcdf", raster.cargar_recorte_nc))
    monkeypatch.setattr(fuentes, "estadisticas_zonales", contar("zonales", raster.estadisticas_zonales))
    monkeypatch.setattr(fuentes, "calcular_estadisticas_zonales",
                        contar("zonales", raster.calcular_estadisticas_zonales))
    st.cache_data.clear()  # partir de cero para que la primera ejecución sí procese

    at = _pagina("satelital", "es", fuente="MODIS")
    _sin_errores(at)
    assert llamadas["netcdf"] > 0 and llamadas["zonales"] > 0
    antes = dict(llamadas)

    at.session_state[CLAVE_IDIOMA] = "en"
    at.run()
    _sin_errores(at)
    assert llamadas == antes  # solo se regeneraron textos y el HTML del visor en inglés
