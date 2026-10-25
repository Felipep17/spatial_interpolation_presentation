"""Grilla fija de 1 km que cubre Cali: la misma de los NetCDF de GEE y de la vista de estaciones.

Se define una sola vez aquí; los scripts de descarga (descargas/gee.py) la importan.
Solo depende de numpy para que los scripts no carguen Streamlit.
"""

import numpy as np

# 0.009° ≈ 1.002 km en latitud y ≈ 1.000 km en longitud a la latitud de Cali (3.4° N)
RES_1KM = 0.009
# Margen alrededor de la extensión de Cali (grados)
MARGEN = 0.02


def grilla_1km(bounds):
    """Centros (lats descendentes, lons ascendentes) y esquina superior izquierda de la grilla para `bounds`."""
    minx, miny, maxx, maxy = bounds
    x0 = np.floor((minx - MARGEN) / RES_1KM) * RES_1KM
    x1 = np.ceil((maxx + MARGEN) / RES_1KM) * RES_1KM
    y0 = np.floor((miny - MARGEN) / RES_1KM) * RES_1KM
    y1 = np.ceil((maxy + MARGEN) / RES_1KM) * RES_1KM
    nx = int(round((x1 - x0) / RES_1KM))
    ny = int(round((y1 - y0) / RES_1KM))
    lons = np.round(x0 + RES_1KM * (np.arange(nx) + 0.5), 6)
    lats = np.round(y1 - RES_1KM * (np.arange(ny) + 0.5), 6)
    return lats, lons, (round(float(x0), 6), round(float(y1), 6))
