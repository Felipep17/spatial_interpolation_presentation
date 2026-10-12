import streamlit as st
from pathlib import Path

def render(gdf, inputs_path: Path):
    st.title("📡 Estaciones Meteorológicas")
    st.info("Módulo preparado para interpolación y estaciones en tierra (CVC, IDEAM, etc.).")