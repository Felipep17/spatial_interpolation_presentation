from pathlib import Path
import streamlit as st
from components.ui import apply_custom_css, render_footer
from utils import cargar_shapefile
from views import estaciones, satelital

# Configuración de página
st.set_page_config(
    page_title="Plataforma de Análisis Espacial Cali",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inyección de estilos modernos
apply_custom_css()

# =========================================================================
# RUTA DINÁMICA: Directorio raíz de la aplicación
# =========================================================================
BASE_DIR = Path(__file__).resolve().parent
INPUTS_PATH = BASE_DIR / "inputs"

if not INPUTS_PATH.exists():
    st.error(f"❌ No se encontró la carpeta 'inputs' en: {INPUTS_PATH}")
    st.info("Asegúrate de que la carpeta 'inputs' esté presente en el proyecto.")
    st.stop()

# =========================================================================
# Cargar Capa Vectorial (Shapefile/GeoParquet)
# =========================================================================
with st.spinner("Cargando capa vectorial de referencia..."):
    try:
        gdf = cargar_shapefile(INPUTS_PATH / "shapefiles")
    except Exception as e:
        st.error(f"Error cargando archivo vectorial: {e}")
        st.stop()

# =========================================================================
# Barra Lateral (Sidebar)
# =========================================================================
with st.sidebar:
    st.markdown(
        """
        <div style="padding: 10px 0 15px 0;">
            <div style="font-size: 18px; font-weight: 800; color: #1e293b;">🌐 GeoClima Cali</div>
            <div style="font-size: 12px; color: #64748b;">Sistema de Monitoreo & Asimilación</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### 🧭 Módulo de Visualización")
    vista = st.radio(
        "Seleccione el enfoque:",
        ["Fuentes Satelitales", "Estaciones Meteorológicas"],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown("### 📍 Contexto Espacial")
    col_sb1, col_sb2 = st.columns(2)
    with col_sb1:
        st.metric("Barrios/Polígonos", len(gdf))
    with col_sb2:
        st.metric("CRS Base", "EPSG:4326")

    st.markdown("---")
    st.caption("ℹ️ Datos integrados desde sensores in-situ, Copernicus C3S y CHIRPS 3.0.")

# =========================================================================
# Enrutamiento de Vistas
# =========================================================================
if vista == "Fuentes Satelitales":
    satelital.render(gdf, INPUTS_PATH)
elif vista == "Estaciones Meteorológicas":
    estaciones.render(gdf, INPUTS_PATH)

render_footer()
