import json
from pathlib import Path
import branca.colormap as bcm
from branca.element import Element
import folium
from folium.plugins import TimestampedGeoJson
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box
import streamlit as st
import xarray as xr

@st.cache_data(show_spinner=False)
def obtener_html_mapa_c3s(
    _gdf, _da_rh, _da_t, barrios_stats, time_vals, lats, lons, pad
):
    mapa = generar_mapa_interactivo(
        _gdf, _da_rh, _da_t, barrios_stats, time_vals, lats, lons, pad
    )
    return mapa.get_root().render()
@st.cache_data(show_spinner=False)
def obtener_html_mapa_chirps(_gdf, nc_path: Path):
    mapa = generar_mapa_chirps(_gdf, nc_path)
    return mapa.get_root().render()
@st.cache_data
def cargar_shapefile(carpeta: Path):
    formatos = ["*.parquet", "*.shp", "*.geojson", "*.gpkg"]
    arch = None
    for fmt in formatos:
        hits = list(carpeta.glob(fmt))
        if hits:
            arch = hits[0]
            break
    if not arch:
        raise FileNotFoundError(f"Sin vectores en {carpeta}")
    gdf = (
        gpd.read_parquet(arch)
        if arch.suffix == ".parquet"
        else gpd.read_file(arch)
    )
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    return gdf


def listar_fuentes(raster_dir: Path):
    fuentes = {}
    if raster_dir.exists():
        for d in sorted([p for p in raster_dir.iterdir() if p.is_dir()]):
            fuentes[d.name] = sorted(
                list(d.glob("*.nc")) + list(d.glob("*.tif"))
            )
    return fuentes


def cargar_recorte_nc(nc_path: Path, bounds, res=0.1):
    minx, miny, maxx, maxy = bounds
    pad = res / 2

    try:
        ds = xr.open_dataset(nc_path, engine="h5netcdf")
    except Exception:
        ds = xr.open_dataset(nc_path)

    vars_validas = [
        v
        for v in ds.data_vars
        if len(ds[v].dims) >= 2 and v not in ["spatial_ref", "crs"]
    ]
    var_name = vars_validas[0] if vars_validas else list(ds.data_vars)[0]
    da = ds[var_name]
    lat_col = next(
        c
        for c in list(da.coords) + list(da.dims)
        if c.lower() in ["latitude", "lat", "y"]
    )
    lon_col = next(
        c
        for c in list(da.coords) + list(da.dims)
        if c.lower() in ["longitude", "lon", "x"]
    )
    minx_s, maxx_s = (
        (minx + 360, maxx + 360)
        if (float(da[lon_col].min()) >= 0 and minx < 0)
        else (minx, maxx)
    )
    lat_slice = (
        slice(maxy + pad, miny - pad)
        if da[lat_col].values[0] > da[lat_col].values[-1]
        else slice(miny - pad, maxy + pad)
    )
    lon_slice = slice(minx_s - pad, maxx_s + pad)
    da = da.sel({lat_col: lat_slice, lon_col: lon_slice})
    if float(ds[lon_col].min()) >= 0 and minx < 0:
        da = da.assign_coords({lon_col: da[lon_col] - 360})
    if (
        "temp" in var_name.lower()
        or "t2m" in var_name.lower()
        or "mx2t" in var_name.lower()
    ) and float(da.mean().values) > 100:
        da = da - 273.15
    return da, lat_col, lon_col, pad

def calcular_estadisticas_zonales(
    gdf: gpd.GeoDataFrame,
    da_rh: xr.DataArray,
    da_t: xr.DataArray,
    lat_col: str,
    lon_col: str,
    pad: float,
):
    lats = da_rh[lat_col].values
    lons = da_rh[lon_col].values
    time_vals = pd.to_datetime(da_rh.time.values)
    pixel_boxes = [
        {
            "i": i,
            "j": j,
            "geom": box(lon - pad, lat - pad, lon + pad, lat + pad),
        }
        for i, lat in enumerate(lats)
        for j, lon in enumerate(lons)
    ]
    col_nombre = next(
        (c for c in gdf.columns if c.lower() == "nombre"), gdf.columns[0]
    )
    gdf["b_id"] = list(range(len(gdf)))
    gdf["nombre_barrio"] = gdf[col_nombre].astype(str)
    barrios_stats = []
    for idx, row in gdf.iterrows():
        b_geom = row.geometry
        touching = [p for p in pixel_boxes if b_geom.intersects(p["geom"])]
        rh_prom, t_prom = [], []
        for ti in range(len(time_vals)):
            v_rh = [
                float(da_rh.isel(time=ti).values[p["i"], p["j"]])
                for p in touching
            ]
            v_t = [
                float(da_t.isel(time=ti).values[p["i"], p["j"]])
                for p in touching
            ]
            v_rh = [v for v in v_rh if not np.isnan(v)]
            v_t = [v for v in v_t if not np.isnan(v)]
            rh_prom.append(round(float(np.mean(v_rh)), 1) if v_rh else None)
            t_prom.append(round(float(np.mean(v_t)), 1) if v_t else None)
        barrios_stats.append(
            {
                "id": int(idx),
                "nom": str(row["nombre_barrio"]),
                "n_pix": int(len(touching)),
                "rh": rh_prom,
                "t": t_prom,
            }
        )
    gdf["n_pixeles"] = [b["n_pix"] for b in barrios_stats]
    return barrios_stats, time_vals, lats, lons


def generar_mapa_interactivo(
    gdf, da_rh, da_t, barrios_stats, time_vals, lats, lons, pad, *args, **kwargs
):
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    minx, miny, maxx, maxy = [float(v) for v in gdf.total_bounds]
    centro_lat = (miny + maxy) / 2
    centro_lon = (minx + maxx) / 2

    m = folium.Map(
        location=[centro_lat, centro_lon],
        zoom_start=12,
        min_zoom=9,
        max_bounds=True,
        min_lat=miny - 0.5,
        max_lat=maxy + 0.5,
        min_lon=minx - 0.5,
        max_lon=maxx + 0.5,
        tiles="OpenStreetMap",
        width="100%",
        height="780px",
    )
    m.fit_bounds([[miny, minx], [maxy, maxx]])

    vmin_rh, vmax_rh = round(float(np.nanmin(da_rh.values)), 1), round(
        float(np.nanmax(da_rh.values)), 1
    )
    vmin_t, vmax_t = round(float(np.nanmin(da_t.values)), 1), round(
        float(np.nanmax(da_t.values)), 1
    )
    cm_rh = bcm.linear.viridis.scale(vmin_rh, vmax_rh)
    cm_t = bcm.linear.YlOrRd_09.scale(vmin_t, vmax_t)

    if len(time_vals) > 1:
        dt_hours = max(
            1, int((time_vals[1] - time_vals[0]).total_seconds() / 3600)
        )
        period_str = (
            f"P{dt_hours // 24}D" if dt_hours >= 24 else f"PT{dt_hours}H"
        )
        date_fmt = "YYYY-MM-DD" if dt_hours >= 24 else "YYYY-MM-DD HH:mm"
    else:
        period_str = "P1D"
        date_fmt = "YYYY-MM-DD"

    features_rh, features_t = [], []
    for t_idx, t in enumerate(time_vals):
        iso_time = t.isoformat()
        vals_rh = da_rh.isel(time=t_idx).values
        vals_t = da_t.isel(time=t_idx).values
        for i, lat_val in enumerate(lats):
            for j, lon_val in enumerate(lons):
                v_rh, v_t = float(vals_rh[i, j]), float(vals_t[i, j])
                coords = [
                    [
                        [lon_val - pad, lat_val - pad],
                        [lon_val + pad, lat_val - pad],
                        [lon_val + pad, lat_val + pad],
                        [lon_val - pad, lat_val + pad],
                        [lon_val - pad, lat_val - pad],
                    ]
                ]
                if not np.isnan(v_rh):
                    features_rh.append(
                        {
                            "type": "Feature",
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": coords,
                            },
                            "properties": {
                                "times": [iso_time],
                                "style": {
                                    "fillColor": cm_rh(v_rh),
                                    "fillOpacity": 0.38,
                                    "color": "white",
                                    "weight": 0.3,
                                },
                            },
                        }
                    )
                if not np.isnan(v_t):
                    features_t.append(
                        {
                            "type": "Feature",
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": coords,
                            },
                            "properties": {
                                "times": [iso_time],
                                "style": {
                                    "fillColor": cm_t(v_t),
                                    "fillOpacity": 0.38,
                                    "color": "white",
                                    "weight": 0.3,
                                },
                            },
                        }
                    )

    tg_rh = TimestampedGeoJson(
        {"type": "FeatureCollection", "features": features_rh},
        period=period_str,
        duration=period_str,
        add_last_point=False,
        auto_play=False,
        loop=False,
        max_speed=5,
        loop_button=True,
        date_options=date_fmt,
        time_slider_drag_update=True,
    )
    tg_rh.add_to(m)

    folium.GeoJson(
        gdf,
        name="Límites Cali",
        show=True,
        style_function=lambda x: {
            "fillColor": "#ffffff",
            "fillOpacity": 0.04,
            "color": "#111111",
            "weight": 1.2,
        },
        highlight_function=lambda x: {
            "weight": 2.5,
            "color": "#000000",
            "fillOpacity": 0.20,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["nombre_barrio", "n_pixeles"],
            aliases=["Barrio:", "No. Píxeles:"],
            localize=True,
            sticky=True,
            style="background-color: white; border-radius: 4px; padding: 6px; font-weight: bold; border: 1px solid #444;",
        ),
    ).add_to(m)

    folium.LayerControl(position="topright", collapsed=False).add_to(m)

    grid_data = {
        "lats": [float(x) for x in lats],
        "lons": [float(x) for x in lons],
        "pad": float(pad),
        "rh": [
            [
                [
                    (
                        None
                        if np.isnan(v)
                        else round(float(v), 1)
                    )
                    for v in da_rh.isel(time=t_i).values[i]
                ]
                for i in range(len(lats))
            ]
            for t_i in range(len(time_vals))
        ],
        "t": [
            [
                [
                    (
                        None
                        if np.isnan(v)
                        else round(float(v), 1)
                    )
                    for v in da_t.isel(time=t_i).values[i]
                ]
                for i in range(len(lats))
            ]
            for t_i in range(len(time_vals))
        ],
    }

    panel_html = Element(f"""
    <div id="panel-control" style="position: absolute; top: 14px; left: 55px; z-index: 1000; background: white; padding: 12px 16px; border-radius: 8px; box-shadow: 0 3px 10px rgba(0,0,0,0.25); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; width: 240px;">
        <div style="font-weight: bold; margin-bottom: 6px; font-size: 13px; border-bottom: 1px solid #eee; padding-bottom: 4px;">📊 Variable Activa</div>
        <label style="cursor: pointer; display: block; margin-bottom: 3px; font-size: 13px;"><input type="radio" name="rad_var" value="rh" checked onchange="window.cambiarVar('rh')"> Humedad Relativa</label>
        <label style="cursor: pointer; display: block; margin-bottom: 3px; font-size: 13px;"><input type="radio" name="rad_var" value="t" onchange="window.cambiarVar('t')"> Temp. Máxima</label>
        <label style="cursor: pointer; display: block; margin-bottom: 8px; font-size: 13px; color: #555;"><input type="radio" name="rad_var" value="none" onchange="window.cambiarVar('none')"> Ocultar Raster</label>
        <div id="barra-rh">
            <div style="display: flex; justify-content: space-between; font-size: 11px; font-weight: bold; color: #444;"><span>{vmin_rh}%</span><span>{((vmin_rh + vmax_rh)/2):.1f}%</span><span>{vmax_rh}%</span></div>
            <div style="height: 12px; border-radius: 3px; background: linear-gradient(to right, #440154, #3b528b, #21918c, #5ec962, #fde725); border: 1px solid #aaa; margin: 3px 0;"></div>
            <div style="text-align: center; font-size: 10px; color: #666;">Humedad Relativa (%)</div>
        </div>
        <div id="barra-t" style="display: none;">
            <div style="display: flex; justify-content: space-between; font-size: 11px; font-weight: bold; color: #444;"><span>{vmin_t}°C</span><span>{((vmin_t + vmax_t)/2):.1f}°C</span><span>{vmax_t}°C</span></div>
            <div style="height: 12px; border-radius: 3px; background: linear-gradient(to right, #ffffb2, #fed976, #feb24c, #fd8d3c, #f03b20, #bd0026); border: 1px solid #aaa; margin: 3px 0;"></div>
            <div style="text-align: center; font-size: 10px; color: #666;">Temperatura Máxima (°C)</div>
        </div>
        <div id="box-valor" style="margin-top: 8px; padding: 5px 8px; background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 4px;">
            <div style="font-size: 10px; color: #6c757d; text-transform: uppercase;">Pixel bajo el cursor:</div>
            <div id="txt-valor" style="font-size: 15px; font-weight: bold; color: #0d6efd;">--</div>
        </div>
        <div id="box-barrio" style="margin-top: 8px; padding: 6px 8px; background: #eef4fc; border: 1px solid #d5e4f7; border-radius: 4px; font-size: 11px;">
            <div style="font-weight: bold; color: #1e4273; border-bottom: 1px solid #c8dcf5; padding-bottom: 2px; margin-bottom: 3px;">📍 Barrio Seleccionado:</div>
            <div><b>Nombre:</b> <span id="b-nom">--</span></div>
            <div><b>No. Píxeles:</b> <span id="b-pix">--</span></div>
            <div><b>Promedio Zonal:</b> <span id="b-val" style="font-weight: bold; color: #d9381e;">--</span></div>
        </div>
    </div>
    <script>
    window.grid_info = {json.dumps(grid_data)};
    window.barrios_info = {json.dumps(barrios_stats)};
    window.cali_geojson = {gdf[["b_id", "geometry"]].to_json()};
    window.features_t = {json.dumps({"type": "FeatureCollection", "features": features_t})};
    window.varActiva = 'rh';
    window.map_id = "{m.get_name()}";
    window.rh_id = "{tg_rh.get_name()}";
    window.layer_t = null;
    window.barrioActivoIdx = null;
    window.caliLayerVisible = true;
    window.ultimoLatLng = null;
    var b_coords_c3s = [[{miny}, {minx}], [{maxy}, {maxx}]];

    window.cambiarVar = function(tipo) {{
        window.varActiva = tipo;
        var b_rh = document.getElementById('barra-rh');
        var b_t = document.getElementById('barra-t');
        var box_val = document.getElementById('box-valor');
        var map = window[window.map_id];
        var l_rh = window[window.rh_id];
        var l_t = window.layer_t;
        if (tipo === 't') {{
            if (b_rh) b_rh.style.display = 'none';
            if (b_t) b_t.style.display = 'block';
            if (box_val) box_val.style.display = 'block';
            if (map && l_rh && l_t) {{ map.removeLayer(l_rh); map.addLayer(l_t); if (l_t._onNewTimeDimensionAvailable) l_t._onNewTimeDimensionAvailable(); }}
        }} else if (tipo === 'rh') {{
            if (b_t) b_t.style.display = 'none';
            if (b_rh) b_rh.style.display = 'block';
            if (box_val) box_val.style.display = 'block';
            if (map && l_rh && l_t) {{ map.removeLayer(l_t); map.addLayer(l_rh); if (l_rh._onNewTimeDimensionAvailable) l_rh._onNewTimeDimensionAvailable(); }}
        }} else {{
            if (b_rh) b_rh.style.display = 'none';
            if (b_t) b_t.style.display = 'none';
            if (box_val) box_val.style.display = 'none';
            if (map && l_rh && l_t) {{ map.removeLayer(l_rh); map.removeLayer(l_t); }}
        }}
        if (window.ultimoLatLng) window.actualizarPixel(window.ultimoLatLng);
        if (window.barrioActivoIdx !== null) window.actualizarInfoBarrio(window.barrioActivoIdx);
    }};

    window.actualizarPixel = function(latlng) {{
        var lat = latlng.lat, lon = latlng.lng, g = window.grid_info;
        var i_lat = -1;
        for (var i = 0; i < g.lats.length; i++) {{ if (Math.abs(lat - g.lats[i]) <= g.pad) {{ i_lat = i; break; }} }}
        var j_lon = -1;
        for (var j = 0; j < g.lons.length; j++) {{ if (Math.abs(lon - g.lons[j]) <= g.pad) {{ j_lon = j; break; }} }}
        var el = document.getElementById('txt-valor');
        var map = window[window.map_id];
        if (el && i_lat !== -1 && j_lon !== -1) {{
            var t_idx = 0;
            if (map && map.timeDimension) {{ t_idx = map.timeDimension.getCurrentTimeIndex(); if (t_idx < 0) t_idx = 0; }}
            var val = (window.varActiva === 'rh') ? g.rh[t_idx][i_lat][j_lon] : g.t[t_idx][i_lat][j_lon];
            el.innerText = (val !== null && val !== undefined) ? ((window.varActiva === 'rh') ? val + ' %' : val + ' °C') : '--';
        }} else if (el) {{
            el.innerText = '--';
        }}
    }};

    window.actualizarInfoBarrio = function(idx) {{
        if (!window.caliLayerVisible) return;
        window.barrioActivoIdx = idx;
        var b = window.barrios_info[idx];
        if (!b) return;
        document.getElementById('b-nom').innerText = b.nom;
        document.getElementById('b-pix').innerText = b.n_pix;
        var map = window[window.map_id];
        var t_idx = 0;
        if (map && map.timeDimension) {{ t_idx = map.timeDimension.getCurrentTimeIndex(); if (t_idx < 0) t_idx = 0; }}
        var elVal = document.getElementById('b-val');
        if (window.varActiva === 'none') {{ elVal.innerText = 'Raster Oculto'; }}
        else if (window.varActiva === 'rh') {{ var v = b.rh[t_idx]; elVal.innerText = (v !== null ? v + ' %' : '--'); }}
        else {{ var v = b.t[t_idx]; elVal.innerText = (v !== null ? v + ' °C' : '--'); }}
    }};

    window.limpiarInfoBarrio = function() {{
        window.barrioActivoIdx = null;
        document.getElementById('b-nom').innerText = '--';
        document.getElementById('b-pix').innerText = '--';
        document.getElementById('b-val').innerText = '--';
    }};

    function forzarCaliC3S() {{
        var map = window[window.map_id];
        if (!map) return;
        map.invalidateSize();
        map.setView([{centro_lat}, {centro_lon}], 12);
        map.fitBounds(b_coords_c3s, {{padding: [20, 20]}});
    }}

    function iniciarControl() {{
        var map = window[window.map_id];
        var l_rh = window[window.rh_id];
        var map_div = document.getElementById(window.map_id);
        if (!map || !l_rh || !map.timeDimension || !map_div) {{ setTimeout(iniciarControl, 100); return; }}
        
        forzarCaliC3S();

        window.layer_t = L.timeDimension.layer.geoJson(L.geoJson(window.features_t, {{ style: function(f) {{ return f.properties.style; }} }}), {{ updateTimeDimension: false, duration: "{period_str}", period: "{period_str}" }});
        var caliInteractive = L.geoJson(window.cali_geojson, {{
            style: {{ fillColor: '#ffffff', fillOpacity: 0.01, color: 'transparent', weight: 1 }},
            onEachFeature: function(feature, layer) {{
                layer.on({{
                    mouseover: function(e) {{ if (feature.properties && feature.properties.b_id !== undefined) {{ window.actualizarInfoBarrio(feature.properties.b_id); }} }},
                    mouseout: function(e) {{ window.limpiarInfoBarrio(); }}
                }});
            }}
        }}).addTo(map);

        map.timeDimension.on('timeload timechange', function() {{
            if (window.barrioActivoIdx !== null) window.actualizarInfoBarrio(window.barrioActivoIdx);
            if (window.ultimoLatLng) window.actualizarPixel(window.ultimoLatLng);
        }});
        map.on('overlayremove', function(e) {{
            if (e.name === "Límites Cali") {{ window.caliLayerVisible = false; window.limpiarInfoBarrio(); map.removeLayer(caliInteractive); document.getElementById('b-nom').innerText = 'Capa Desactivada'; }}
        }});
        map.on('overlayadd', function(e) {{
            if (e.name === "Límites Cali") {{ window.caliLayerVisible = true; window.limpiarInfoBarrio(); map.addLayer(caliInteractive); }}
        }});
        map_div.addEventListener('mousemove', function(e) {{
            if (window.varActiva === 'none') return;
            window.ultimoLatLng = map.mouseEventToLatLng(e);
            window.actualizarPixel(window.ultimoLatLng);
        }});

        [200, 500, 1000, 2000].forEach(function(d){{
            setTimeout(forzarCaliC3S, d);
        }});
    }}
    window.addEventListener('load', iniciarControl);
    setTimeout(iniciarControl, 150);
    </script>
    """)
    m.get_root().html.add_child(panel_html)
    return m


def generar_mapa_chirps(gdf: gpd.GeoDataFrame, nc_path: Path):
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    try:
        ds = xr.open_dataset(nc_path, engine="h5netcdf")
    except Exception:
        ds = xr.open_dataset(nc_path)

    da_p = ds["precipitation"]
    lat_col = "lat" if "lat" in da_p.coords else "latitude"
    lon_col = "lon" if "lon" in da_p.coords else "longitude"

    lats = da_p[lat_col].values
    lons = da_p[lon_col].values
    time_vals = pd.to_datetime(da_p.time.values)
    pad = (
        abs(float(lats[1] - lats[0])) / 2.0
        if len(lats) > 1
        else abs(float(lons[1] - lons[0])) / 2.0
    )

    minx, miny, maxx, maxy = [float(v) for v in gdf.total_bounds]
    centro_lat = (miny + maxy) / 2
    centro_lon = (minx + maxx) / 2

    m = folium.Map(
        location=[centro_lat, centro_lon],
        zoom_start=12,
        tiles="OpenStreetMap",
        width="100%",
        height="780px",
    )
    m.fit_bounds([[miny, minx], [maxy, maxx]])

    pixel_boxes = [
        {
            "i": i,
            "j": j,
            "geom": box(lon - pad, lat - pad, lon + pad, lat + pad),
        }
        for i, lat in enumerate(lats)
        for j, lon in enumerate(lons)
    ]
    col_nombre = next(
        (c for c in gdf.columns if c.lower() == "nombre"), gdf.columns[0]
    )
    gdf["b_id"] = list(range(len(gdf)))
    gdf["nombre_barrio"] = gdf[col_nombre].astype(str)

    barrios_stats = []
    for idx, row in gdf.iterrows():
        b_geom = row.geometry
        touching = [p for p in pixel_boxes if b_geom.intersects(p["geom"])]
        p_prom = []
        for ti in range(len(time_vals)):
            vals = [
                float(da_p.isel(time=ti).values[p["i"], p["j"]])
                for p in touching
            ]
            vals = [v for v in vals if not np.isnan(v)]
            p_prom.append(round(float(np.mean(vals)), 2) if vals else None)
        barrios_stats.append(
            {
                "id": int(idx),
                "nom": str(row["nombre_barrio"]),
                "n_pix": int(len(touching)),
                "p": p_prom,
            }
        )
    gdf["n_pixeles"] = [b["n_pix"] for b in barrios_stats]

    vals_clean = da_p.values[~np.isnan(da_p.values)]
    vmin_p = 0.0
    vmax_p = (
        max(1.0, round(float(np.max(vals_clean)), 1))
        if len(vals_clean)
        else 10.0
    )
    cm_p = bcm.linear.YlGnBu_09.scale(vmin_p, vmax_p)

    features_p = []
    for t_idx, t in enumerate(time_vals):
        iso_time = t.isoformat()
        vals_mat = da_p.isel(time=t_idx).values
        for i, lat_val in enumerate(lats):
            for j, lon_val in enumerate(lons):
                v = float(vals_mat[i, j])
                if not np.isnan(v):
                    coords = [
                        [
                            [lon_val - pad, lat_val - pad],
                            [lon_val + pad, lat_val - pad],
                            [lon_val + pad, lat_val + pad],
                            [lon_val - pad, lat_val + pad],
                            [lon_val - pad, lat_val - pad],
                        ]
                    ]
                    features_p.append(
                        {
                            "type": "Feature",
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": coords,
                            },
                            "properties": {
                                "times": [iso_time],
                                "style": {
                                    "fillColor": cm_p(v),
                                    "fillOpacity": 0.45,
                                    "color": "white",
                                    "weight": 0.3,
                                },
                            },
                        }
                    )

    tg_p = TimestampedGeoJson(
        {"type": "FeatureCollection", "features": features_p},
        period="P1D",
        duration="P1D",
        add_last_point=False,
        auto_play=False,
        loop=False,
        max_speed=5,
        loop_button=True,
        date_options="YYYY-MM-DD",
        time_slider_drag_update=True,
    )
    tg_p.add_to(m)

    folium.GeoJson(
        gdf,
        name="Límites Cali",
        show=True,
        style_function=lambda x: {
            "fillColor": "#ffffff",
            "fillOpacity": 0.04,
            "color": "#111111",
            "weight": 1.2,
        },
        highlight_function=lambda x: {
            "weight": 2.5,
            "color": "#000000",
            "fillOpacity": 0.20,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["nombre_barrio", "n_pixeles"],
            aliases=["Barrio:", "No. Píxeles:"],
            localize=True,
            sticky=True,
            style="background-color: white; border-radius: 4px; padding: 6px; font-weight: bold; border: 1px solid #444;",
        ),
    ).add_to(m)

    folium.LayerControl(position="topright", collapsed=False).add_to(m)

    grid_data = {
        "lats": [float(x) for x in lats],
        "lons": [float(x) for x in lons],
        "pad": float(pad),
        "p": [
            [
                [
                    (
                        None
                        if np.isnan(v)
                        else round(float(v), 2)
                    )
                    for v in da_p.isel(time=ti).values[i]
                ]
                for i in range(len(lats))
            ]
            for ti in range(len(time_vals))
        ],
    }

    panel_html = Element(f"""
    <div id="panel-control-ch" style="position: absolute; top: 14px; left: 55px; z-index: 1000; background: white; padding: 12px 16px; border-radius: 8px; box-shadow: 0 3px 10px rgba(0,0,0,0.25); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; width: 240px;">
        <div style="font-weight: bold; margin-bottom: 6px; font-size: 13px; border-bottom: 1px solid #eee; padding-bottom: 4px;">🌧️ CHIRPS Precipitación</div>
        <div style="display: flex; justify-content: space-between; font-size: 11px; font-weight: bold; color: #444;"><span>{vmin_p} mm</span><span>{((vmin_p + vmax_p)/2):.1f} mm</span><span>{vmax_p} mm</span></div>
        <div style="height: 12px; border-radius: 3px; background: linear-gradient(to right, #ffffd9, #c7e9b4, #41b6c4, #225ea8, #081d58); border: 1px solid #aaa; margin: 3px 0;"></div>
        <div style="text-align: center; font-size: 10px; color: #666;">Precipitación diaria (mm/día)</div>
        <div id="box-valor" style="margin-top: 8px; padding: 5px 8px; background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 4px;">
            <div style="font-size: 10px; color: #6c757d; text-transform: uppercase;">Pixel bajo el cursor:</div>
            <div id="txt-valor" style="font-size: 15px; font-weight: bold; color: #0d6efd;">--</div>
        </div>
        <div id="box-barrio" style="margin-top: 8px; padding: 6px 8px; background: #eef4fc; border: 1px solid #d5e4f7; border-radius: 4px; font-size: 11px;">
            <div style="font-weight: bold; color: #1e4273; border-bottom: 1px solid #c8dcf5; padding-bottom: 2px; margin-bottom: 3px;">📍 Barrio Seleccionado:</div>
            <div><b>Nombre:</b> <span id="b-nom">--</span></div>
            <div><b>No. Píxeles:</b> <span id="b-pix">--</span></div>
            <div><b>Promedio Zonal:</b> <span id="b-val" style="font-weight: bold; color: #0055bb;">--</span></div>
        </div>
    </div>
    <script>
    var grid_info_ch = {json.dumps(grid_data)};
    var barrios_info_ch = {json.dumps(barrios_stats)};
    var map_id_ch = "{m.get_name()}";
    var barrioActivo_ch = null;
    var ultimoLatLng_ch = null;
    var b_coords_ch = [[{miny}, {minx}], [{maxy}, {maxx}]];

    function actPixelCh(ll) {{
        var g = grid_info_ch;
        var i_lat = g.lats.findIndex(function(lt){{ return Math.abs(ll.lat - lt) <= g.pad; }});
        var j_lon = g.lons.findIndex(function(ln){{ return Math.abs(ll.lng - ln) <= g.pad; }});
        var el = document.getElementById('txt-valor');
        var map = window[map_id_ch];
        if (el && i_lat !== -1 && j_lon !== -1) {{
            var ti = map && map.timeDimension ? Math.max(0, map.timeDimension.getCurrentTimeIndex()) : 0;
            var v = g.p[ti][i_lat][j_lon];
            el.innerText = (v !== null && v !== undefined) ? v + ' mm' : '--';
        }} else if (el) {{
            el.innerText = '--';
        }}
    }}

    function actBarrioCh(idx) {{
        barrioActivo_ch = idx;
        var b = barrios_info_ch[idx];
        if (!b) return;
        document.getElementById('b-nom').innerText = b.nom;
        document.getElementById('b-pix').innerText = b.n_pix;
        var map = window[map_id_ch];
        var ti = map && map.timeDimension ? Math.max(0, map.timeDimension.getCurrentTimeIndex()) : 0;
        var v = b.p[ti];
        document.getElementById('b-val').innerText = (v !== null && v !== undefined) ? v + ' mm' : '--';
    }}

    function forzarCaliCh() {{
        var map = window[map_id_ch];
        if (!map) return;
        map.invalidateSize();
        map.fitBounds(b_coords_ch);
    }}

    function initChirps() {{
        var map = window[map_id_ch];
        var el = document.getElementById(map_id_ch);
        if (!map || !el) return setTimeout(initChirps, 100);

        forzarCaliCh();

        L.geoJson({gdf[["b_id", "geometry"]].to_json()}, {{
            style: {{ fillColor: '#fff', fillOpacity: 0.01, color: 'transparent' }},
            onEachFeature: function(f, l) {{
                l.on('mouseover', function() {{ actBarrioCh(f.properties.b_id); }});
                l.on('mouseout', function() {{
                    barrioActivo_ch = null;
                    document.getElementById('b-nom').innerText = '--';
                    document.getElementById('b-pix').innerText = '--';
                    document.getElementById('b-val').innerText = '--';
                }});
            }}
        }}).addTo(map);

        if (map.timeDimension) {{
            map.timeDimension.on('timeload timechange', function() {{
                if (barrioActivo_ch !== null) actBarrioCh(barrioActivo_ch);
                if (ultimoLatLng_ch) actPixelCh(ultimoLatLng_ch);
            }});
        }}

        el.addEventListener('mousemove', function(e) {{
            ultimoLatLng_ch = map.mouseEventToLatLng(e);
            actPixelCh(ultimoLatLng_ch);
        }});

        [150, 400, 800].forEach(function(d){{
            setTimeout(forzarCaliCh, d);
        }});
    }}

    window.addEventListener('load', initChirps);
    setTimeout(initChirps, 150);
    </script>
    """)
    m.get_root().html.add_child(panel_html)
    return m