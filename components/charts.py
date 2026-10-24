import plotly.graph_objects as go
import streamlit as st

from components.theme import COLORS, PLOTLY_CONFIG, VarSpec


def serie_temporal(
    x,
    y,
    spec: VarSpec,
    *,
    height: int = 320,
    referencia: float | None = None,
    ref_label: str = "Media",
    selector_rango: bool = False,
    fmt_fecha: str = "%Y-%m-%d",
) -> go.Figure:
    """Serie de una sola variable: barras para acumulados, línea fina para estados."""
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
                    dict(count=6, label="6M", step="month", stepmode="backward"),
                    dict(count=1, label="1A", step="year", stepmode="backward"),
                    dict(count=3, label="3A", step="year", stepmode="backward"),
                    dict(step="all", label="Todo"),
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


SERIE_COLORES = ["#2a78d6", "#eb6834", "#1baf7a"]  # orden categórico fijo (paleta validada)


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


def serie_vs_ciudad(x, y_barrio, y_ciudad, spec: VarSpec, nombre_barrio: str, *, height: int = 240) -> go.Figure:
    """Serie del barrio (acento) frente al promedio de la ciudad (gris, de referencia)."""
    hover = f"%{{y:,.{spec.decimales}f}} {spec.unidad}"
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=y_ciudad, name="Promedio Cali", mode="lines", connectgaps=False,
        line=dict(color=COLORS["axis"], width=2), hovertemplate=hover + "<extra>Cali</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=y_barrio, name=nombre_barrio, mode="lines+markers", connectgaps=False,
        line=dict(color=COLORS["accent"], width=2),
        marker=dict(size=6, color=COLORS["accent"], line=dict(width=1.5, color=COLORS["page"])),
        hovertemplate=hover + "<extra>Barrio</extra>",
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
             rango: tuple | None = None) -> go.Figure:
    """Barras horizontales de una sola serie con el valor en la punta."""
    colores = [COLORS["accent"] if (destacar is None or c == destacar) else "#9ec5f4" for c in categorias]
    fig = go.Figure(go.Bar(
        x=valores, y=categorias, orientation="h",
        marker=dict(color=colores, line=dict(width=0)),
        text=[f"{v:,.0f}{sufijo}" for v in valores], textposition="outside", cliponaxis=False,
        textfont=dict(color=COLORS["ink_2"], size=12),
        hovertemplate="%{y}: %{x:,.0f}" + sufijo + "<extra></extra>",
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
