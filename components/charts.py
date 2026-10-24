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
