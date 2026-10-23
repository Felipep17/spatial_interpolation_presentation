import os
from pathlib import Path
import streamlit as st
from utils import cargar_shapefile
from views import estaciones, satelital

st.set_page_config(page_title="Interpolación Espacial", layout="wide")

# =========================================================================
# RUTA DINÁMICA: Encuentra la carpeta raíz donde está app.py automáticamente
# =========================================================================
BASE_DIR = Path(__file__).resolve().parent
INPUTS_PATH = BASE_DIR / "inputs"

# Verificación de que la carpeta existe para evitar caídas silenciosas
if not INPUTS_PATH.exists():
    st.error(f"❌ No se encontró la carpeta 'inputs' en: {INPUTS_PATH}")
    st.info("Asegúrate de que la carpeta 'inputs' esté subida a tu repositorio.")
    st.stop()

# =========================================================================
# Cargar Shapefile
# =========================================================================
try:
    gdf = cargar_shapefile(INPUTS_PATH / "shapefiles")
except Exception as e:
    st.error(f"Error cargando shapefile: {e}")
    st.stop()

with st.sidebar:
    st.header("📌 Navegación")
    vista = st.radio(
        "Seleccionar Vista:",
        ["Fuentes Satelitales", "Estaciones Meteorológicas"],
    )

if vista == "Fuentes Satelitales":
    satelital.render(gdf, INPUTS_PATH)
elif vista == "Estaciones Meteorológicas":
    estaciones.render(gdf, INPUTS_PATH)