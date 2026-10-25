"""Coropletas por barrio: valor del periodo (con puesto) y animación diaria."""

import json
import warnings

import folium
import geopandas as gpd
import numpy as np

from geoclima.datos.barrios import puestos
from geoclima.mapas.base import (
    GeoJsonMapa,
    HtmlFijo,
    ScriptMapa,
    capa_comunas,
    control_capas,
    geojson_mapa,
    mapa_base,
    para_mapa,
)
from geoclima.ui.i18n import fecha_corta, locale_js, t, t_comuna
from geoclima.ui.tema import COLORS, VarSpec, colormap, escala_robusta, leyenda_html

COROPLETA_OPACITY = 0.72


SIN_DATO = "#d9d8d2"


def mapa_coropleta(gdf_b, valores, spec: VarSpec, titulo: str, *, etiqueta: str, fmt_valor,
                   seleccion: int | None = None, foco=None, pista: str | None = None,
                   height: int | str = "100%", lang: str | None = None):
    """Barrios coloreados por un valor del periodo, con puesto en el tooltip y leyenda del colormap real.

    fmt_valor: función valor → texto (incluye unidad). seleccion: b_id del barrio a resaltar.
    foco: máscara booleana; los barrios fuera de ella se atenúan y la cámara se ajusta a los de dentro.
    """
    vals = np.asarray(valores, float)
    cm = colormap(spec.cmap, *escala_robusta(vals))
    n_validos = int(np.isfinite(vals).sum())
    pos = puestos(vals)
    foco = np.ones(len(vals), bool) if foco is None else np.asarray(foco, bool)
    datos = gdf_b[["b_id", "nombre_barrio", "comuna", "geometry"]].assign(
        comuna=gdf_b["comuna"].map(lambda c: t_comuna(c, lang)),
        valor=[fmt_valor(v) if np.isfinite(v) else t("mapa.sin_dato", lang) for v in vals],
        puesto=[t("gen.a_de_b", lang, a=p, b=n_validos) if p else "—" for p in pos],
        relleno=[cm.rgb_hex_str(v) if np.isfinite(v) else SIN_DATO for v in vals],
        opacidad=np.where(foco, COROPLETA_OPACITY, 0.16),
    )

    m = mapa_base(gdf_b, height=height, lang=lang)
    if not foco.all():
        minx, miny, maxx, maxy = gdf_b.loc[foco].total_bounds
        m.fit_bounds([[miny - 0.004, minx - 0.004], [maxy + 0.004, maxx + 0.004]])
    GeoJsonMapa(
        geojson_mapa(datos),
        name=etiqueta,
        style_function=lambda f: {"fillColor": f["properties"]["relleno"], "fillOpacity": f["properties"]["opacidad"],
                                  "color": "#ffffff", "weight": 0.7, "opacity": 0.9},
        highlight_function=lambda f: {"weight": 2.4, "color": COLORS["ink"], "fillOpacity": 0.85},
        tooltip=folium.GeoJsonTooltip(fields=["nombre_barrio", "comuna", "valor", "puesto"],
                                      aliases=[t("gen.barrio", lang), t("gen.comuna", lang), etiqueta,
                                               t("mapa.puesto", lang)], sticky=True,
                                      class_name="gc-tooltip"),
    ).add_to(m)
    capa_comunas(gdf_b, show=True, lang=lang).add_to(m)
    if not foco.all():
        borde = gpd.GeoDataFrame(geometry=[gdf_b.loc[foco].geometry.union_all()], crs=gdf_b.crs)
        folium.GeoJson(borde, name=t("mapa.ambito", lang), interactive=False, control=False,
                       style_function=lambda f: {"fillOpacity": 0, "color": COLORS["ink"], "weight": 2.2,
                                                 "opacity": 0.9}).add_to(m)
    if seleccion is not None:
        folium.GeoJson(
            gdf_b.iloc[[seleccion]][["nombre_barrio", "geometry"]], name=t("mapa.barrio_sel", lang),
            style_function=lambda f: {"fillOpacity": 0, "color": COLORS["ink"], "weight": 3, "opacity": 1},
            interactive=False,
        ).add_to(m)

    control_capas(m)
    pista_html = f'<div class="gc-legend-note" style="margin-top:8px">{pista}</div>' if pista else ""
    m.get_root().html.add_child(HtmlFijo(f"""
    <details class="gc-panel" open>
        <summary class="gc-panel-title">{titulo}</summary>
        {leyenda_html(cm, spec, etiqueta, opacidad=COROPLETA_OPACITY, nota=t("mapa.nota_escala_barrios", lang),
                      lang=lang)}
        {pista_html}
    </details>
    """))
    # En móvil el panel arranca plegado para no tapar el mapa
    ScriptMapa("""
    if (window.innerWidth <= 640) {
        var panel = document.querySelector('.gc-panel');
        if (panel) panel.removeAttribute('open');
    }""").add_to(m)
    return m


# JS de la coropleta animada: recolorea la capa de barrios día a día (la geometría no se repite)
_JS_ANIMACION = """
var A = window.GCA;
A.fmt = function(v) {
    return (v === null || v === undefined) ? A.txt.sin_dato
        : v.toLocaleString(A.locale, {minimumFractionDigits: A.dec, maximumFractionDigits: A.dec}) + (A.unidad ? ' ' + A.unidad : '');
};
A.el = function(id) { return document.getElementById(id); };
A.leer = function(i) {
    A.activo = i;
    if (i === null) { ['gc-a-nom', 'gc-a-com', 'gc-a-val', 'gc-a-pos'].forEach(function(id) { A.el(id).innerText = '—'; }); return; }
    var v = A.valores[A.t][i], p = A.puestos[A.t][i];
    A.el('gc-a-nom').innerText = A.nombres[i];
    A.el('gc-a-com').innerText = A.comunas[i];
    A.el('gc-a-val').innerText = A.fmt(v);
    A.el('gc-a-pos').innerText = p ? (p + ' ' + A.txt.de + ' ' + A.nvalidos[A.t]) : '—';
};
A.pintar = function(d) {
    A.t = d;
    A.capa.eachLayer(function(l) { l.setStyle({fillColor: A.colores[d][l.feature.properties.b_id]}); });
    A.el('gc-a-fecha').innerText = A.fechas[d];
    A.el('gc-a-slider').value = d;
    A.el('gc-a-media').innerText = A.fmt(A.medias[d]);
    if (A.activo !== null) A.leer(A.activo);
};
A.paso = function(delta) { A.pintar((A.t + delta + A.fechas.length) % A.fechas.length); };
A.pausar = function() {
    if (A.timer) { clearInterval(A.timer); A.timer = null; }
    var b = A.el('gc-a-play'); b.innerText = '▶'; b.title = A.txt.reproducir;
};
A.alternar = function() {
    if (A.timer) { A.pausar(); return; }
    A.timer = setInterval(function() { A.paso(1); }, A.ms);
    var b = A.el('gc-a-play'); b.innerText = '❚❚'; b.title = A.txt.pausar;
};
A.el('gc-a-play').onclick = A.alternar;
A.el('gc-a-prev').onclick = function() { A.pausar(); A.paso(-1); };
A.el('gc-a-next').onclick = function() { A.pausar(); A.paso(1); };
A.el('gc-a-slider').oninput = function(e) { A.pausar(); A.pintar(parseInt(e.target.value, 10)); };
A.capa.eachLayer(function(l) {
    l.on('mouseover', function() { l.setStyle({weight: 2.4, color: A.borde_activo}); l.bringToFront(); A.leer(l.feature.properties.b_id); });
    l.on('mouseout', function() { l.setStyle({weight: 0.7, color: '#ffffff'}); A.leer(null); });
});
if (window.innerWidth <= 640) {
    var panel = document.querySelector('.gc-panel');
    if (panel) panel.removeAttribute('open');
}
A.pintar(A.inicio);
"""


def mapa_coropleta_animado(gdf_b, matriz_dias, fechas, spec: VarSpec, titulo: str, *, etiqueta: str,
                           foco=None, lang: str | None = None, height: int | str = "100%", ms: int = 800):
    """Coropleta diaria con reproducción: barrios coloreados por su valor zonal de cada día.

    matriz_dias: barrios × días (orden de la capa de barrios); los días sin ningún dato se omiten.
    La geometría de los barrios viaja una sola vez y el JS solo cambia el color al pasar de día, así el HTML
    es liviano y la animación fluida. La escala es común a todos los días para que los colores sean comparables.
    """
    mat = np.asarray(matriz_dias, float)
    dias = np.flatnonzero(np.isfinite(mat).any(axis=0))
    mat, fechas = mat[:, dias], [fechas[d] for d in dias]
    cm = colormap(spec.cmap, *escala_robusta(mat, desde_cero=spec.forma == "barra"))
    foco = np.ones(len(mat), bool) if foco is None else np.asarray(foco, bool)
    dec = spec.decimales

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        medias = np.nanmean(mat, axis=0)
    columnas = [mat[:, d] for d in range(mat.shape[1])]
    datos_js = {
        "fechas": [fecha_corta(f, lang) for f in fechas],
        "valores": [[round(float(v), dec) if np.isfinite(v) else None for v in col] for col in columnas],
        "colores": [[cm.rgb_hex_str(v) if np.isfinite(v) else SIN_DATO for v in col] for col in columnas],
        "puestos": [puestos(col).tolist() for col in columnas],
        "nvalidos": [int(np.isfinite(col).sum()) for col in columnas],
        "medias": [round(float(v), dec) if np.isfinite(v) else None for v in medias],
        "nombres": gdf_b["nombre_barrio"].tolist(),
        "comunas": [t_comuna(c, lang) for c in gdf_b["comuna"]],
        "unidad": spec.unidad, "dec": dec, "locale": locale_js(lang), "ms": ms,
        "inicio": int(np.nanargmax(medias)) if np.isfinite(medias).any() else 0,  # abre en el día de mayor valor
        "borde_activo": COLORS["ink"],
        "txt": {"sin_dato": t("mapa.sin_dato", lang), "de": t("mapa.de", lang), "reproducir": t("mapa.reproducir", lang),
                "pausar": t("mapa.pausar", lang)},
    }

    datos = para_mapa(gdf_b[["b_id", "nombre_barrio", "geometry"]]).assign(
        opacidad=np.where(foco, COROPLETA_OPACITY, 0.16))
    m = mapa_base(gdf_b, height=height, lang=lang)
    if not foco.all():
        minx, miny, maxx, maxy = gdf_b.loc[foco].total_bounds
        m.fit_bounds([[miny - 0.004, minx - 0.004], [maxy + 0.004, maxx + 0.004]])
    capa = folium.GeoJson(
        datos, name=etiqueta,
        style_function=lambda f: {"fillColor": SIN_DATO, "fillOpacity": f["properties"]["opacidad"],
                                  "color": "#ffffff", "weight": 0.7, "opacity": 0.9},
    ).add_to(m)
    capa_comunas(gdf_b, show=True, lang=lang).add_to(m)
    if not foco.all():
        borde = gpd.GeoDataFrame(geometry=[gdf_b.loc[foco].geometry.union_all()], crs=gdf_b.crs)
        folium.GeoJson(borde, name=t("mapa.ambito", lang), interactive=False, control=False,
                       style_function=lambda f: {"fillOpacity": 0, "color": COLORS["ink"], "weight": 2.2,
                                                 "opacity": 0.9}).add_to(m)
    control_capas(m)

    filas = [("gc-a-nom", "gen.barrio"), ("gc-a-com", "gen.comuna"), ("gc-a-val", "mapa.valor_dia"),
             ("gc-a-pos", "mapa.puesto_dia"), ("gc-a-media", "mapa.promedio_dia")]
    lectura = "".join(f'<div class="gc-readout-row"><span>{t(k, lang)}</span><span id="{i}">—</span></div>'
                      for i, k in filas)
    m.get_root().html.add_child(HtmlFijo(f"""
    <details class="gc-panel" open>
        <summary class="gc-panel-title">{titulo}</summary>
        {leyenda_html(cm, spec, etiqueta, opacidad=COROPLETA_OPACITY, nota=t("mapa.nota_escala_dias", lang), lang=lang)}
        <div class="gc-readout">{lectura}</div>
    </details>
    <div class="gc-anim">
        <button id="gc-a-prev" title="{t("mapa.anterior", lang)}">‹</button>
        <button id="gc-a-play" class="gc-play" title="{t("mapa.reproducir", lang)}">▶</button>
        <button id="gc-a-next" title="{t("mapa.siguiente", lang)}">›</button>
        <span id="gc-a-fecha" class="gc-anim-fecha">—</span>
        <input id="gc-a-slider" type="range" min="0" max="{len(fechas) - 1}" step="1" value="0"
               aria-label="{t("mapa.dia", lang)}">
        <span class="gc-anim-n">{t("mapa.n_dias", lang, n=len(fechas))}</span>
    </div>
    """))
    js = f"window.GCA = Object.assign({json.dumps(datos_js, separators=(',', ':'))}, {{map: {m.get_name()}, capa: {capa.get_name()}, " \
         "t: 0, timer: null, activo: null});\n" + _JS_ANIMACION
    ScriptMapa(js).add_to(m)
    return m
