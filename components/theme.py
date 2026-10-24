"""Tokens de diseño compartidos por Streamlit (CSS), Plotly y Folium.

Mantener sincronizado con `.streamlit/config.toml`.
"""

from dataclasses import dataclass
from html import escape

import branca.colormap as bcm
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio

# =========================================================================
# Tokens de color
# =========================================================================
COLORS = {
    "page": "#f9f9f7",
    "surface": "#fcfcfb",
    "surface_alt": "#f4f3ef",
    "ink": "#0b0b0b",
    "ink_2": "#52514e",
    "muted": "#898781",
    "grid": "#e1e0d9",
    "axis": "#c3c2b7",
    "border": "rgba(11,11,11,0.10)",
    "accent": "#2a78d6",
    "accent_dark": "#1c5cab",
    "accent_wash": "rgba(42,120,214,0.10)",
    "highlight": "#eb6834",
}

FONT_STACK = "Inter, system-ui, -apple-system, 'Segoe UI', sans-serif"
FONT_URL = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"

# Mapa base único para toda la aplicación: OpenStreetMap estándar (calles, vías y edificios).
# Endpoint sin subdominios {s}: OSM los declaró obsoletos.
TILES_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
TILES_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
MAP_HEIGHT = 640

# Opacidades calibradas para que la trama urbana se lea bajo los datos
RASTER_OPACITY = 0.38
BARRIO_LINE = {"color": "#1f2937", "weight": 1.1, "opacity": 0.75}


# =========================================================================
# Especificación de variables
# =========================================================================
@dataclass(frozen=True)
class VarSpec:
    label: str
    unidad: str
    agregacion: str
    cmap: str
    forma: str = "linea"  # "linea" | "barra"
    decimales: int = 1

    def fmt(self, v) -> str:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return "—"
        return f"{v:,.{self.decimales}f} {self.unidad}".strip()


VARIABLES = {
    "Precipitacion": VarSpec("Precipitación", "mm", "acumulado semanal", "Blues_09", "barra"),
    "Tmin": VarSpec("Temperatura mínima", "°C", "media semanal", "YlOrRd_09"),
    "Tmax": VarSpec("Temperatura máxima", "°C", "media semanal", "YlOrRd_09"),
    "Humedad relativa": VarSpec("Humedad relativa", "%", "media semanal", "viridis"),
    "Velocidad del viento": VarSpec("Velocidad del viento", "m/s", "media semanal", "PuBu_09"),
    "Radiación solar": VarSpec("Radiación solar", "W/m²", "media semanal", "plasma"),
}

RASTER_VARS = {
    "rh": VarSpec("Humedad relativa", "%", "diaria", "viridis"),
    "t": VarSpec("Temperatura máxima", "°C", "diaria", "YlOrRd_09"),
    "p": VarSpec("Precipitación", "mm", "diaria", "Blues_09", "barra", 2),
    # Índices adimensionales (−1 a 1)
    "ndvi": VarSpec("NDVI", "", "diario", "YlGn_09", decimales=2),
    "ndwi": VarSpec("NDWI", "", "diario", "GnBu_09", decimales=2),
}


# =========================================================================
# Escalas de color (percentiles) y leyendas sincronizadas
# =========================================================================
def escala_robusta(values, low: float = 2, high: float = 98, desde_cero: bool = False):
    """Límites de color por percentiles para que los extremos no saturen la paleta."""
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return 0.0, 1.0
    vmin = 0.0 if desde_cero else float(np.percentile(arr, low))
    vmax = float(np.percentile(arr, high))
    if vmax - vmin < 1e-6:
        vmax = vmin + 1.0
    return round(vmin, 2), round(vmax, 2)


def colormap(nombre: str, vmin: float, vmax: float) -> bcm.LinearColormap:
    """Colormap continuo de branca; los valores fuera de rango se recortan a los extremos."""
    return getattr(bcm.linear, nombre).scale(vmin, vmax)


def gradiente_css(cm: bcm.LinearColormap, pasos: int = 12) -> str:
    """Degradado CSS muestreado del mismo colormap que pinta los datos."""
    stops = [cm.rgb_hex_str(v) for v in np.linspace(cm.vmin, cm.vmax, pasos)]
    return f"linear-gradient(to right, {', '.join(stops)})"


def leyenda_html(cm: bcm.LinearColormap, spec: VarSpec, titulo: str | None = None, ticks: int = 5,
                 opacidad: float = 1.0) -> str:
    """Leyenda continua: degradado y marcas generados desde el colormap real (misma opacidad que la capa)."""
    unidad = f" <span>({escape(spec.unidad)})</span>" if spec.unidad else ""
    valores = np.linspace(cm.vmin, cm.vmax, ticks)
    rango = cm.vmax - cm.vmin
    dec = 0 if rango >= 20 else 1 if rango >= 2 else 2
    etiquetas = []
    for k, v in enumerate(valores):
        txt = f"{v:,.{dec}f}"
        if k == 0 and cm.vmin > 0:
            txt = f"≤{txt}"
        if k == ticks - 1:
            txt = f"≥{txt}"
        etiquetas.append(f"<span>{txt}</span>")
    return f"""
    <div class="gc-legend">
        <div class="gc-legend-title">{escape(titulo or spec.label)}{unidad}</div>
        <div class="gc-legend-bar" style="background: {gradiente_css(cm)}; opacity: {opacidad};"></div>
        <div class="gc-legend-ticks">{''.join(etiquetas)}</div>
        <div class="gc-legend-note">Escala p2–p98 · extremos recortados</div>
    </div>"""


# =========================================================================
# Plantilla Plotly coordinada con el tema
# =========================================================================
def _registrar_plantilla():
    tpl = go.layout.Template(pio.templates["plotly_white"])
    tpl.layout.update(
        font=dict(family=FONT_STACK, size=12, color=COLORS["ink_2"]),
        title=dict(font=dict(size=14, color=COLORS["ink"])),
        paper_bgcolor=COLORS["page"],
        plot_bgcolor=COLORS["page"],
        colorway=["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
        margin=dict(l=8, r=8, t=8, b=8),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor=COLORS["surface"],
            bordercolor=COLORS["grid"],
            font=dict(family=FONT_STACK, size=12, color=COLORS["ink"]),
        ),
        xaxis=dict(
            showgrid=False,
            linecolor=COLORS["axis"],
            ticks="outside",
            tickcolor=COLORS["axis"],
            tickfont=dict(color=COLORS["muted"]),
            title=dict(font=dict(color=COLORS["ink_2"])),
            showspikes=True,
            spikecolor=COLORS["axis"],
            spikethickness=1,
            spikedash="solid",
            spikemode="across",
        ),
        yaxis=dict(
            gridcolor=COLORS["grid"],
            gridwidth=1,
            zeroline=False,
            linecolor="rgba(0,0,0,0)",
            tickfont=dict(color=COLORS["muted"]),
            title=dict(font=dict(color=COLORS["ink_2"])),
        ),
        legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, font=dict(color=COLORS["ink_2"])),
        barcornerradius=3,
    )
    pio.templates["geoclima"] = tpl
    pio.templates.default = "geoclima"


_registrar_plantilla()

PLOTLY_CONFIG = {
    "displaylogo": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d", "toggleSpikelines"],
}
