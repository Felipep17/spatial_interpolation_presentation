"""Explorador de barrios: coropleta del periodo, ficha del barrio elegido y ranking.

Lo comparten Panorama (todos los indicadores) y Fuentes satelitales (los de la fuente activa).
"""

from functools import partial

import numpy as np
import streamlit as st
from streamlit_folium import st_folium

from geoclima.datos.barrios import barrio_en_clic, orden_comunas, puestos
from geoclima.datos.fuentes import FUENTES_META, Indicador, matriz, periodo_txt, serie_area, valores_periodo
from geoclima.mapas.coropleta import mapa_coropleta, mapa_coropleta_animado
from geoclima.ui.componentes import ficha_seleccion, lista_ranking, pista
from geoclima.ui.graficos import mostrar, serie_temporal
from geoclima.ui.i18n import conservar, idioma, t, t_comuna
from geoclima.ui.navegacion import enlace_barrio
from geoclima.ui.tema import COLORS, RASTER_VARS

TODA_CALI = "Toda Cali"  # valor interno del ámbito; se muestra traducido
MODOS = {"periodo": "exp.modo_periodo", "animacion": "exp.modo_animacion"}
ETIQUETA_CORTA = {"rh": "var_corta.hr", "t": "var_corta.tmax_mapa", "p": "var_corta.lluvia", "ndvi": "var_corta.ndvi",
                  "ndwi": "var_corta.ndwi"}


def nombre_ambito(valor: str) -> str:
    """Etiqueta visible de una opción de ámbito: «Toda Cali» o una comuna, en el idioma activo."""
    return t("comuna.toda") if valor == TODA_CALI else t_comuna(valor)


def _etiqueta(ind: Indicador, varias_fuentes: bool) -> str:
    corto = t(ETIQUETA_CORTA[ind.clave]) if ind.clave in ETIQUETA_CORTA else ind.etiqueta
    if not varias_fuentes:
        return ind.etiqueta
    return f"{corto} · {FUENTES_META[ind.fuente]['corto'].split(' ')[0]}" if ind.clave == "p" else corto


def _ranking(barrios, vals, foco, ind: Indicador, n: int = 5):
    """Barrios con los valores más altos y más bajos dentro del ámbito."""
    idx = np.flatnonzero(foco & np.isfinite(vals))
    if not len(idx):
        return
    orden = idx[np.argsort(-vals[idx], kind="stable")]
    lo, hi = float(vals[idx].min()), float(vals[idx].max())
    base = lo - (hi - lo) * 0.15  # la barra del menor valor no queda vacía

    # Puestos dentro del ámbito; los empates comparten puesto (fuentes gruesas dan el mismo valor a vecinos)
    pos = dict(zip(idx, puestos(vals[idx]), strict=True))

    def filas(sel):
        return [{"puesto": pos[i], "nombre": barrios["nombre_barrio"].iat[i], "sub": t_comuna(barrios["comuna"].iat[i]),
                 "valor": ind.fmt(vals[i]), "frac": (vals[i] - base) / max(hi - base, 1e-9)} for i in sel]

    lista_ranking(t("exp.mas_altos"), filas(orden[:n]), COLORS["accent"])
    lista_ranking(t("exp.mas_bajos"), filas(orden[::-1][:n]), "#9ec5f4")
    if len(np.unique(vals[idx])) < len(idx) / 4:
        pista(t("exp.empates"), icono="info")


def _al_clic(key: str, barrios):
    """Guarda el barrio clicado (callback: el valor del mapa ya está en session_state antes del rerun)."""
    nombre = barrio_en_clic(barrios, st.session_state.get(f"{key}_mapa"))
    if nombre:
        st.session_state[f"{key}_sel"] = nombre


@st.cache_data(show_spinner=False, max_entries=32)
def _html_animado(_barrios, clave: str, mat: np.ndarray, fechas: tuple, foco: np.ndarray, titulo: str,
                  etiqueta: str, lang: str, alto: int) -> str:
    """HTML de la coropleta animada (cacheado por indicador, ámbito e idioma; los datos ya vienen calculados)."""
    m = mapa_coropleta_animado(_barrios, mat, list(fechas), RASTER_VARS[clave], titulo, etiqueta=etiqueta,
                               foco=foco, lang=lang)
    return m.get_root().render()


def _animacion(barrios, b: dict, ind: Indicador, foco, alto: int):
    """Coropleta diaria con reproducción (en un iframe: la animación corre en el navegador, sin reruns)."""
    mat = matriz(b["stats"], ind.clave)
    con_dato = np.isfinite(mat).any(axis=0)
    if not con_dato.any():
        pista(t("exp.sin_dias"), icono="info")
        return
    titulo = f"{FUENTES_META[ind.fuente]['corto']} · {t('exp.modo_animacion')}"
    html = _html_animado(barrios, ind.clave, mat, tuple(b["times"]), np.asarray(foco, bool), titulo,
                         ind.spec.label, idioma(), alto)
    c_mapa, c_lado = st.columns([2.1, 1], gap="medium")
    with c_mapa:
        st.iframe(html, height=alto)
    with c_lado:
        pista(t("exp.animacion_pista"), icono="play_circle")
        st.markdown(f"**{t('exp.serie_ciudad')}**")
        mostrar(serie_temporal(b["times"], serie_area(b["stats"], ind.clave), ind.spec, height=230),
                key=f"anim_serie_{ind.id}")
        if (~con_dato).any():
            st.caption(t("exp.dias_omitidos", n=int((~con_dato).sum())))


def explorador(barrios, bundles: dict, indicadores: list[Indicador], *, key: str, alto: int = 600):
    """Dibuja el explorador y devuelve (indicador activo, valores por barrio, ámbito, máscara del ámbito)."""
    varias = len({i.fuente for i in indicadores}) > 1
    por_id = {i.id: i for i in indicadores}
    comunas = orden_comunas(barrios["comuna"])

    conservar(f"{key}_ind", f"{key}_modo", f"{key}_ambito")  # etiquetas traducidas: conservar al cambiar de idioma
    c_ind, c_modo, c_amb = st.columns([3, 1.4, 1.1], vertical_alignment="bottom")
    with c_ind:
        if len(indicadores) > 1:
            ind_id = st.segmented_control(
                t("exp.indicador"), list(por_id), default=indicadores[0].id, required=True, key=f"{key}_ind",
                format_func=lambda i: _etiqueta(por_id[i], varias), wrap=True,
            )
        else:
            ind_id = indicadores[0].id
    with c_modo:
        modo = st.segmented_control(t("exp.modo"), list(MODOS), format_func=lambda m: t(MODOS[m]), default="periodo",
                                    required=True, key=f"{key}_modo", help=t("exp.modo_ayuda"))
    with c_amb:
        ambito = st.selectbox(t("mapa.ambito"), [TODA_CALI, *comunas], key=f"{key}_ambito",
                              format_func=nombre_ambito, help=t("exp.ambito_ayuda"))
    ind = por_id[ind_id]
    b = bundles[ind.fuente]
    vals = valores_periodo(b, ind)
    foco = np.ones(len(vals), bool) if ambito == TODA_CALI else (barrios["comuna"] == ambito).to_numpy()

    if modo == "animacion":
        _animacion(barrios, b, ind, foco, alto)
        return ind, vals, ambito, foco

    m = mapa_coropleta(
        barrios, vals, ind.spec, f"{FUENTES_META[ind.fuente]['corto']} · {periodo_txt(b['times'])}",
        etiqueta=ind.etiqueta, fmt_valor=ind.fmt, foco=foco, pista=t("mapa.pista_clic"),
    )
    c_mapa, c_lado = st.columns([2.1, 1], gap="medium")
    with c_mapa:
        st_folium(m, key=f"{key}_mapa", height=alto, use_container_width=True,
                  returned_objects=["last_clicked"], on_change=partial(_al_clic, key, barrios))
    elegido = st.session_state.get(f"{key}_sel")

    with c_lado:
        if elegido in set(barrios["nombre_barrio"]):
            k = int(np.flatnonzero(barrios["nombre_barrio"].to_numpy() == elegido)[0])
            pos = puestos(vals)
            media = float(np.nanmean(vals))
            dif = vals[k] - media
            u = ind.spec.unidad
            dec = 3 if not u else 1
            meta = (t("exp.puesto_meta", p=pos[k], n=int(np.isfinite(vals).sum()), dif=f"{dif:+,.{dec}f} {u}".strip())
                    if np.isfinite(vals[k]) else t("exp.sin_dato"))
            ficha_seleccion(elegido, t_comuna(barrios["comuna"].iat[k]), ind.fmt(vals[k]), meta)
            enlace_barrio(elegido, ancho="stretch")
        else:
            pista(t("exp.pista"))
        _ranking(barrios, vals, foco, ind)
    return ind, vals, ambito, foco
