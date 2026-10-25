import numpy as np
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from geoclima.ui.i18n import t
from geoclima.ui.tema import COLORS, PLOTLY_CONFIG, SERIE_COLORES, VarSpec, colormap


def serie_temporal(
    x,
    y,
    spec: VarSpec,
    *,
    height: int = 320,
    referencia: float | None = None,
    ref_label: str | None = None,
    selector_rango: bool = False,
    fmt_fecha: str = "%Y-%m-%d",
) -> go.Figure:
    """Serie de una sola variable: barras para acumulados, línea fina para estados."""
    ref_label = ref_label or t("graf.media")
    hover = f"%{{y:,.{spec.decimales}f}} {spec.unidad}<extra>{spec.label}</extra>"
    fig = go.Figure()
    if spec.forma == "barra":
        fig.add_trace(go.Bar(
            x=x, y=y, name=spec.label, marker=dict(color=COLORS["accent"], line=dict(width=0)),
            hovertemplate=hover,
        ))
        fig.update_layout(bargap=0.18)
    else:
        corta = len(x) <= 45
        fig.add_trace(go.Scatter(
            x=x, y=y, name=spec.label,
            mode="lines+markers" if corta else "lines",
            line=dict(color=COLORS["accent"], width=2, shape="linear"),
            marker=dict(size=8, color=COLORS["accent"], line=dict(width=2, color=COLORS["surface"])),
            connectgaps=False,
            hovertemplate=hover,
        ))

    if referencia is not None:
        fig.add_hline(
            y=referencia,
            line=dict(color=COLORS["muted"], width=1),
            annotation_text=f"{ref_label} · {spec.fmt(referencia)}",
            annotation_position="top right",
            annotation_font=dict(size=11, color=COLORS["ink_2"]),
            annotation_bgcolor=COLORS["page"],
        )

    fig.update_layout(
        height=height,
        showlegend=False,
        # Explícitos en el layout: Streamlit reemplaza los fondos que solo vienen de la plantilla
        plot_bgcolor=COLORS["page"],
        paper_bgcolor=COLORS["page"],
        xaxis=dict(hoverformat=fmt_fecha),
        yaxis=dict(title=dict(text=spec.unidad or spec.label, standoff=6), rangemode="tozero" if spec.forma == "barra" else "normal"),
    )
    if selector_rango:
        fig.update_xaxes(
            rangeselector=dict(
                buttons=[
                    dict(count=6, label=t("graf.r_6m"), step="month", stepmode="backward"),
                    dict(count=1, label=t("graf.r_1a"), step="year", stepmode="backward"),
                    dict(count=3, label=t("graf.r_3a"), step="year", stepmode="backward"),
                    dict(step="all", label=t("graf.r_todo")),
                ],
                x=0, y=1.02, xanchor="left", yanchor="bottom",
                bgcolor=COLORS["surface_alt"], activecolor=COLORS["grid"],
                bordercolor=COLORS["grid"], borderwidth=1,
                font=dict(size=11, color=COLORS["ink_2"]),
            )
        )
        fig.update_layout(margin=dict(t=40))
    return fig


def mostrar(fig: go.Figure, key: str | None = None):
    # theme=None: se usa la plantilla "geoclima" en lugar de la de Streamlit
    st.plotly_chart(fig, theme=None, config=PLOTLY_CONFIG, key=key)


def series_multiples(x, series: dict, spec: VarSpec, *, height: int = 320, forma: str = "linea") -> go.Figure:
    """Varias series de la misma variable (misma unidad, un solo eje), con leyenda."""
    fig = go.Figure()
    # Máximo tres series: es el límite validado de la paleta categórica
    items = list(series.items())[:3]
    for (nombre, y), color in zip(items, SERIE_COLORES[: len(items)], strict=True):
        hover = f"%{{y:,.{spec.decimales}f}} {spec.unidad}<extra>{nombre}</extra>"
        if forma == "barra":
            fig.add_trace(go.Bar(x=x, y=y, name=nombre, marker=dict(color=color, line=dict(width=0)),
                                 hovertemplate=hover))
        else:
            fig.add_trace(go.Scatter(
                x=x, y=y, name=nombre, mode="lines+markers", connectgaps=False,
                line=dict(color=color, width=2),
                marker=dict(size=7, color=color, line=dict(width=2, color=COLORS["page"])),
                hovertemplate=hover,
            ))
    fig.update_layout(
        height=height, showlegend=True, bargap=0.25, bargroupgap=0.08,
        plot_bgcolor=COLORS["page"], paper_bgcolor=COLORS["page"],
        margin=dict(l=8, r=8, t=36, b=8),
        xaxis=dict(hoverformat="%Y-%m-%d"),
        yaxis=dict(title=dict(text=spec.unidad or spec.label, standoff=6),
                   rangemode="tozero" if spec.forma == "barra" else "normal"),
    )
    return fig


def serie_vs_ciudad(x, barrios: dict, y_ciudad, spec: VarSpec, *, height: int = 240) -> go.Figure:
    """Series de uno a tres barrios (paleta categórica) frente al promedio de la ciudad (gris).

    Las series con muchos huecos (p. ej. días nublados en MODIS) se unen con línea punteada para que
    se lea la tendencia; los puntos marcan los días con dato real.
    """
    hover = f"%{{y:,.{spec.decimales}f}} {spec.unidad}"
    y_ciudad = np.asarray(y_ciudad, float)
    dispersa = bool(np.isfinite(y_ciudad).mean() < 0.6)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=y_ciudad, name=t("graf.promedio_cali"), mode="lines+markers" if dispersa else "lines",
        connectgaps=dispersa, line=dict(color=COLORS["axis"], width=2, dash="dot" if dispersa else "solid"),
        marker=dict(size=5, color=COLORS["axis"]), hovertemplate=hover + "<extra>Cali</extra>",
    ))
    for (nombre, y), color in zip(list(barrios.items())[:3], SERIE_COLORES, strict=False):
        fig.add_trace(go.Scatter(
            x=x, y=y, name=nombre, mode="lines+markers", connectgaps=dispersa,
            line=dict(color=color, width=2, dash="dot" if dispersa else "solid"),
            marker=dict(size=6, color=color, line=dict(width=1.5, color=COLORS["page"])),
            hovertemplate=hover + f"<extra>{nombre}</extra>",
        ))
    fig.update_layout(
        height=height, showlegend=True,
        plot_bgcolor=COLORS["page"], paper_bgcolor=COLORS["page"],
        margin=dict(l=8, r=8, t=30, b=8),
        legend=dict(orientation="h", y=1.04, yanchor="bottom", x=0, font=dict(size=11)),
        xaxis=dict(hoverformat="%Y-%m-%d", tickformat="%d %b"),
        yaxis=dict(title=dict(text=spec.unidad or spec.label, standoff=4)),
    )
    return fig


def barras_h(categorias, valores, *, sufijo: str = "", height: int = 220, destacar: str | None = None,
             rango: tuple | None = None, decimales: int = 0, colores: list | None = None) -> go.Figure:
    """Barras horizontales de una sola serie con el valor en la punta."""
    if colores is None:
        colores = [COLORS["accent"] if (destacar is None or c == destacar) else "#9ec5f4" for c in categorias]
    fig = go.Figure(go.Bar(
        x=valores, y=categorias, orientation="h",
        marker=dict(color=colores, line=dict(width=0)),
        text=[f"{v:,.{decimales}f}{sufijo}" for v in valores], textposition="outside", cliponaxis=False,
        textfont=dict(color=COLORS["ink_2"], size=12),
        hovertemplate="%{y}: %{x:,." + str(decimales) + "f}" + sufijo + "<extra></extra>",
    ))
    fig.update_layout(
        height=height, showlegend=False, bargap=0.35, hovermode="closest",
        plot_bgcolor=COLORS["page"], paper_bgcolor=COLORS["page"],
        margin=dict(l=8, r=40, t=8, b=8),
        xaxis=dict(showgrid=True, gridcolor=COLORS["grid"], zeroline=False, showspikes=False,
                   range=list(rango) if rango else None, ticks=""),
        yaxis=dict(autorange="reversed", showgrid=False, tickfont=dict(color=COLORS["ink"], size=12)),
    )
    return fig


def barras_comunas(comunas, valores, spec: VarSpec, *, unidad: str, destacar: str | None = None,
                   referencia: float | None = None) -> go.Figure:
    """Promedio por comuna (de mayor a menor), coloreado con la misma escala del mapa."""
    vals = np.asarray(valores, float)
    orden = np.argsort(-np.nan_to_num(vals, nan=-np.inf))
    comunas, vals = [comunas[i] for i in orden], vals[orden]
    cm = colormap(spec.cmap, float(np.nanmin(vals)), float(np.nanmax(vals)) + 1e-9)
    colores = [cm.rgb_hex_str(v) if np.isfinite(v) else COLORS["grid"] for v in vals]
    if destacar in comunas:
        colores = [c if com == destacar else c + "66" for c, com in zip(colores, comunas, strict=True)]
    dec = max(spec.decimales, 1) if unidad else 3
    fig = barras_h(comunas, vals, sufijo=f" {unidad}" if unidad else "", height=40 + 21 * len(comunas),
                   decimales=dec, colores=colores)
    fig.update_traces(marker_line=dict(width=0.5, color=COLORS["axis"]))
    lo, hi = float(np.nanmin(vals)), float(np.nanmax(vals))
    pad = (hi - lo) * 0.25 or abs(hi) * 0.1 or 1
    fig.update_layout(bargap=0.22, xaxis=dict(range=[max(lo - pad, 0) if lo >= 0 else lo - pad, hi + pad]),
                      yaxis=dict(tickfont=dict(size=11.5)), margin=dict(l=8, r=56, t=8, b=8))
    if referencia is not None and np.isfinite(referencia):
        fig.add_vline(x=referencia, line=dict(color=COLORS["ink_2"], width=1, dash="dot"),
                      annotation_text="Cali", annotation_position="top",
                      annotation_font=dict(size=10.5, color=COLORS["ink_2"]))
    return fig


def posicion_barrio(filas: list[dict], *, alto_fila: int = 92) -> go.Figure:
    """Distribución de los barrios por indicador (puntos grises) con el barrio elegido y los comparados.

    filas: [{"titulo", "valores" (todos los barrios), "marcas": [(nombre, valor, color)], "media", "fmt"}]
    """
    n = len(filas)
    alto = alto_fila * n + 30
    # Separación fija en píxeles (marcas del eje + título de la fila siguiente), expresada como fracción
    fig = make_subplots(rows=n, cols=1, vertical_spacing=min(0.3, 50 / alto) if n > 1 else 0,
                        subplot_titles=[f["titulo"] for f in filas])
    rng = np.random.default_rng(7)  # dispersión vertical fija: el gráfico no "salta" entre reruns
    for r, f in enumerate(filas, start=1):
        v = np.asarray(f["valores"], float)
        v = v[np.isfinite(v)]
        fig.add_trace(go.Scatter(
            x=v, y=rng.uniform(-0.32, 0.32, len(v)), mode="markers", showlegend=False, hoverinfo="skip",
            marker=dict(size=5, color=COLORS["axis"], opacity=0.55),
        ), row=r, col=1)
        if np.isfinite(f["media"]):
            fig.add_vline(x=f["media"], line=dict(color=COLORS["ink_2"], width=1, dash="dot"), row=r, col=1)
        for nombre, valor, color in reversed(f["marcas"]):  # el barrio principal queda encima
            if valor is None or not np.isfinite(valor):
                continue
            fig.add_trace(go.Scatter(
                x=[valor], y=[0], mode="markers", name=nombre, showlegend=False,
                marker=dict(size=15, color=color, line=dict(width=2, color=COLORS["surface"])),
                hovertemplate=f"<b>{nombre}</b><br>{f['fmt'](valor)}<extra></extra>",
            ), row=r, col=1)
        fig.update_yaxes(visible=False, range=[-0.6, 0.6], fixedrange=True, row=r, col=1)
        fig.update_xaxes(showgrid=True, gridcolor=COLORS["grid"], showspikes=False, ticks="", fixedrange=True,
                         tickfont=dict(size=10.5), row=r, col=1)
    fig.update_annotations(font=dict(size=12, color=COLORS["ink"]), x=0, xanchor="left")
    fig.update_layout(height=alto, hovermode="closest", plot_bgcolor=COLORS["page"],
                      paper_bgcolor=COLORS["page"], margin=dict(l=8, r=8, t=26, b=8))
    return fig


def climatologia_semanal(semanas, p10, p50, p90, actual, spec: VarSpec, *, etiqueta_actual: str,
                         height: int = 320) -> go.Figure:
    """Ciclo anual por semana epidemiológica: banda p10–p90 y mediana histórica, con el año elegido encima."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=semanas, y=p90, mode="lines", line=dict(width=0), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(
        x=semanas, y=p10, mode="lines", line=dict(width=0), fill="tonexty", fillcolor=COLORS["accent_wash"],
        name=t("graf.rango_habitual"), hoverinfo="skip",
    ))
    hover = f"%{{y:,.{spec.decimales}f}} {spec.unidad}"
    fig.add_trace(go.Scatter(
        x=semanas, y=p50, mode="lines", name=t("graf.mediana_hist"),
        line=dict(color=COLORS["muted"], width=1.6, dash="dot"),
        hovertemplate=hover + f"<extra>{t('graf.mediana_hist')}</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=semanas, y=actual, mode="lines+markers", name=etiqueta_actual, connectgaps=False,
        line=dict(color=COLORS["highlight"], width=2.2),
        marker=dict(size=5, color=COLORS["highlight"], line=dict(width=1, color=COLORS["page"])),
        hovertemplate=hover + f"<extra>{etiqueta_actual}</extra>",
    ))
    fig.update_layout(
        height=height, plot_bgcolor=COLORS["page"], paper_bgcolor=COLORS["page"],
        margin=dict(l=8, r=8, t=36, b=8),
        xaxis=dict(title=dict(text=t("graf.semana_epi"), standoff=6), range=[0.5, 53.5], dtick=4,
                   hoverformat="d", showspikes=True),
        yaxis=dict(title=dict(text=spec.unidad or spec.label, standoff=6),
                   rangemode="tozero" if spec.forma == "barra" else "normal"),
    )
    fig.update_layout(hovermode="x unified")
    return fig


def calendario_semanal(z, anios, semanas, spec: VarSpec, *, height: int | None = None) -> go.Figure:
    """Mapa de calor año × semana epidemiológica (celdas vacías = semana sin dato)."""
    cm_escala = {
        "Blues_09": "Blues", "YlOrRd_09": "YlOrRd", "viridis": "Viridis", "PuBu_09": "PuBu", "plasma": "Plasma",
    }.get(spec.cmap, "Blues")
    finitos = np.asarray(z, float)[np.isfinite(np.asarray(z, float))]
    zmin = 0 if spec.forma == "barra" else (float(np.percentile(finitos, 2)) if finitos.size else None)
    zmax = float(np.percentile(finitos, 98)) if finitos.size else None
    fig = go.Figure(go.Heatmap(
        z=z, x=semanas, y=[str(a) for a in anios], colorscale=cm_escala, zmin=zmin, zmax=zmax,
        xgap=1.5, ygap=1.5, hoverongaps=False,
        colorbar=dict(title=dict(text=spec.unidad, side="right"), thickness=10, len=0.9, outlinewidth=0,
                      tickfont=dict(size=10.5, color=COLORS["muted"])),
        hovertemplate=t("graf.calendario_hover") + "<br>%{z:,." + str(spec.decimales) + "f} " + spec.unidad
                      + "<extra></extra>",
    ))
    fig.update_layout(
        height=height or 60 + 24 * len(anios), plot_bgcolor=COLORS["page"], paper_bgcolor=COLORS["page"],
        hovermode="closest", margin=dict(l=8, r=8, t=8, b=8),
        xaxis=dict(title=dict(text=t("graf.semana_epi"), standoff=6), dtick=4, showspikes=False, ticks=""),
        yaxis=dict(autorange="reversed", showgrid=False, type="category", tickfont=dict(size=11)),
    )
    return fig


def cobertura_temporal(filas: list[dict], *, height: int | None = None) -> go.Figure:
    """Periodo de cada fuente como barra horizontal: deja ver si las fuentes comparan el mismo periodo.

    filas: [{"fuente", "inicio", "fin", "color", "texto"}]
    """
    fig = go.Figure()
    for f in filas:
        fig.add_trace(go.Bar(
            base=[f["inicio"]], x=[(f["fin"] - f["inicio"]).total_seconds() * 1000 + 86_400_000],
            y=[f["fuente"]], orientation="h", marker=dict(color=f["color"], line=dict(width=0)),
            text=[f["texto"]], textposition="inside", insidetextanchor="middle",
            textfont=dict(color="#ffffff", size=11.5), showlegend=False,
            hovertemplate=f"<b>{f['fuente']}</b><br>{f['texto']}<extra></extra>",
        ))
    fig.update_layout(
        height=height or 50 + 40 * len(filas), barmode="overlay", bargap=0.38, hovermode="closest",
        plot_bgcolor=COLORS["page"], paper_bgcolor=COLORS["page"], margin=dict(l=8, r=8, t=8, b=8),
        xaxis=dict(type="date", showgrid=True, gridcolor=COLORS["grid"], tickformat="%d %b", showspikes=False),
        yaxis=dict(autorange="reversed", tickfont=dict(color=COLORS["ink"], size=12)),
    )
    return fig
