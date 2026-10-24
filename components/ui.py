from html import escape
from pathlib import Path

import streamlit as st

from components.theme import COLORS

_BADGE_TONES = {
    "blue": ("#eef4fc", "#1c5cab", "#cde2fb"),
    "violet": ("#f3f1fd", "#4a3aa7", "#dcd7f7"),
    "green": ("#eef7ee", "#006300", "#cfe8cf"),
    "gray": ("#f4f3ef", "#52514e", "#e1e0d9"),
}


def apply_custom_css():
    """Capa CSS mínima sobre el tema nativo (.streamlit/config.toml)."""
    c = COLORS
    css = f"""
    <style>
    [data-testid="stMainBlockContainer"] {{
        padding-top: 4rem;  /* debajo de la barra superior de Streamlit Cloud (Fork, GitHub) */
        padding-bottom: 3rem;
        max-width: 1480px;
    }}

    /* Encabezado de página */
    .gc-header {{
        display: flex; align-items: flex-end; justify-content: space-between; gap: 24px;
        padding-bottom: 18px; margin-bottom: 8px; border-bottom: 1px solid {c["grid"]};
    }}
    .gc-eyebrow {{
        font-size: 11px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase;
        color: {c["accent"]}; margin-bottom: 6px;
    }}
    .gc-title {{
        font-size: 28px; font-weight: 700; letter-spacing: -0.02em; line-height: 1.15;
        color: {c["ink"]}; margin: 0;
    }}
    .gc-subtitle {{ font-size: 14px; color: {c["ink_2"]}; margin: 6px 0 0 0; max-width: 760px; }}
    .gc-badges {{ display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }}

    /* Insignias */
    .gc-badge {{
        display: inline-flex; align-items: center; gap: 6px; white-space: nowrap;
        padding: 3px 10px; border-radius: 999px; font-size: 11.5px; font-weight: 500;
        border: 1px solid var(--gc-b); background: var(--gc-bg); color: var(--gc-fg);
    }}
    .gc-badge b {{ font-weight: 600; }}

    /* Títulos de sección */
    .gc-section {{ margin: 22px 0 6px 0; }}
    .gc-section h3 {{
        font-size: 15px; font-weight: 600; color: {c["ink"]}; margin: 0; padding: 0;
        letter-spacing: -0.005em;
    }}
    .gc-section p {{ font-size: 12.5px; color: {c["muted"]}; margin: 2px 0 0 0; }}

    /* Tarjetas de métricas (st.metric con borde) */
    [data-testid="stMetric"] {{
        background: {c["surface"]};
        box-shadow: 0 1px 2px rgba(11,11,11,0.04);
        transition: box-shadow .18s ease, transform .18s ease, border-color .18s ease;
    }}
    [data-testid="stMetric"]:hover {{
        box-shadow: 0 6px 18px rgba(11,11,11,0.07);
        transform: translateY(-1px);
    }}
    [data-testid="stMetricLabel"] p {{
        font-size: 12px; font-weight: 500; color: {c["ink_2"]};
    }}

    /* Mapas y gráficos dentro de tarjeta */
    .gc-frame-note {{ font-size: 12px; color: {c["muted"]}; margin-top: 4px; }}

    /* Leyenda continua (fuera de mapas) */
    .gc-legend {{ max-width: 360px; margin-top: 6px; }}
    .gc-legend-title {{ font-size: 12px; font-weight: 600; color: {c["ink"]}; margin-bottom: 5px; }}
    .gc-legend-title span {{ font-weight: 400; color: {c["muted"]}; }}
    .gc-legend-bar {{ height: 10px; border-radius: 3px; }}
    .gc-legend-ticks {{
        display: flex; justify-content: space-between; font-size: 10.5px; color: {c["ink_2"]};
        margin-top: 3px; font-variant-numeric: tabular-nums;
    }}
    .gc-legend-note {{ font-size: 10px; color: {c["muted"]}; margin-top: 2px; }}

    /* Resumen de la grilla de 1 km */
    .gc-grid-summary {{
        border: 1px solid {c["grid"]}; border-radius: 10px; background: {c["surface"]};
        padding: 10px 14px; margin-top: 10px; font-size: 12.5px;
    }}
    .gc-grid-summary .gc-readout-row {{
        display: flex; justify-content: space-between; gap: 12px; padding: 3px 0;
        border-bottom: 1px solid {c["surface_alt"]};
    }}
    .gc-grid-summary .gc-readout-row:last-child {{ border-bottom: 0; }}
    .gc-grid-summary .gc-readout-row span:first-child {{ color: {c["ink_2"]}; }}
    .gc-grid-summary .gc-readout-row span:last-child {{
        font-weight: 600; color: {c["ink"]}; text-align: right; font-variant-numeric: tabular-nums;
    }}

    /* Estado vacío */
    .gc-empty {{
        border: 1px dashed {c["axis"]}; border-radius: 12px; padding: 36px 24px;
        text-align: center; background: {c["surface"]};
    }}
    .gc-empty .gc-empty-title {{ font-weight: 600; color: {c["ink"]}; font-size: 15px; }}
    .gc-empty .gc-empty-body {{ color: {c["ink_2"]}; font-size: 13px; margin-top: 4px; }}

    /* Barra lateral */
    .gc-side-label {{
        font-size: 10.5px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase;
        color: {c["muted"]}; margin: 14px 0 6px 0;
    }}
    .gc-side-grid {{ display: flex; flex-wrap: wrap; gap: 6px; }}
    .gc-side-meta {{ font-size: 12px; color: {c["ink_2"]}; line-height: 1.55; }}
    .gc-side-meta code {{ font-size: 11px; background: {c["surface_alt"]}; padding: 1px 5px; border-radius: 4px; }}

    /* Footer */
    .gc-footer {{
        margin-top: 4px; padding-top: 14px;
        display: flex; justify-content: space-between; color: {c["muted"]}; font-size: 12px;
    }}

    /* Franja institucional compacta en la parte superior */
    .st-key-gc_topbar {{ margin-bottom: -4px; }}
    @media (max-width: 640px) {{ .st-key-gc_topbar {{ display: none; }} }}  /* en móvil queda en el footer */

    /* Franja institucional (aliados y financiador) */
    .st-key-gc_aliados {{
        margin-top: 48px; background: #ffffff; padding: 18px 24px 14px;
    }}
    .gc-aliados-label {{
        font-size: 10.5px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase;
        color: {c["muted"]}; text-align: center;
    }}
    </style>
    """
    st.html(css)


def badge_html(text: str, tone: str = "gray", strong: str | None = None) -> str:
    bg, fg, border = _BADGE_TONES.get(tone, _BADGE_TONES["gray"])
    label = f"{escape(text)} <b>{escape(strong)}</b>" if strong else escape(text)
    return f'<span class="gc-badge" style="--gc-bg:{bg};--gc-fg:{fg};--gc-b:{border};">{label}</span>'


def render_header(title: str, subtitle: str, eyebrow: str | None = None, badges: list[tuple] | None = None):
    """Encabezado de página: antetítulo, título, descripción e insignias de contexto."""
    eyebrow_html = f'<div class="gc-eyebrow">{escape(eyebrow)}</div>' if eyebrow else ""
    badges_html = "".join(badge_html(*b) for b in (badges or []))
    st.html(
        f"""
        <div class="gc-header">
            <div>
                {eyebrow_html}
                <h1 class="gc-title">{escape(title)}</h1>
                <p class="gc-subtitle">{escape(subtitle)}</p>
            </div>
            <div class="gc-badges">{badges_html}</div>
        </div>
        """
    )


def section_title(title: str, caption: str | None = None):
    cap = f"<p>{escape(caption)}</p>" if caption else ""
    st.html(f'<div class="gc-section"><h3>{escape(title)}</h3>{cap}</div>')


def metric_card(
    label: str,
    value: str,
    *,
    delta=None,
    delta_description: str | None = None,
    delta_color: str = "off",
    neutral_delta: bool = False,
    chart=None,
    chart_type: str = "line",
    help: str | None = None,
):
    """Tarjeta KPI nativa con micro-gráfico opcional y contexto comparativo."""
    st.metric(
        label,
        value,
        delta=delta,
        delta_color=delta_color,
        delta_arrow="off" if neutral_delta else "auto",
        delta_description=delta_description,
        chart_data=chart,
        chart_type=chart_type,
        border=True,
        help=help,
        height=156,  # altura uniforme con o sin micro-gráfico
    )


def tabla_resumen(filas: list[tuple[str, str]]):
    """Bloque compacto de pares etiqueta → valor (resúmenes de grillas)."""
    filas_html = "".join(
        f'<div class="gc-readout-row"><span>{escape(k)}</span><span>{escape(v)}</span></div>' for k, v in filas
    )
    st.html(f'<div class="gc-grid-summary">{filas_html}</div>')


def empty_state(title: str, body: str):
    st.html(
        f"""
        <div class="gc-empty">
            <div class="gc-empty-title">{escape(title)}</div>
            <div class="gc-empty-body">{escape(body)}</div>
        </div>
        """
    )


def sidebar_label(text: str):
    st.html(f'<div class="gc-side-label">{escape(text)}</div>')


def render_footer(aliados_png: Path | None = None):
    """Pie de página con la franja institucional del proyecto, si existe el PNG de aliados."""
    if aliados_png and aliados_png.exists():
        with st.container(border=True, key="gc_aliados", horizontal_alignment="center", gap="small"):
            st.html('<div class="gc-aliados-label">Proyecto Dengue.IA Cali · Alianza institucional</div>')
            st.image(
                str(aliados_png),
                width=900,
                caption=None,
            )
    st.html(
        """
        <div class="gc-footer">
            <span>GeoClima Cali · Análisis espaciotemporal hidrometeorológico</span>
            <span>Santiago de Cali, Colombia</span>
        </div>
        """
    )
