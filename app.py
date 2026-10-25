"""GeoClima Cali · punto de entrada (Streamlit Cloud ejecuta este archivo).

Solo arma la aplicación: configuración, idioma, capa de barrios, navegación y marco común.
El código vive en el paquete geoclima/ (datos, mapas, ui y paginas).
"""

import streamlit as st

from geoclima.datos.barrios import cargar_shapefile
from geoclima.paginas import barrio, estaciones, panorama, satelital
from geoclima.rutas import ASSETS, INPUTS, SHAPEFILES
from geoclima.ui.barra_lateral import barra_lateral, selector_idioma
from geoclima.ui.componentes import apply_custom_css, franja_aliados, render_footer
from geoclima.ui.i18n import t
from geoclima.ui.navegacion import PAGINAS

LOGO_ALIADOS = ASSETS / "aliados.png"

st.set_page_config(
    page_title="GeoClima Cali",
    page_icon=":material/public:",
    layout="wide",
    initial_sidebar_state="auto",  # abierta en escritorio, cerrada en móvil
)
apply_custom_css()
selector_idioma()  # primero: el idioma traduce también los títulos de las páginas

# =========================================================================
# Capa vectorial de referencia
# =========================================================================
if not INPUTS.exists():
    st.error(t("app.sin_inputs", ruta=INPUTS))
    st.stop()
try:
    gdf = cargar_shapefile(SHAPEFILES)
except FileNotFoundError as e:
    st.error(t("app.sin_vector", error=e))
    st.stop()
except Exception as e:  # lectura/reproyección
    st.error(t("app.error_vector", error=e))
    st.stop()


# =========================================================================
# Navegación nativa: solo se ejecuta la página activa
# =========================================================================
def _pagina_panorama():
    panorama.render(gdf, INPUTS, paginas={
        "satelital": (pag_satelital, ":material/satellite_alt:"),
        "estaciones": (pag_estaciones, ":material/sensors:"),
        "barrio": (pag_barrio, ":material/location_city:"),
    })


def _pagina_satelital():
    satelital.render(gdf, INPUTS)


def _pagina_estaciones():
    estaciones.render(gdf, INPUTS)


def _pagina_barrio():
    barrio.render(gdf, INPUTS)


# La página por defecto siempre se sirve en "/". Las rutas son fijas: no cambian con el idioma.
pag_panorama = st.Page(_pagina_panorama, title=t("nav.panorama"), icon=":material/dashboard:", default=True,
                       url_path="panorama")
pag_satelital = st.Page(_pagina_satelital, title=t("nav.satelital"), icon=":material/satellite_alt:",
                        url_path="satelital")
pag_estaciones = st.Page(_pagina_estaciones, title=t("nav.estaciones"), icon=":material/sensors:",
                         url_path="estaciones")
pag_barrio = st.Page(_pagina_barrio, title=t("nav.barrio"), icon=":material/location_city:", url_path="barrio")
PAGINAS.update(panorama=pag_panorama, satelital=pag_satelital, estaciones=pag_estaciones, barrio=pag_barrio)

st.logo(ASSETS / "logo.svg", icon_image=ASSETS / "icon.svg", size="large")
nav = st.navigation(
    {t("nav.resumen"): [pag_panorama], t("nav.modulos"): [pag_satelital, pag_estaciones, pag_barrio]},
    position="sidebar",
)

# =========================================================================
# Marco común: barra lateral, franja institucional, página activa y pie
# =========================================================================
barra_lateral(gdf)
franja_aliados(LOGO_ALIADOS)
nav.run()
render_footer(LOGO_ALIADOS)
