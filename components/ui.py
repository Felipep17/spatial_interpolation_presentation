import streamlit as st


def apply_custom_css():
    """Aplica estilos CSS personalizados inspirados en interfaces analíticas modernas."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        /* Ajuste de contenedor principal */
        .main .block-container {
            padding-top: 1.8rem;
            padding-bottom: 2.5rem;
            padding-left: 2.5rem;
            padding-right: 2.5rem;
            max-width: 98% !important;
        }

        /* Tarjetas de Métricas KPI */
        .kpi-card {
            background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 16px 20px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.04);
            transition: all 0.2s ease-in-out;
            margin-bottom: 12px;
        }
        .kpi-card:hover {
            box-shadow: 0 6px 14px rgba(0,0,0,0.08);
            transform: translateY(-2px);
            border-color: #cbd5e1;
        }
        .kpi-title {
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #64748b;
            margin-bottom: 6px;
        }
        .kpi-value {
            font-size: 22px;
            font-weight: 700;
            color: #0f172a;
            line-height: 1.2;
        }
        .kpi-subtitle {
            font-size: 11px;
            color: #94a3b8;
            margin-top: 4px;
        }

        /* Encabezado Principal */
        .page-header-container {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 12px 0 20px 0;
            border-bottom: 1px solid #e2e8f0;
            margin-bottom: 20px;
        }
        .page-title {
            font-size: 26px;
            font-weight: 800;
            color: #0f172a;
            letter-spacing: -0.02em;
            margin: 0;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .page-subtitle {
            font-size: 13px;
            color: #64748b;
            margin-top: 4px;
            margin-bottom: 0;
        }

        /* Badges e Insignias */
        .badge {
            display: inline-flex;
            align-items: center;
            padding: 4px 10px;
            border-radius: 9999px;
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.02em;
        }
        .badge-blue {
            background-color: #eff6ff;
            color: #1d4ed8;
            border: 1px solid #bfdbfe;
        }
        .badge-green {
            background-color: #f0fdf4;
            color: #15803d;
            border: 1px solid #bbf7d0;
        }
        .badge-purple {
            background-color: #faf5ff;
            color: #7e22ce;
            border: 1px solid #e9d5ff;
        }

        /* Tarjeta informativa */
        .info-panel {
            background-color: #f8fafc;
            border-left: 4px solid #3b82f6;
            border-radius: 6px;
            padding: 12px 16px;
            margin-bottom: 16px;
            color: #334155;
            font-size: 13px;
        }

        /* Footer */
        .footer-container {
            margin-top: 40px;
            padding-top: 16px;
            border-top: 1px solid #e2e8f0;
            text-align: center;
            color: #94a3b8;
            font-size: 12px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(title: str, subtitle: str, badge_text: str = None, badge_type: str = "blue"):
    """Renderiza un encabezado moderno estilizado."""
    badge_html = f'<span class="badge badge-{badge_type}">{badge_text}</span>' if badge_text else ""
    st.markdown(
        f"""
        <div class="page-header-container">
            <div>
                <h1 class="page-title">{title}</h1>
                <p class="page-subtitle">{subtitle}</p>
            </div>
            <div>{badge_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_card(title: str, value: str, subtitle: str = ""):
    """Renderiza una tarjeta KPI con estilo refinado."""
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-title">{title}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_footer():
    """Renderiza el pie de página institucional."""
    st.markdown(
        """
        <div class="footer-container">
            Plataforma de Análisis Espaciotemporal y Monitoreo Hidrometeorológico • Santiago de Cali
        </div>
        """,
        unsafe_allow_html=True,
    )
