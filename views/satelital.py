import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path
from utils import (
    listar_fuentes,
    cargar_recorte_nc,
    calcular_estadisticas_zonales,
    generar_mapa_interactivo,
    generar_mapa_chirps,
)

ENLACES = {
    "C3S": "https://cds.climate.copernicus.eu/datasets/sis-agrometeorological-indicators?tab=overview",
    "CHIRPS": "https://www.chc.ucsb.edu/data/chirps3",
    "MSWEP": "https://climatedataguide.ucar.edu/climate-data/global-high-resolution-precipitation-mswep",
    "GEE": None,
}

def render(gdf, inputs_path: Path):
    st.title("🛰️ Fuentes Satelitales")
    fuentes = listar_fuentes(inputs_path / "raster")
    if not fuentes:
        st.warning("No se encontraron carpetas raster.")
        return

    pestanas = st.tabs(list(fuentes.keys()))
    for nombre, tab in zip(fuentes.keys(), pestanas):
        with tab:
            st.subheader(f"Fuente: {nombre}")
            url = ENLACES.get(nombre.upper())
            if url:
                st.caption(f"🌐 [Ver Documentación Oficial y Acceso a Datos]({url})")

            archivos = fuentes[nombre]

            if nombre.upper() == "C3S":
                f_rh = next((f for f in archivos if "relative_humidity" in f.name), None)
                f_t = next((f for f in archivos if "temperature_maximu" in f.name or "t2m" in f.name), None)
                if f_rh and f_t:
                    with st.spinner("Procesando C3S..."):
                        da_rh, lat_c, lon_c, pad = cargar_recorte_nc(f_rh, gdf.total_bounds)
                        da_t, _, _, _ = cargar_recorte_nc(f_t, gdf.total_bounds)
                        stats, times, lats, lons = calcular_estadisticas_zonales(gdf, da_rh, da_t, lat_c, lon_c, pad)
                        mapa = generar_mapa_interactivo(gdf, da_rh, da_t, stats, times, lats, lons, pad)
                        mapa_html = mapa.get_root().render()
                    components.html(mapa_html, height=820, scrolling=False)
                else:
                    st.warning("Archivos de HR o Temperatura no encontrados.")

            elif nombre.upper() == "CHIRPS":
                f_ch = next((f for f in archivos if "chirps" in f.name.lower() and f.suffix == ".nc"), None)
                if f_ch:
                    with st.spinner("Procesando precipitación CHIRPS..."):
                        mapa_ch = generar_mapa_chirps(gdf, f_ch)
                        mapa_ch_html = mapa_ch.get_root().render()
                    components.html(mapa_ch_html, height=820, scrolling=False)
                else:
                    st.warning("No se encontró el archivo NetCDF de CHIRPS.")

            else:
                if archivos:
                    data = [{"Archivo": a.name, "Extensión": a.suffix, "Tamaño (MB)": round(a.stat().st_size / (1024 * 1024), 2)} for a in archivos]
                    st.dataframe(data, use_container_width=True)
                else:
                    st.info(f"Sin archivos en {nombre}.")