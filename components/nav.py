"""Registro de páginas para enlazar entre módulos sin importaciones circulares.

`app.py` llena `PAGINAS` al crear la navegación; las vistas solo leen de aquí.
"""

import streamlit as st

from components.i18n import CLAVE_IDIOMA, IDIOMA_DEFECTO, idioma, t

PAGINAS: dict = {}

# Clave del selector de barrio: también es el parámetro de la URL (/barrio?barrio=…)
CLAVE_BARRIO = "barrio"


def _query(nombre: str) -> dict:
    """Parámetros de la URL del perfil: el barrio y, si no es el idioma por defecto, el idioma."""
    q = {CLAVE_BARRIO: nombre}
    if idioma() != IDIOMA_DEFECTO:
        q[CLAVE_IDIOMA] = idioma()
    return q


def enlace_barrio(nombre: str, etiqueta: str | None = None, *, ancho: str = "content"):
    """Enlace al perfil de un barrio (conserva el barrio en la URL)."""
    pagina = PAGINAS.get("barrio")
    if pagina is None:
        return
    st.page_link(pagina, label=etiqueta or t("nav.abrir_perfil", nombre=nombre), icon=":material/location_city:",
                 query_params=_query(nombre), width=ancho)


def ir_a_barrio(nombre: str):
    """Navega al perfil del barrio. Debe llamarse antes de que se dibuje el selector de esa página."""
    pagina = PAGINAS.get("barrio")
    if pagina is None:
        return
    st.session_state[CLAVE_BARRIO] = nombre
    st.switch_page(pagina, query_params=_query(nombre))
