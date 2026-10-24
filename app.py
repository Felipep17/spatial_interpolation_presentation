from pathlib import Path

import streamlit as st

from components.ui import apply_custom_css, badge_html, render_footer, sidebar_label
from utils import cargar_shapefile, listar_fuentes
from views import barrio, estaciones, panorama, satelital

st.set_page_config(
    page_title="GeoClima Cali",
    page_icon=":material/public:",
    layout="wide",
    initial_sidebar_state="auto",  # abierta en escritorio, cerrada en móvil
)
apply_custom_css()

# =========================================================================
# Rutas
# =========================================================================
BASE_DIR = Path(__file__).resolve().parent
INPUTS_PATH = BASE_DIR / "inputs"
ASSETS_PATH = BASE_DIR / "assets"

if not INPUTS_PATH.exists():
    st.error(f"No se encontró la carpeta 'inputs' en: {INPUTS_PATH}")
    st.stop()

# =========================================================================
# Capa vectorial de referencia
# =========================================================================
try:
    gdf = cargar_shapefile(INPUTS_PATH / "shapefiles")
except FileNotFoundError as e:
    st.error(f"No se encontró la capa vectorial de barrios: {e}")
    st.stop()
except Exception as e:  # lectura/reproyección
    st.error(f"No fue posible leer la capa vectorial: {e}")
    st.stop()

# =========================================================================
# Navegación nativa: solo se ejecuta la página activa
# =========================================================================
def _pagina_panorama():
    panorama.render(gdf, INPUTS_PATH, paginas={
        "Explorar fuentes": (pag_satelital, ":material/satellite_alt:"),
        "Estaciones": (pag_estaciones, ":material/sensors:"),
        "Perfil de barrio": (pag_barrio, ":material/location_city:"),
    })


def _pagina_satelital():
    satelital.render(gdf, INPUTS_PATH)


def _pagina_estaciones():
    estaciones.render(gdf, INPUTS_PATH)


def _pagina_barrio():
    barrio.render(gdf, INPUTS_PATH)


# La página por defecto siempre se sirve en "/"
pag_panorama = st.Page(_pagina_panorama, title="Panorama", icon=":material/dashboard:", default=True)
pag_satelital = st.Page(_pagina_satelital, title="Fuentes satelitales", icon=":material/satellite_alt:",
                        url_path="satelital")
pag_estaciones = st.Page(_pagina_estaciones, title="Estaciones in situ", icon=":material/sensors:",
                         url_path="estaciones")
pag_barrio = st.Page(_pagina_barrio, title="Perfil de barrio", icon=":material/location_city:", url_path="barrio")
paginas = {
    "Resumen": [pag_panorama],
    "Módulos": [pag_satelital, pag_estaciones, pag_barrio],
}

st.logo(ASSETS_PATH / "logo.svg", icon_image=ASSETS_PATH / "icon.svg", size="large")
nav = st.navigation(paginas, position="sidebar")

# =========================================================================
# Barra lateral: contexto espacial y metadatos
# =========================================================================
with st.sidebar:
    epsg = gdf.crs.to_epsg() if gdf.crs else None
    minx, miny, maxx, maxy = gdf.total_bounds

    sidebar_label("Contexto espacial")
    st.html(
        '<div class="gc-side-grid">'
        + badge_html("CRS", "blue", f"EPSG:{epsg}" if epsg else "sin definir")
        + badge_html("Polígonos", "gray", f"{len(gdf):,}")
        + "</div>"
    )
    st.html(
        f"""
        <div class="gc-side-meta" style="margin-top:8px;">
            Lat <code>{miny:.3f}° → {maxy:.3f}°</code><br>
            Lon <code>{minx:.3f}° → {maxx:.3f}°</code>
        </div>
        """
    )

    sidebar_label("Fuentes de datos")
    fuentes = listar_fuentes(INPUTS_PATH / "raster")
    chips = [
        badge_html(nombre, "violet" if archivos else "gray", str(len(archivos)))
        for nombre, archivos in fuentes.items()
    ]
    if (INPUTS_PATH / "climaticas_post_calidad.csv").exists():
        chips.append(badge_html("Estaciones", "green", "CSV"))
    st.html(f'<div class="gc-side-grid">{"".join(chips)}</div>')

    st.caption("Sensores in situ, Copernicus C3S (AgERA5) y CHIRPS v3.0.")

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
