"""Barra lateral común a todas las páginas: idioma, búsqueda de barrio, periodos de datos y referencia espacial."""

import streamlit as st

from geoclima.datos.barrios import orden_comunas, preparar_barrios
from geoclima.datos.estaciones import periodo_estaciones
from geoclima.datos.fuentes import FUENTES_META, periodos_fuentes
from geoclima.rutas import CSV_ESTACIONES, INPUTS
from geoclima.ui.componentes import badge_html, sidebar_label
from geoclima.ui.i18n import CLAVE_IDIOMA, IDIOMA_DEFECTO, IDIOMAS, marcar_idioma, rango_fechas, t
from geoclima.ui.navegacion import ir_a_barrio


def selector_idioma():
    """Selector ES / EN ligado a la URL (?lang=es|en).

    Se dibuja antes que todo lo demás porque el idioma traduce también los títulos de las páginas; la
    navegación queda arriba de la barra lateral aunque se cree después, así que el selector va debajo del menú.
    """
    with st.sidebar:
        lang = st.segmented_control(
            "Idioma · Language", IDIOMAS, default=IDIOMA_DEFECTO, required=True, key=CLAVE_IDIOMA,
            bind="query-params", label_visibility="collapsed",
        )
    marcar_idioma(lang)


def _buscar_barrio():
    """Guarda el destino y limpia el buscador (la navegación ocurre fuera del callback)."""
    st.session_state["_ir_barrio"] = st.session_state.get("gc_buscar")
    st.session_state["gc_buscar"] = None


def barra_lateral(gdf):
    """Búsqueda de barrio, periodo de cada fuente y referencia espacial de la capa de barrios."""
    barrios = preparar_barrios(gdf)
    with st.sidebar:
        sidebar_label(t("side.ir_barrio"))
        st.selectbox(
            t("side.buscar"), sorted(barrios["nombre_barrio"]), index=None, key="gc_buscar",
            placeholder=t("side.placeholder"), label_visibility="collapsed", on_change=_buscar_barrio,
            help=t("side.buscar_ayuda"),
        )

        sidebar_label(t("side.periodo"))
        filas = [
            f'<div class="gc-side-row"><span>{FUENTES_META.get(f, {}).get("corto", f)}</span>'
            f"<span>{rango_fechas(t0, t1)}</span></div>"
            for f, (t0, t1) in periodos_fuentes(INPUTS).items()
        ]
        if CSV_ESTACIONES.exists():
            t0, t1 = periodo_estaciones(str(CSV_ESTACIONES), CSV_ESTACIONES.stat().st_mtime)
            filas.append(f'<div class="gc-side-row"><span>{t("gen.estaciones")}</span>'
                         f"<span>{rango_fechas(t0, t1)}</span></div>")
        st.html(f'<div class="gc-side-list">{"".join(filas)}</div>')

        sidebar_label(t("side.referencia"))
        epsg = gdf.crs.to_epsg() if gdf.crs else None
        minx, miny, maxx, maxy = gdf.total_bounds
        n_comunas = len([c for c in orden_comunas(barrios["comuna"]) if c.startswith("Comuna")])
        st.html(
            '<div class="gc-side-grid">'
            + badge_html("CRS", "blue", f"EPSG:{epsg}" if epsg else t("side.sin_definir"))
            + badge_html(t("gen.barrios"), "gray", f"{len(gdf):,}")
            + (badge_html(t("gen.comunas"), "gray", str(n_comunas)) if n_comunas else "")
            + "</div>"
            f'<div class="gc-side-meta" style="margin-top:8px;">Lat <code>{miny:.3f}° → {maxy:.3f}°</code><br>'
            f"Lon <code>{minx:.3f}° → {maxx:.3f}°</code></div>"
        )
        st.caption(t("side.creditos"))

    destino = st.session_state.pop("_ir_barrio", None)
    if destino:
        ir_a_barrio(destino)
