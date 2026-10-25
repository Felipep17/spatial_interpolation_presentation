"""Visores diarios de productos raster: cada píxel día a día, con lectura del píxel y del promedio zonal."""

import json

import numpy as np
from branca.element import Element
from folium.plugins import TimestampedGeoJson

from geoclima.mapas.base import ScriptMapa, capa_barrios, capa_comunas, control_capas, mapa_base
from geoclima.ui.i18n import locale_js, t
from geoclima.ui.tema import COLORS, RASTER_OPACITY, RASTER_VARS, colormap, escala_robusta, leyenda_html


def _periodo(time_vals):
    if len(time_vals) > 1:
        dt_hours = max(1, int((time_vals[1] - time_vals[0]).total_seconds() / 3600))
        period = f"P{dt_hours // 24}D" if dt_hours >= 24 else f"PT{dt_hours}H"
        fmt = "YYYY-MM-DD" if dt_hours >= 24 else "YYYY-MM-DD HH:mm"
        return period, fmt
    return "P1D", "YYYY-MM-DD"


def _features_pixeles(arr, lats, lons, pad, time_vals, cm, opacidad):
    feats = []
    for t_idx, fecha in enumerate(time_vals):
        iso = fecha.isoformat()
        for i, lat in enumerate(lats):
            for j, lon in enumerate(lons):
                v = float(arr[t_idx, i, j])
                if np.isnan(v):
                    continue
                feats.append({
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [[
                        [lon - pad, lat - pad], [lon + pad, lat - pad],
                        [lon + pad, lat + pad], [lon - pad, lat + pad], [lon - pad, lat - pad],
                    ]]},
                    "properties": {
                        "times": [iso],
                        "style": {"fillColor": cm.rgb_hex_str(v), "fillOpacity": opacidad,
                                  "color": COLORS["surface"], "weight": 0.8, "opacity": 0.5},
                    },
                })
    return {"type": "FeatureCollection", "features": feats}


def _timestamped(fc, period, fmt):
    return TimestampedGeoJson(
        fc,
        period=period,
        duration=period,
        add_last_point=False,
        auto_play=False,
        loop=False,
        max_speed=5,
        loop_button=True,
        date_options=fmt,
        time_slider_drag_update=True,
    )


def _grilla_js(arr, dec):
    return [[[None if np.isnan(v) else round(float(v), dec) for v in fila] for fila in paso] for paso in arr]


# JS común: lectura del píxel bajo el cursor y del promedio zonal del barrio
_JS_LECTURA = """
var GC = window.GC;
// En móvil el panel arranca plegado para no tapar el mapa (se despliega tocando el título)
if (window.innerWidth <= 640) {
    var panel = document.querySelector('.gc-panel');
    if (panel) panel.removeAttribute('open');
}
GC.tIdx = function() {
    var td = GC.map.timeDimension;
    return td ? Math.max(0, td.getCurrentTimeIndex()) : 0;
};
GC.fmt = function(v, u) { return (v !== null && v !== undefined) ? v.toLocaleString(GC.locale) + ' ' + u : '—'; };
GC.pixel = function(ll) {
    var g = GC.grid, el = document.getElementById('gc-pix');
    if (!el) return;
    if (GC.var === 'none') { el.innerText = '—'; return; }
    var i = g.lats.findIndex(function(v) { return Math.abs(ll.lat - v) <= g.pad; });
    var j = g.lons.findIndex(function(v) { return Math.abs(ll.lng - v) <= g.pad; });
    el.innerText = (i < 0 || j < 0) ? '—' : GC.fmt(g[GC.var][GC.tIdx()][i][j], GC.units[GC.var]);
};
GC.barrio = function(idx) {
    GC.activo = idx;
    var b = GC.barrios[idx];
    if (!b) return;
    document.getElementById('gc-bnom').innerText = b.nom;
    document.getElementById('gc-bpix').innerText = b.n_pix;
    document.getElementById('gc-bval').innerText =
        GC.var === 'none' ? '—' : GC.fmt(b[GC.var][GC.tIdx()], GC.units[GC.var]);
};
GC.limpiar = function() {
    GC.activo = null;
    ['gc-bnom', 'gc-bpix', 'gc-bval'].forEach(function(id) { document.getElementById(id).innerText = '—'; });
};
GC.capaBarrios.eachLayer(function(l) {
    l.on('mouseover', function() { GC.barrio(l.feature.properties.b_id); });
    l.on('mouseout', GC.limpiar);
});
GC.map.on('mousemove', function(e) { GC.ultimo = e.latlng; GC.pixel(e.latlng); });
if (GC.map.timeDimension) {
    GC.map.timeDimension.on('timeload timechange', function() {
        if (GC.activo !== null) GC.barrio(GC.activo);
        if (GC.ultimo) GC.pixel(GC.ultimo);
    });
}
"""


def _html_lectura(lang: str | None = None) -> str:
    filas = [("gc-pix", "mapa.lectura_pixel", ' class="gc-readout-big"'), ("gc-bnom", "gen.barrio", ""),
             ("gc-bpix", "mapa.lectura_pix_int", ""), ("gc-bval", "mapa.lectura_zonal", "")]
    return '<div class="gc-readout">' + "".join(
        f'<div class="gc-readout-row"><span>{t(k, lang)}</span><span id="{i}"{c}>—</span></div>' for i, k, c in filas
    ) + "</div>"


def _datos_js(m, capa, grid, barrios, units, var_inicial, lang):
    return (
        "window.GC = {"
        f"map: {m.get_name()}, capaBarrios: {capa.get_name()},"
        f"grid: {json.dumps(grid)}, barrios: {json.dumps(barrios)}, units: {json.dumps(units)},"
        f"var: '{var_inicial}', activo: null, ultimo: null, locale: '{locale_js(lang)}'"
        "};\n"
    )


def generar_mapa_dual(gdf_b, capas, titulo, barrios_stats, time_vals, lats, lons, pad, lang: str | None = None):
    """Visor temporal con dos variables alternables.

    capas: [(clave, arreglo T×Ny×Nx, VarSpec, etiqueta corta), (…)]. La primera se muestra al abrir.
    """
    m = mapa_base(gdf_b, lang=lang)
    period, fmt = _periodo(time_vals)
    prep = []
    for clave, arr, spec, etiqueta in capas:
        arr = np.asarray(arr, float)
        cm = colormap(spec.cmap, *escala_robusta(arr, desde_cero=spec.forma == "barra"))
        prep.append((clave, arr, spec, etiqueta, cm, _features_pixeles(arr, lats, lons, pad, time_vals, cm, RASTER_OPACITY)))

    (k0, _, _, _, _, fc0), (k1, _, _, _, _, fc1) = prep
    tg0 = _timestamped(fc0, period, fmt)
    tg0.add_to(m)
    capa_comunas(gdf_b, lang=lang).add_to(m)
    capa = capa_barrios(gdf_b, lang=lang).add_to(m)
    control_capas(m)

    grid = {"lats": [float(x) for x in lats], "lons": [float(x) for x in lons], "pad": float(pad),
            **{c: _grilla_js(a, sp.decimales) for c, a, sp, *_ in prep}}
    radios = "".join(
        f'<label><input type="radio" name="gc-var" value="{c}" {"checked" if n == 0 else ""} '
        f'onchange="GC.cambiar(\'{c}\')">{et}</label>'
        for n, (c, _, _, et, _, _) in enumerate(prep)
    )
    leyendas = "".join(
        f'<div id="gc-leg-{c}" style="display:{"block" if n == 0 else "none"}">'
        f'{leyenda_html(cm, sp, opacidad=RASTER_OPACITY, lang=lang)}</div>'
        for n, (c, _, sp, _, cm, _) in enumerate(prep)
    )
    m.get_root().html.add_child(Element(f"""
    <details class="gc-panel" open>
        <summary class="gc-panel-title">{titulo}</summary>
        <div class="gc-seg">
            {radios}
            <label><input type="radio" name="gc-var" value="none" onchange="GC.cambiar('none')">{t("mapa.ocultar", lang)}</label>
        </div>
        {leyendas}
        {_html_lectura(lang)}
    </details>
    """))

    js = _datos_js(m, capa, grid, barrios_stats, {c: sp.unidad for c, _, sp, *_ in prep}, k0, lang)
    js += f"""
    window.GC.capas = {{
        {k0}: {tg0.get_name()},
        {k1}: L.timeDimension.layer.geoJson(
            L.geoJson({json.dumps(fc1)}, {{ style: function(f) {{ return f.properties.style; }} }}),
            {{ updateTimeDimension: false, duration: "{period}", period: "{period}" }}
        )
    }};
    window.GC.cambiar = function(tipo) {{
        var GC = window.GC;
        GC.var = tipo;
        Object.keys(GC.capas).forEach(function(k) {{
            document.getElementById('gc-leg-' + k).style.display = (k === tipo) ? 'block' : 'none';
            if (k === tipo) {{ GC.map.addLayer(GC.capas[k]); }} else {{ GC.map.removeLayer(GC.capas[k]); }}
        }});
        // Los límites de barrio deben quedar encima del raster para recibir el hover
        if (GC.map.hasLayer(GC.capaBarrios)) GC.capaBarrios.bringToFront();
        if (GC.ultimo) GC.pixel(GC.ultimo);
        if (GC.activo !== null) GC.barrio(GC.activo);
    }};
    """
    js += _JS_LECTURA
    ScriptMapa(js).add_to(m)
    return m


def generar_mapa_interactivo(gdf_b, arr_rh, arr_t, barrios_stats, time_vals, lats, lons, pad, lang: str | None = None):
    capas = [("rh", arr_rh, RASTER_VARS["rh"], t("var_corta.hr", lang)),
             ("t", arr_t, RASTER_VARS["t"], t("var_corta.tmax_mapa", lang))]
    return generar_mapa_dual(gdf_b, capas, "C3S · AgERA5", barrios_stats, time_vals, lats, lons, pad, lang=lang)


def generar_mapa_simple(gdf_b, arr, clave, titulo, leyenda, barrios_stats, time_vals, lats, lons, pad,
                        lang: str | None = None):
    """Visor temporal de una sola variable (precipitación CHIRPS / MSWEP)."""
    m = mapa_base(gdf_b, lang=lang)
    spec = RASTER_VARS[clave]
    arr = np.asarray(arr, float)
    cm = colormap(spec.cmap, *escala_robusta(arr, desde_cero=spec.forma == "barra"))
    period, fmt = _periodo(time_vals)

    fc = _features_pixeles(arr, lats, lons, pad, time_vals, cm, RASTER_OPACITY)
    _timestamped(fc, period, fmt).add_to(m)
    capa_comunas(gdf_b, lang=lang).add_to(m)
    capa = capa_barrios(gdf_b, lang=lang).add_to(m)
    control_capas(m)

    grid = {"lats": [float(x) for x in lats], "lons": [float(x) for x in lons], "pad": float(pad),
            clave: _grilla_js(arr, spec.decimales)}

    m.get_root().html.add_child(Element(f"""
    <details class="gc-panel" open>
        <summary class="gc-panel-title">{titulo}</summary>
        {leyenda_html(cm, spec, leyenda, opacidad=RASTER_OPACITY, lang=lang)}
        {_html_lectura(lang)}
    </details>
    """))
    js = _datos_js(m, capa, grid, barrios_stats, {clave: spec.unidad}, clave, lang) + _JS_LECTURA
    ScriptMapa(js).add_to(m)
    return m
