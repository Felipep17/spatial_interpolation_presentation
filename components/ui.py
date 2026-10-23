import streamlit as st

def apply_custom_css():
    """Aplica estilos CSS personalizados a la aplicación Streamlit."""
    st.markdown("""
        <style>
        /* Importar fuente Inter */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }

        /* Estilo general del contenedor */
        .main .block-container {
            padding-top: 2