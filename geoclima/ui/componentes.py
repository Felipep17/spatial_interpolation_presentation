from html import escape
from pathlib import Path

import streamlit as st

from geoclima.ui.i18n import t
from geoclima.ui.tema import COLORS

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

    /* Tarjetas de fuentes (Panorama) */
    .gc-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
    .gc-card {{
        background: {c["surface"]}; border: 1px solid {c["grid"]}; border-radius: 12px; padding: 14px 16px;
        box-shadow: 0 1px 2px rgba(11,11,11,0.04); transition: box-shadow .18s ease, transform .18s ease;
        display: flex; flex-direction: column; gap: 8px;
    }}
    .gc-card:hover {{ box-shadow: 0 6px 18px rgba(11,11,11,0.07); transform: translateY(-1px); }}
    .gc-card-top {{ display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }}
    .gc-card-name {{ font-weight: 600; font-size: 15px; color: {c["ink"]}; }}
    .gc-card-vars {{ font-size: 12px; color: {c["muted"]}; margin-top: -4px; }}
    .gc-card .gc-readout-row {{ display: flex; justify-content: space-between; gap: 10px; font-size: 12.5px; padding: 2px 0; }}
    .gc-card .gc-readout-row span:first-child {{ color: {c["ink_2"]}; }}
    .gc-card .gc-readout-row span:last-child {{ font-weight: 600; color: {c["ink"]}; font-variant-numeric: tabular-nums; text-align: right; }}
    .gc-meter-label {{ display: flex; justify-content: space-between; font-size: 11.5px; color: {c["ink_2"]}; margin-top: 4px; }}
    .gc-meter-label b {{ color: {c["ink"]}; font-weight: 600; }}
    .gc-meter {{ height: 6px; border-radius: 3px; background: #cde2fb; overflow: hidden; }}
    .gc-meter > div {{ height: 100%; background: {c["accent"]}; border-radius: 3px; }}

    /* Estado vacío */
    .gc-empty {{
        border: 1px dashed {c["axis"]}; border-radius: 12px; padding: 36px 24px;
        text-align: center; background: {c["surface"]};
    }}
    .gc-empty .gc-empty-title {{ font-weight: 600; color: {c["ink"]}; font-size: 15px; }}
    .gc-empty .gc-empty-body {{ color: {c["ink_2"]}; font-size: 13px; margin-top: 4px; }}

    /* Selector de idioma: compacto, a la derecha y en mayúsculas (la URL conserva es/en) */
    .st-key-lang {{ margin: 4px 0 2px 0; }}
    .st-key-lang [data-testid="stButtonGroup"] {{ justify-content: flex-end; }}
    .st-key-lang button {{ text-transform: uppercase; letter-spacing: .06em; font-size: 11.5px;
        min-height: 0; padding: 2px 10px; }}

    /* Barra lateral */
    .gc-side-label {{
        font-size: 10.5px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase;
        color: {c["muted"]}; margin: 14px 0 6px 0;
    }}
    .gc-side-grid {{ display: flex; flex-wrap: wrap; gap: 6px; }}
    .gc-side-meta {{ font-size: 12px; color: {c["ink_2"]}; line-height: 1.55; }}
    .gc-side-list {{ font-size: 12px; border: 1px solid {c["grid"]}; border-radius: 8px; background: {c["surface"]};
        padding: 4px 10px; }}
    .gc-side-row {{ display: flex; justify-content: space-between; gap: 8px; padding: 4px 0;
        border-bottom: 1px solid {c["surface_alt"]}; }}
    .gc-side-row:last-child {{ border-bottom: 0; }}
    .gc-side-row span:first-child {{ color: {c["ink"]}; font-weight: 500; }}
    .gc-side-row span:last-child {{ color: {c["ink_2"]}; font-variant-numeric: tabular-nums; }}
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

    /* Ranking de barrios (más altos / más bajos) */
    .gc-rank {{ border: 1px solid {c["grid"]}; border-radius: 10px; background: {c["surface"]}; padding: 10px 12px; }}
    .gc-rank-title {{ font-size: 11px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase;
        color: {c["muted"]}; margin-bottom: 6px; }}
    .gc-rank-row {{ display: grid; grid-template-columns: 26px 1fr auto; align-items: center; gap: 8px;
        padding: 4px 0; font-size: 12.5px; border-bottom: 1px solid {c["surface_alt"]}; }}
    .gc-rank-row:last-child {{ border-bottom: 0; }}
    .gc-rank-pos {{ color: {c["muted"]}; font-variant-numeric: tabular-nums; font-size: 11.5px; }}
    .gc-rank-name {{ color: {c["ink"]}; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .gc-rank-name small {{ display: block; color: {c["muted"]}; font-size: 10.5px; }}
    .gc-rank-val {{ font-weight: 600; color: {c["ink"]}; font-variant-numeric: tabular-nums; text-align: right; }}
    .gc-rank-bar {{ grid-column: 2 / 4; height: 4px; border-radius: 2px; background: {c["surface_alt"]};
        margin-top: -2px; overflow: hidden; }}
    .gc-rank-bar > div {{ height: 100%; border-radius: 2px; }}

    /* Ficha del barrio elegido en un mapa */
    .gc-pick {{ border: 1px solid {c["grid"]}; border-left: 3px solid {c["accent"]}; border-radius: 10px;
        background: {c["surface"]}; padding: 10px 14px; }}
    .gc-pick-name {{ font-size: 16px; font-weight: 700; color: {c["ink"]}; letter-spacing: -.01em; }}
    .gc-pick-sub {{ font-size: 12px; color: {c["muted"]}; margin-bottom: 6px; }}
    .gc-pick-val {{ font-size: 22px; font-weight: 700; color: {c["ink"]}; font-variant-numeric: tabular-nums; }}
    .gc-pick-meta {{ font-size: 12px; color: {c["ink_2"]}; }}

    /* Accesos a módulos (Panorama) */
    [class*="st-key-gc_nav_"] {{
        background: {c["surface"]}; transition: box-shadow .18s ease, transform .18s ease;
    }}
    [class*="st-key-gc_nav_"]:hover {{ box-shadow: 0 6px 18px rgba(11,11,11,0.07); transform: translateY(-1px); }}
    .gc-nav-desc {{ font-size: 12.5px; color: {c["ink_2"]}; margin: -6px 0 0 0; line-height: 1.45; }}

    /* Línea de tiempo de cobertura */
    .gc-legend-inline {{ display: flex; flex-wrap: wrap; gap: 12px; font-size: 12px; color: {c["ink_2"]}; }}
    .gc-legend-inline i {{ display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 5px;
        vertical-align: -1px; }}

    /* ===================== Móvil (≤ 640 px): el escritorio no cambia ===================== */
    @media (max-width: 640px) {{
        [data-testid="stMainBlockContainer"] {{
            padding-top: 3.5rem; padding-left: 1rem; padding-right: 1rem; padding-bottom: 2rem;
        }}
        /* Encabezado: título arriba, insignias debajo */
        .gc-header {{ flex-direction: column; align-items: flex-start; gap: 10px; padding-bottom: 14px; }}
        .gc-title {{ font-size: 22px; }}
        .gc-subtitle {{ font-size: 13px; }}
        .gc-badges {{ justify-content: flex-start; }}
        .gc-section {{ margin-top: 16px; }}

        /* Tarjetas KPI: altura según contenido en vez de fija */
        [data-testid="stMetric"],
        [data-testid="stElementContainer"]:has(> [data-testid="stMetric"]) {{
            height: auto !important; min-height: 0 !important;
        }}
        [data-testid="stMetric"]:hover {{ transform: none; }}
        /* Filas de KPIs: cuadrícula 2 × 2 en lugar de una tarjeta por fila */
        [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) {{
            flex-direction: row !important; flex-wrap: wrap !important; gap: 8px !important;
        }}
        [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="stColumn"] {{
            flex: 1 1 calc(50% - 4px) !important; width: calc(50% - 4px) !important;
            min-width: calc(50% - 4px) !important;
        }}
        [data-testid="stMetric"] {{ padding: 10px 12px !important; }}
        [data-testid="stMetricValue"] {{ font-size: 1.25rem !important; }}
        [data-testid="stMetricLabel"] p {{ font-size: 11px !important; white-space: normal !important; }}
        [data-testid="stMetricLabel"] *, [data-testid="stMetricDelta"] * {{
            white-space: normal !important; overflow: visible !important; text-overflow: clip !important;
        }}
        /* La barra de herramientas de Plotly tapa la leyenda en pantallas táctiles */
        .modebar-container {{ display: none !important; }}

        /* Selectores segmentados (fuentes, variables): pasan a varias líneas */
        [data-testid="stButtonGroup"], [data-testid="stButtonGroup"] > div {{
            flex-wrap: wrap !important; max-width: 100%;
        }}

        /* Resúmenes etiqueta → valor: el valor baja si no cabe */
        .gc-grid-summary {{ padding: 8px 10px; }}
        .gc-grid-summary .gc-readout-row {{ flex-wrap: wrap; gap: 2px 12px; }}
        .gc-grid-summary .gc-readout-row span:last-child {{ text-align: left; }}

        .gc-legend {{ max-width: 100%; }}
        .st-key-gc_aliados {{ padding: 12px; margin-top: 32px; }}
        .gc-footer {{ flex-direction: column; gap: 4px; }}
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
    height: int | str = 156,
):
    """Tarjeta KPI nativa con micro-gráfico opcional y contexto comparativo.

    height: 156 px por defecto (altura uniforme con o sin micro-gráfico); "content" para filas sin gráficos.
    """
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
        height=height,
    )


def tabla_resumen(filas: list[tuple[str, str]]):
    """Bloque compacto de pares etiqueta → valor (resúmenes de grillas)."""
    filas_html = "".join(
        f'<div class="gc-readout-row"><span>{escape(k)}</span><span>{escape(v)}</span></div>' for k, v in filas
    )
    st.html(f'<div class="gc-grid-summary">{filas_html}</div>')


def boton_descarga(df, nombre: str, key: str, geojson: bytes | None = None):
    """Descarga CSV de una tabla (sin columnas de mini-gráficos). UTF-8 con BOM para Excel.

    Si se pasa `geojson`, añade al lado la descarga de la capa vectorial (para QGIS/ArcGIS).
    """
    columnas = [c for c in df.columns
                if c != "geometry" and not df[c].map(lambda v: isinstance(v, (list, tuple))).any()]
    with st.container(horizontal=True, gap="small"):
        st.download_button(
            t("dl.csv"),
            df[columnas].to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{nombre}.csv",
            mime="text/csv",
            icon=":material/download:",
            type="tertiary",
            key=key,
        )
        if geojson is not None:
            st.download_button(
                t("dl.geojson"),
                geojson,
                file_name=f"{nombre}.geojson",
                mime="application/geo+json",
                icon=":material/map:",
                type="tertiary",
                key=f"{key}_geo",
                help=t("dl.geojson_ayuda"),
            )


def lista_ranking(titulo: str, filas: list[dict], color: str):
    """Lista compacta de barrios: puesto, nombre (y comuna), valor y barra proporcional (0–1)."""
    html = []
    for f in filas:
        frac = max(0.02, min(1.0, float(f.get("frac", 0))))
        sub = f'<small>{escape(f["sub"])}</small>' if f.get("sub") else ""
        html.append(
            f'<div class="gc-rank-row"><span class="gc-rank-pos">{f["puesto"]}</span>'
            f'<span class="gc-rank-name" title="{escape(f["nombre"])}">{escape(f["nombre"])}{sub}</span>'
            f'<span class="gc-rank-val">{escape(f["valor"])}</span>'
            f'<div class="gc-rank-bar"><div style="width:{100 * frac:.0f}%;background:{color}"></div></div></div>'
        )
    st.html(f'<div class="gc-rank"><div class="gc-rank-title">{escape(titulo)}</div>{"".join(html)}</div>')


def ficha_seleccion(nombre: str, sub: str, valor: str, meta: str):
    """Tarjeta del barrio elegido en un mapa."""
    st.html(
        f'<div class="gc-pick"><div class="gc-pick-name">{escape(nombre)}</div>'
        f'<div class="gc-pick-sub">{escape(sub)}</div><div class="gc-pick-val">{escape(valor)}</div>'
        f'<div class="gc-pick-meta">{escape(meta)}</div></div>'
    )


def pista(texto: str, icono: str = "touch_app"):
    """Indicación breve de interacción (por ejemplo, «haga clic en un barrio»)."""
    st.caption(f":material/{icono}: {texto}")


def tarjetas_fuentes(tarjetas: list[dict]):
    """Rejilla de tarjetas resumen. Cada tarjeta: nombre, etiqueta, variables, filas [(k, v)], medidor (0-100)."""
    html = []
    for tarjeta in tarjetas:
        filas = "".join(
            f'<div class="gc-readout-row"><span>{escape(k)}</span><span>{escape(v)}</span></div>' for k, v in tarjeta["filas"]
        )
        medidor = ""
        if tarjeta.get("medidor") is not None:
            pct = max(0.0, min(100.0, float(tarjeta["medidor"])))
            medidor = (
                f'<div class="gc-meter-label"><span>{escape(tarjeta.get("medidor_label", ""))}</span><b>{pct:.0f} %</b></div>'
                f'<div class="gc-meter" role="meter" aria-valuenow="{pct:.0f}" aria-valuemin="0" aria-valuemax="100">'
                f'<div style="width:{pct:.1f}%"></div></div>'
            )
        etiqueta = badge_html(tarjeta["etiqueta"], tarjeta.get("tono", "blue")) if tarjeta.get("etiqueta") else ""
        html.append(
            f'<div class="gc-card"><div class="gc-card-top"><span class="gc-card-name">{escape(tarjeta["nombre"])}</span>'
            f'{etiqueta}</div><div class="gc-card-vars">{escape(tarjeta.get("variables", ""))}</div>{filas}{medidor}</div>'
        )
    st.html(f'<div class="gc-cards">{"".join(html)}</div>')


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


@st.cache_resource
def _logo_recortado(ruta: Path, mtime: float):
    """Recorta el margen transparente del PNG para que los logos se vean más grandes."""
    from PIL import Image

    img = Image.open(ruta)
    return img.crop(img.getchannel("A").getbbox()) if img.mode == "RGBA" else img


def franja_aliados(aliados_png: Path):
    """Franja institucional compacta arriba a la derecha (en móvil solo se muestra en el pie)."""
    if aliados_png.exists():
        with st.container(horizontal=True, horizontal_alignment="right", key="gc_topbar"):
            st.image(_logo_recortado(aliados_png, aliados_png.stat().st_mtime), width=440)


def render_footer(aliados_png: Path | None = None):
    """Pie de página con la franja institucional del proyecto, si existe el PNG de aliados."""
    if aliados_png and aliados_png.exists():
        with st.container(border=True, key="gc_aliados", horizontal_alignment="center", gap="small"):
            st.html(f'<div class="gc-aliados-label">{escape(t("pie.aliados"))}</div>')
            st.image(
                str(aliados_png),
                width=900,
                caption=None,
            )
    st.html(
        f"""
        <div class="gc-footer">
            <span>{escape(t("pie.app"))}</span>
            <span>{escape(t("pie.lugar"))}</span>
        </div>
        """
    )
