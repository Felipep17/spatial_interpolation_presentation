from pathlib import Path

import streamlit as st

from components.i18n import CLAVE_IDIOMA, IDIOMA_DEFECTO, IDIOMAS, marcar_idioma, t
from components.nav import PAGINAS, ir_a_barrio
from components.ui import apply_custom_css, badge_html, render_footer, sidebar_label
from datos import FUENTES_META, periodo_estaciones, periodos_fuentes, rango_fechas
from utils import cargar_shapefile, orden_comunas, preparar_barrios
from views import barrio, estaciones, panorama, satelital

st.set_page_config(
    page_title="GeoClima Cali",
    page_icon=":material/public:",
    layout="wide",
    initial_sidebar_state="auto",  # abierta en escritorio, cerrada en móvil
)
apply_custom_css()

# =========================================================================
# Idioma: se elige antes que todo lo demás porque traduce también los títulos de las páginas.
# El selector está ligado a la URL (?lang=es|en); la navegación se dibuja arriba de la barra lateral
# aunque se cree después, así que el selector queda debajo del menú.
# =========================================================================
with st.sidebar:
    lang = st.segmented_control(
        "Idioma · Language", IDIOMAS, default=IDIOMA_DEFECTO, required=True, key=CLAVE_IDIOMA,
        bind="query-params", label_visibility="collapsed",
    )
marcar_idioma(lang)

# =========================================================================
# Rutas
# =========================================================================
BASE_DIR = Path(__file__).resolve().parent
INPUTS_PATH = BASE_DIR / "inputs"
ASSETS_PATH = BASE_DIR / "assets"

if not INPUTS_PATH.exists():
    st.error(t("app.sin_inputs", ruta=INPUTS_PATH))
    st.stop()

# =========================================================================
# Capa vectorial de referencia
# =========================================================================
try:
    gdf = cargar_shapefile(INPUTS_PATH / "shapefiles")
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
    panorama.render(gdf, INPUTS_PATH, paginas={
        "satelital": (pag_satelital, ":material/satellite_alt:"),
        "estaciones": (pag_estaciones, ":material/sensors:"),
        "barrio": (pag_barrio, ":material/location_city:"),
    })


def _pagina_satelital():
    satelital.render(gdf, INPUTS_PATH)


def _pagina_estaciones():
    estaciones.render(gdf, INPUTS_PATH)


def _pagina_barrio():
    barrio.render(gdf, INPUTS_PATH)


# La página por defecto siempre se sirve en "/". Las rutas son fijas: no cambian con el idioma.
pag_panorama = st.Page(_pagina_panorama, title=t("nav.panorama"), icon=":material/dashboard:", default=True,
                       url_path="panorama")
pag_satelital = st.Page(_pagina_satelital, title=t("nav.satelital"), icon=":material/satellite_alt:",
                        url_path="satelital")
pag_estaciones = st.Page(_pagina_estaciones, title=t("nav.estaciones"), icon=":material/sensors:",
                         url_path="estaciones")
pag_barrio = st.Page(_pagina_barrio, title=t("nav.barrio"), icon=":material/location_city:", url_path="barrio")
paginas = {
    t("nav.resumen"): [pag_panorama],
    t("nav.modulos"): [pag_satelital, pag_estaciones, pag_barrio],
}

PAGINAS.update(panorama=pag_panorama, satelital=pag_satelital, estaciones=pag_estaciones, barrio=pag_barrio)

st.logo(ASSETS_PATH / "logo.svg", icon_image=ASSETS_PATH / "icon.svg", size="large")
nav = st.navigation(paginas, position="sidebar")

# =========================================================================
# Barra lateral: búsqueda de barrio, periodos de datos y referencia espacial
# =========================================================================
barrios_ref = preparar_barrios(gdf)


def _buscar_barrio():
    """Guarda el destino y limpia el buscador (la navegación ocurre fuera del callback)."""
    st.session_state["_ir_barrio"] = st.session_state.get("gc_buscar")
    st.session_state["gc_buscar"] = None


with st.sidebar:
    sidebar_label(t("side.ir_barrio"))
    st.selectbox(
        t("side.buscar"), sorted(barrios_ref["nombre_barrio"]), index=None, key="gc_buscar",
        placeholder=t("side.placeholder"), label_visibility="collapsed", on_change=_buscar_barrio,
        help=t("side.buscar_ayuda"),
    )

    sidebar_label(t("side.periodo"))
    filas = [
        f'<div class="gc-side-row"><span>{FUENTES_META.get(f, {}).get("corto", f)}</span>'
        f"<span>{rango_fechas(t0, t1)}</span></div>"
        for f, (t0, t1) in periodos_fuentes(INPUTS_PATH).items()
    ]
    csv_estaciones = INPUTS_PATH / "climaticas_post_calidad.csv"
    if csv_estaciones.exists():
        t0, t1 = periodo_estaciones(str(csv_estaciones), csv_estaciones.stat().st_mtime)
        filas.append(f'<div class="gc-side-row"><span>{t("gen.estaciones")}</span>'
                     f"<span>{rango_fechas(t0, t1)}</span></div>")
    st.html(f'<div class="gc-side-list">{"".join(filas)}</div>')

    sidebar_label(t("side.referencia"))
    epsg = gdf.crs.to_epsg() if gdf.crs else None
    minx, miny, maxx, maxy = gdf.total_bounds
    n_comunas = len([c for c in orden_comunas(barrios_ref["comuna"]) if c.startswith("Comuna")])
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

# Franja institucional compacta (arriba a la derecha) visible al abrir cualquier página
LOGO_ALIADOS = INPUTS_PATH / "logo.png"


@st.cache_resource
def _logo_recortado(ruta: Path, mtime: float):
    """Recorta el margen transparente del PNG para que los logos se vean más grandes."""
    from PIL import Image

    img = Image.open(ruta)
    return img.crop(img.getchannel("A").getbbox()) if img.mode == "RGBA" else img


if LOGO_ALIADOS.exists():
    with st.container(horizontal=True, horizontal_alignment="right", key="gc_topbar"):
        st.image(_logo_recortado(LOGO_ALIADOS, LOGO_ALIADOS.stat().st_mtime), width=440)

nav.run()
render_footer(LOGO_ALIADOS)
