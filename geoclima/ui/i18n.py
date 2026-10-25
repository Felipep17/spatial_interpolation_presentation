"""Textos de la interfaz en español e inglés (i18n).

Uso:
    t("pan.titulo")                    → texto en el idioma activo de la sesión
    t("pan.titulo", "en")              → texto en un idioma concreto (p. ej. dentro de funciones cacheadas)
    t("gen.a_de_b", a=3, b=357)        → con campos de formato («3 de 357»)

Cada clave tiene un espacio de nombres (nav., side., pan., sat., est., bar., mapa., graf., var., …) y
un par (español, inglés). Una clave inexistente lanza KeyError: las pruebas recorren todas las páginas
en ambos idiomas y verifican que cada clave usada en el código esté definida.
"""

import pandas as pd
import streamlit as st

IDIOMAS = ("es", "en")
IDIOMA_DEFECTO = "es"
CLAVE_IDIOMA = "lang"  # clave del selector y parámetro de la URL (?lang=es|en)

_TEXTOS: dict[str, tuple[str, str]] = {
    # ------------------------------------------------------------------ Navegación y barra lateral
    "nav.resumen": ("Resumen", "Summary"),
    "nav.modulos": ("Módulos", "Modules"),
    "nav.panorama": ("Panorama", "Overview"),
    "nav.satelital": ("Fuentes satelitales", "Satellite Sources & Reanalysis"),
    "nav.estaciones": ("Estaciones in situ", "In-situ Weather Stations"),
    "nav.barrio": ("Perfil de barrio", "Neighborhood Profile"),
    "nav.abrir_perfil": ("Abrir perfil de {nombre}", "Open profile of {nombre}"),
    "side.idioma": ("Idioma", "Language"),
    "side.ir_barrio": ("Ir a un barrio", "Go to a neighborhood"),
    "side.buscar": ("Buscar barrio", "Search neighborhood"),
    "side.placeholder": ("Escriba un nombre…", "Type a name…"),
    "side.buscar_ayuda": ("Abre el perfil del barrio con todas las fuentes.",
                          "Opens the neighborhood profile with all sources."),
    "side.periodo": ("Periodo de los datos", "Data period"),
    "side.referencia": ("Referencia espacial", "Spatial reference"),
    "side.sin_definir": ("sin definir", "undefined"),
    "side.creditos": ("Copernicus C3S (AgERA5), CHIRPS v3.0, MSWEP, MODIS vía Google Earth Engine y estaciones in situ.",
                      "Copernicus C3S (AgERA5), CHIRPS v3.0, MSWEP, MODIS via Google Earth Engine and in-situ stations."),
    "app.sin_inputs": ("No se encontró la carpeta 'inputs' en: {ruta}", "The 'inputs' folder was not found at: {ruta}"),
    "app.sin_vector": ("No se encontró la capa vectorial de barrios: {error}",
                       "The neighborhood vector layer was not found: {error}"),
    "app.error_vector": ("No fue posible leer la capa vectorial: {error}", "The vector layer could not be read: {error}"),
    "pie.aliados": ("Proyecto Dengue.IA Cali · Alianza institucional", "Dengue.IA Cali Project · Institutional partnership"),
    "pie.app": ("GeoClima Cali · Análisis espaciotemporal hidrometeorológico",
                "GeoClima Cali · Spatiotemporal hydrometeorological analysis"),
    "pie.lugar": ("Santiago de Cali, Colombia", "Santiago de Cali, Colombia"),

    # ------------------------------------------------------------------ Términos generales
    "gen.barrio": ("Barrio", "Neighborhood"),
    "gen.barrios": ("Barrios", "Neighborhoods"),
    "gen.comuna": ("Comuna", "Commune"),
    "gen.comunas": ("Comunas", "Communes"),
    "gen.estacion": ("Estación", "Station"),
    "gen.estaciones": ("Estaciones", "Stations"),
    "gen.fuentes": ("Fuentes", "Sources"),
    "gen.fuentes_raster": ("Fuentes raster", "Raster sources"),
    "gen.periodo": ("Periodo", "Period"),
    "gen.dias": ("Días", "Days"),
    "gen.n_dias": ("{n} días", "{n} days"),
    "gen.n_semanas": ("{n} semanas", "{n} weeks"),
    "gen.a_de_b": ("{a} de {b}", "{a} of {b}"),
    "gen.a_de_b_pct": ("{a} de {b} ({pct} %)", "{a} of {b} ({pct} %)"),
    "gen.rango_a_b": ("{a} a {b}", "{a} to {b}"),
    "gen.mediana": ("mediana {n}", "median {n}"),
    "gen.mediana_max": ("mediana {m} · máx. {x}", "median {m} · max. {x}"),
    "gen.rango_diario": ("rango diario", "daily range"),
    "gen.sin_datos": ("sin datos", "no data"),
    "gen.resolucion": ("Resolución", "Resolution"),
    "gen.resolucion_espacial": ("Resolución espacial", "Spatial resolution"),
    "gen.resolucion_de": ("Resolución {r}", "Resolution {r}"),
    "gen.series_diarias": ("Series diarias", "Daily series"),
    "gen.promedio_zonal_todos": ("Promedio de las estadísticas zonales de todos los barrios.",
                                 "Mean of the zonal statistics of all neighborhoods."),
    "gen.promedio_series_todos": ("Promedio de las series zonales de todos los barrios.",
                                  "Mean of the zonal series of all neighborhoods."),
    "gen.cargando_fuentes": ("Cargando fuentes…", "Loading sources…"),
    "gen.vs_cali": ("vs. Cali", "vs. Cali"),
    "gen.sin_fuentes_raster": ("Sin fuentes raster", "No raster sources"),
    "gen.procesando_estaciones": ("Procesando registros de estaciones…", "Processing station records…"),

    # ------------------------------------------------------------------ Comunas (valores de datos traducidos)
    "comuna.n": ("Comuna {n}", "Commune {n}"),
    "comuna.expansion": ("Área de expansión", "Urban expansion area"),
    "comuna.sin": ("Sin comuna", "No commune"),
    "comuna.fuera": ("Fuera del perímetro urbano", "Outside the urban perimeter"),
    "comuna.toda": ("Toda Cali", "All of Cali"),

    # ------------------------------------------------------------------ Variables, agregaciones e indicadores
    "var.precipitacion": ("Precipitación", "Precipitation"),
    "var.tmin": ("Temperatura mínima", "Minimum Temperature"),
    "var.tmax": ("Temperatura máxima", "Maximum Temperature"),
    "var.hr": ("Humedad relativa", "Relative Humidity"),
    "var.viento": ("Velocidad del viento", "Wind Speed"),
    "var.radiacion": ("Radiación solar", "Solar Radiation"),
    "var.ndvi": ("NDVI", "NDVI"),
    "var.ndwi": ("NDWI", "NDWI"),
    "var.celdas_despejadas": ("Celdas sin nubes", "Cloud-free cells"),
    "var_corta.precipitacion": ("Precipitación", "Precipitation"),
    "var_corta.tmin": ("T. mínima", "Min. temp."),
    "var_corta.tmax": ("T. máxima", "Max. temp."),
    "var_corta.hr": ("Humedad", "Humidity"),
    "var_corta.viento": ("Viento", "Wind"),
    "var_corta.radiacion": ("Radiación", "Radiation"),
    "var_corta.lluvia": ("Lluvia", "Rainfall"),
    "var_corta.tmax_mapa": ("T. máx.", "Max. temp."),
    "var_corta.ndvi": ("NDVI", "NDVI"),
    "var_corta.ndwi": ("NDWI", "NDWI"),
    "agg.acum_semanal": ("acumulado semanal", "weekly total"),
    "agg.media_semanal": ("media semanal", "weekly mean"),
    "agg.diaria": ("diaria", "daily"),
    "ind.lluvia_acumulada": ("Lluvia acumulada", "Accumulated Rainfall"),
    "modo.media": ("media", "mean"),
    "modo.suma": ("suma", "total"),

    # ------------------------------------------------------------------ Fuentes raster
    "fuente.C3S.variables": ("Humedad relativa · Temperatura máxima", "Relative humidity · Maximum temperature"),
    "fuente.C3S.desc": ("Indicadores agrometeorológicos diarios derivados del reanálisis ERA5 (0.1°).",
                        "Daily agrometeorological indicators derived from the ERA5 reanalysis (0.1°)."),
    "fuente.CHIRPS.variables": ("Precipitación", "Precipitation"),
    "fuente.CHIRPS.desc": ("Precipitación diaria cuasi-global combinando satélite y estaciones (0.05°).",
                           "Quasi-global daily precipitation blending satellite and station data (0.05°)."),
    "fuente.MSWEP.variables": ("Precipitación", "Precipitation"),
    "fuente.MSWEP.desc": ("Precipitación diaria multi-fuente ponderada: satélite, reanálisis y pluviómetros (0.1°).",
                          "Daily multi-source weighted-ensemble precipitation: satellite, reanalysis and rain gauges "
                          "(0.1°)."),
    "fuente.GEE.variables": ("NDVI · NDWI", "NDVI · NDWI"),
    "fuente.GEE.desc": ("NDVI y NDWI diarios de MOD09GA promediados a una grilla de 0.009° (~1 km), sin nubes.",
                        "Daily cloud-masked NDVI and NDWI from MOD09GA, averaged onto a 0.009° (~1 km) grid."),

    # ------------------------------------------------------------------ Fechas
    "fecha.meses": ("ene feb mar abr may jun jul ago sep oct nov dic", "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec"),

    # ------------------------------------------------------------------ Mapas (Folium / Leaflet)
    "mapa.calles": ("Calles · OpenStreetMap", "Streets · OpenStreetMap"),
    "mapa.satelite": ("Satélite · Esri", "Satellite · Esri"),
    "mapa.sat_attr": ("Imagen &copy; Esri, Maxar, Earthstar Geographics",
                      "Imagery &copy; Esri, Maxar, Earthstar Geographics"),
    "mapa.pantalla_completa": ("Pantalla completa", "Full screen"),
    "mapa.salir_pantalla": ("Salir de pantalla completa", "Exit full screen"),
    "mapa.limites_barrio": ("Límites de barrio", "Neighborhood boundaries"),
    "mapa.limites_comuna": ("Límites de comuna", "Commune boundaries"),
    "mapa.pixeles": ("Píxeles", "Pixels"),
    "mapa.celdas_gee": ("Celdas GEE (1 km)", "GEE cells (1 km)"),
    "mapa.celdas_1km": ("Celdas 1 km", "1 km cells"),
    "mapa.puesto": ("Puesto", "Rank"),
    "mapa.sin_dato": ("sin dato", "no data"),
    "mapa.ambito": ("Ámbito", "Scope"),
    "mapa.barrio_sel": ("Barrio seleccionado", "Selected neighborhood"),
    "mapa.lectura_pixel": ("Píxel bajo el cursor", "Pixel under cursor"),
    "mapa.lectura_pix_int": ("Píxeles intersectados", "Intersected pixels"),
    "mapa.lectura_zonal": ("Promedio zonal", "Zonal mean"),
    "mapa.ocultar": ("Ocultar", "Hide"),
    "mapa.precip_diaria": ("Precipitación diaria", "Daily precipitation"),
    "mapa.nota_escala": ("Escala p2–p98 · extremos recortados", "p2–p98 scale · extremes clipped"),
    "mapa.nota_escala_barrios": ("Escala p2–p98 entre barrios", "p2–p98 scale across neighborhoods"),
    "mapa.pista_clic": ("Clic en un barrio para ver su ficha.", "Click a neighborhood to see its summary."),
    "mapa.grilla": ("Grilla 1 km", "1 km grid"),
    "mapa.grilla_agera5": ("Grilla 11 km (AgERA5)", "11 km grid (AgERA5)"),
    "mapa.celda": ("Celda", "Cell"),
    "mapa.centro": ("Centro", "Center"),
    "mapa.nombres": ("Nombres", "Names"),
    "mapa.barrios_toca": ("Barrios que toca", "Neighborhoods touched"),
    "mapa.pct_cali": ("% dentro de Cali", "% inside Cali"),
    "mapa.reproducir": ("Reproducir", "Play"),
    "mapa.pausar": ("Pausar", "Pause"),
    "mapa.anterior": ("Día anterior", "Previous day"),
    "mapa.siguiente": ("Día siguiente", "Next day"),
    "mapa.dia": ("Día", "Day"),
    "mapa.de": ("de", "of"),
    "mapa.n_dias": ("{n} días con dato", "{n} days with data"),
    "mapa.valor_dia": ("Valor del día", "Value on this day"),
    "mapa.puesto_dia": ("Puesto del día", "Rank on this day"),
    "mapa.promedio_dia": ("Promedio Cali del día", "Cali average on this day"),
    "mapa.nota_escala_dias": ("Escala p2–p98 de todos los días y barrios", "p2–p98 scale across all days and neighborhoods"),

    # ------------------------------------------------------------------ Gráficos (Plotly)
    "graf.media": ("Media", "Mean"),
    "graf.promedio_cali": ("Promedio Cali", "Cali average"),
    "graf.rango_habitual": ("Rango habitual (p10–p90)", "Usual range (p10–p90)"),
    "graf.mediana_hist": ("Mediana histórica", "Historical median"),
    "graf.semana_epi": ("Semana epidemiológica", "Epidemiological Week"),
    "graf.calendario_hover": ("Año %{y} · semana %{x}", "Year %{y} · week %{x}"),
    "graf.r_6m": ("6M", "6M"),
    "graf.r_1a": ("1A", "1Y"),
    "graf.r_3a": ("3A", "3Y"),
    "graf.r_todo": ("Todo", "All"),

    # ------------------------------------------------------------------ Descargas y componentes
    "dl.csv": ("Descargar CSV", "Download CSV"),
    "dl.geojson": ("GeoJSON", "GeoJSON"),
    "dl.geojson_ayuda": ("Polígonos de los barrios con las columnas de la tabla (EPSG:4326), listos para QGIS o ArcGIS.",
                         "Neighborhood polygons with the table columns (EPSG:4326), ready for QGIS or ArcGIS."),
    "dl.html": ("Mapa HTML", "HTML map"),
    "dl.html_ayuda": ("Visor interactivo completo en un solo archivo: se abre sin conexión a la app.",
                      "Full interactive viewer in a single file; it opens without the app."),

    # ------------------------------------------------------------------ Explorador de barrios
    "exp.indicador": ("Indicador", "Indicator"),
    "exp.ambito_ayuda": ("Enfoca el mapa y el ranking en una comuna.", "Focuses the map and ranking on one commune."),
    "exp.puesto_meta": ("Puesto {p} de {n} · {dif} vs. promedio de Cali", "Rank {p} of {n} · {dif} vs. Cali average"),
    "exp.sin_dato": ("Sin dato en el periodo", "No data in the period"),
    "exp.pista": ("Haga clic en un barrio del mapa para ver su valor, su puesto y abrir su perfil.",
                  "Click a neighborhood on the map to see its value and rank, and to open its profile."),
    "exp.mas_altos": ("Valores más altos", "Highest values"),
    "exp.mas_bajos": ("Valores más bajos", "Lowest values"),
    "exp.modo": ("Vista", "View"),
    "exp.modo_periodo": ("Periodo", "Period"),
    "exp.modo_animacion": ("Animación diaria", "Daily animation"),
    "exp.modo_ayuda": ("Periodo: un valor por barrio para todo el periodo, con ranking. Animación diaria: el valor de "
                       "cada día, con reproducción.",
                       "Period: one value per neighborhood for the whole period, with ranking. Daily animation: each "
                       "day's value, with playback."),
    "exp.animacion_pista": ("Pulse ▶ para recorrer los días o mueva el deslizador; pase el cursor sobre un barrio para "
                            "leer su valor y su puesto ese día. El mapa abre en el día de mayor promedio.",
                            "Press ▶ to step through the days or drag the slider; hover over a neighborhood to read "
                            "its value and rank on that day. The map opens on the day with the highest average."),
    "exp.serie_ciudad": ("Promedio de los barrios por día", "Neighborhood average by day"),
    "exp.dias_omitidos": ("Se omiten {n} días sin ningún dato (nubes).", "{n} days without any data (clouds) are "
                                                                        "skipped."),
    "exp.sin_dias": ("No hay días con dato para animar.", "There are no days with data to animate."),
    "exp.empates": ("Fuente gruesa: muchos barrios comparten la misma celda y empatan en el ranking.",
                    "Coarse source: many neighborhoods share the same cell and tie in the ranking."),

    # ------------------------------------------------------------------ Panorama
    "pan.eyebrow": ("Proyecto Dengue.IA Cali", "Dengue.IA Cali Project"),
    "pan.titulo": ("Panorama hidrometeorológico de Cali", "Hydrometeorological Overview of Cali"),
    "pan.subtitulo": ("Cómo se distribuyen las variables entre barrios y comunas, qué cubre cada fuente y cuánto "
                      "concuerdan los productos de precipitación.",
                      "How variables are distributed across neighborhoods and communes, what each source covers, "
                      "and how closely the precipitation products agree."),
    "pan.preparando": ("Preparando el panorama de fuentes…", "Preparing the source overview…"),
    "pan.sin_fuentes": ("Sin fuentes procesadas", "No processed sources"),
    "pan.sin_fuentes_cuerpo": ("Agregue NetCDF en inputs/raster para ver el panorama.",
                               "Add NetCDF files to inputs/raster to see the overview."),
    "pan.kpi_barrios": ("Barrios analizados", "Neighborhoods analyzed"),
    "pan.kpi_barrios_delta": ("{n} comunas + área de expansión", "{n} communes + expansion area"),
    "pan.kpi_barrios_unidad": ("Unidad de análisis zonal", "Zonal analysis unit"),
    "pan.kpi_resolucion": ("{a} a {b} km de resolución", "{a} to {b} km resolution"),
    "pan.kpi_estaciones": ("Estaciones in situ", "In-situ stations"),
    "pan.kpi_concordancia": ("Concordancia CHIRPS–MSWEP", "CHIRPS–MSWEP agreement"),
    "pan.kpi_concordancia_delta": ("Lluvia diaria promedio", "Mean daily rainfall"),
    "pan.kpi_concordancia_ayuda": ("Correlación de Pearson entre las series diarias de precipitación promedio de "
                                   "los barrios.",
                                   "Pearson correlation between the daily series of neighborhood-mean precipitation."),
    "pan.mapa": ("Mapa de barrios", "Neighborhood map"),
    "pan.mapa_cap": ("Valor del periodo en cada barrio (media diaria; la lluvia es el acumulado). Elija un indicador "
                     "y, si quiere, una comuna.",
                     "Period value for each neighborhood (daily mean; rainfall is the accumulated total). Choose an "
                     "indicator and, optionally, a commune."),
    "pan.por_comuna": ("{ind} por comuna", "{ind} by commune"),
    "pan.por_comuna_cap": ("Promedio simple de los barrios de cada comuna; la línea punteada es el promedio de Cali.",
                           "Simple mean of each commune's neighborhoods; the dotted line is the Cali average."),
    "pan.fuentes": ("Fuentes de datos", "Data sources"),
    "pan.fuentes_cap": ("Resolución, periodo y cuántas celdas de cada grilla cubren realmente a Cali.",
                        "Resolution, period and how many cells of each grid actually cover Cali."),
    "pan.celdas_cali": ("Celdas sobre Cali", "Cells over Cali"),
    "pan.celdas_barrio": ("Celdas por barrio", "Cells per neighborhood"),
    "pan.mas_de_una": ("Barrios con más de una celda", "Neighborhoods with >1 cell"),
    "pan.cobertura": ("Cobertura temporal de las fuentes raster", "Temporal coverage of the raster sources"),
    "pan.nota_otro_mes": ("Las fuentes en naranja cubren otro mes: sus valores no se comparan directamente con el resto.",
                          "Sources in orange cover a different month: their values are not directly comparable "
                          "with the rest."),
    "pan.nota_estaciones": ("Las estaciones cubren {periodo}, sin traslape con el periodo satelital.",
                            "Stations cover {periodo}, with no overlap with the satellite period."),
    "pan.distingue": ("¿Cuánto distingue cada fuente entre barrios?", "How well does each source tell neighborhoods apart?"),
    "pan.distingue_cap": ("Una fuente gruesa asigna el mismo valor a muchos barrios vecinos; la grilla de 1 km los "
                          "separa.",
                          "A coarse source assigns the same value to many adjacent neighborhoods; the 1 km grid "
                          "separates them."),
    "pan.celdas_tocan": ("Celdas de la grilla que tocan Cali", "Grid cells touching Cali"),
    "pan.una_celda": ("Barrios que caen en una sola celda", "Neighborhoods within a single cell"),
    "pan.chirps_mswep": ("Precipitación: CHIRPS frente a MSWEP", "Precipitation: CHIRPS vs. MSWEP"),
    "pan.chirps_mswep_cap": ("Promedio diario de los barrios · {periodo}.", "Daily neighborhood mean · {periodo}."),
    "pan.acum": ("Acumulado {f}", "{f} total"),
    "pan.diferencia": ("Diferencia (MSWEP − CHIRPS)", "Difference (MSWEP − CHIRPS)"),
    "pan.dias_1mm": ("Días ≥ 1 mm", "Days ≥ 1 mm"),
    "pan.dia_lluvioso": ("Día más lluvioso", "Wettest day"),
    "pan.correlacion": ("Correlación diaria", "Daily correlation"),
    "pan.mae": ("Error absoluto medio", "Mean absolute error"),
    "pan.mm_dia": ("{v} mm/día", "{v} mm/day"),
    "pan.no_independientes": ("Las dos fuentes no son independientes: CHIRPS y MSWEP incorporan pluviómetros, por lo "
                              "que la concordancia no equivale a validación.",
                              "The two sources are not independent: both CHIRPS and MSWEP ingest rain-gauge data, so "
                              "agreement does not amount to validation."),
    "pan.explorar": ("Explorar módulos", "Explore modules"),
    "pan.mod_fuentes": ("Visor diario por píxel, mapa del periodo por barrio y tabla descargable de cada producto.",
                        "Daily per-pixel viewer, period map by neighborhood and a downloadable table for each "
                        "product."),
    "pan.mod_estaciones": ("Series por semana epidemiológica, ciclo anual, calendario de datos y grillas de 1 km y "
                           "11 km.",
                           "Series by epidemiological week, annual cycle, data calendar and 1 km and 11 km grids."),
    "pan.mod_barrio": ("Todas las fuentes para un barrio, su posición frente a Cali y comparación con otros barrios.",
                       "All sources for one neighborhood, its position relative to Cali and comparison with other "
                       "neighborhoods."),

    # ------------------------------------------------------------------ Fuentes satelitales
    "sat.titulo": ("Fuentes satelitales y reanálisis", "Satellite Sources & Reanalysis"),
    "sat.subtitulo": ("Exploración espaciotemporal de productos raster y estadísticas zonales por barrio.",
                      "Spatiotemporal exploration of raster products and zonal statistics by neighborhood."),
    "sat.eyebrow": ("Módulo 01 · Raster", "Module 01 · Raster"),
    "sat.sin_carpetas": ("No se encontraron carpetas en inputs/raster.", "No folders were found in inputs/raster."),
    "sat.fuente": ("Fuente", "Source"),
    "sat.documentacion": ("Documentación", "Documentation"),
    "sat.vista": ("Vista del mapa", "Map view"),
    "sat.vista_diario": ("Visor diario", "Daily viewer"),
    "sat.vista_periodo": ("Mapa por barrio", "Map by neighborhood"),
    "sat.vista_ayuda": ("Visor diario: cada píxel de la grilla día a día. Mapa por barrio: valor del periodo de cada "
                        "barrio, con ranking.",
                        "Daily viewer: every grid pixel, day by day. Map by neighborhood: the period value of each "
                        "neighborhood, with ranking."),
    "sat.preparando": ("Preparando visor {f}…", "Preparing {f} viewer…"),
    "sat.ayuda_visor": ("Desplace el cursor sobre el mapa para leer el píxel y el promedio zonal del barrio. Use el "
                        "control temporal inferior para recorrer los días.",
                        "Hover over the map to read the pixel value and the neighborhood's zonal mean. Use the time "
                        "control at the bottom to step through the days."),
    "sat.ayuda_visor_gee": ("Las celdas vacías corresponden a nubes o sombras enmascaradas ese día. Desplace el cursor "
                            "para leer la celda y el promedio zonal del barrio.",
                            "Empty cells are clouds or shadows masked on that day. Hover to read the cell value and "
                            "the neighborhood's zonal mean."),
    "sat.fila_pista": ("Seleccione una fila para abrir el perfil del barrio.",
                       "Select a row to open the neighborhood profile."),
    "sat.grilla": ("Grilla de la fuente", "Source grid"),
    "sat.grilla_cap": ("Celdas del archivo frente a los barrios de Cali (criterio: la celda intersecta el barrio).",
                       "File cells versus Cali's neighborhoods (criterion: the cell intersects the neighborhood)."),
    "sat.celdas_extent": ("Celdas en el extent del archivo", "Cells in the file extent"),
    "sat.celdas_tocan": ("Celdas que tocan Cali", "Cells touching Cali"),
    "sat.celdas_tocan_val": ("{n} ({pct} % del extent)", "{n} ({pct} % of the extent)"),
    "sat.celdas_50": ("Celdas con ≥ 50 % dentro de Cali", "Cells with ≥ 50 % inside Cali"),
    "sat.pixeles_barrio": ("Píxeles por barrio", "Pixels per neighborhood"),
    "sat.celdas1km_barrio": ("Celdas 1 km por barrio", "1 km cells per neighborhood"),
    "sat.barrios_una_celda": ("Barrios dentro de una sola celda", "Neighborhoods within a single cell"),
    "sat.resumen": ("Resumen por barrio", "Summary by neighborhood"),
    "sat.resumen_cap": ("Estadísticos del periodo sobre la serie zonal diaria; ordene por cualquier columna o filtre "
                        "por comuna.",
                        "Period statistics from the daily zonal series; sort by any column or filter by commune."),
    "sat.resumen_cap_gee": ("Estadísticos del periodo sobre los días con píxeles despejados.",
                            "Period statistics over the days with cloud-free pixels."),
    "sat.incompletos": ("Archivos incompletos", "Incomplete files"),
    "sat.incompletos_cuerpo": ("Se requieren los NetCDF de humedad relativa y temperatura máxima.",
                               "The relative humidity and maximum temperature NetCDF files are required."),
    "sat.kpi_hr": ("Humedad relativa media", "Mean relative humidity"),
    "sat.kpi_tmax": ("Temperatura máxima media", "Mean maximum temperature"),
    "sat.kpi_ultimo": ("Último día · Tmax", "Last day · Tmax"),
    "sat.vs_media_periodo": ("vs. media del periodo", "vs. period mean"),
    "sat.kpi_cobertura": ("Cobertura", "Coverage"),
    "sat.kpi_acum": ("Acumulado del periodo", "Period total"),
    "sat.kpi_acum_ayuda": ("Suma de la precipitación diaria promedio de los barrios.",
                           "Sum of the daily neighborhood-mean precipitation."),
    "sat.kpi_dias_lluvia": ("Días con lluvia", "Rainy days"),
    "sat.kpi_dias_lluvia_delta": ("{pct} % del periodo", "{pct} % of the period"),
    "sat.kpi_dias_lluvia_ayuda": ("Días con promedio de barrios ≥ 1 mm.", "Days with a neighborhood mean ≥ 1 mm."),
    "sat.kpi_max_diario": ("Máximo diario", "Daily maximum"),
    "sat.grilla_nativa": ("Grilla nativa", "Native grid"),
    "sat.kpi_ndvi": ("NDVI medio", "Mean NDVI"),
    "sat.kpi_ndwi": ("NDWI medio", "Mean NDWI"),
    "sat.kpi_ndvi_ayuda": ("Promedio de las series zonales de todos los barrios (días sin nubes).",
                           "Mean of all neighborhoods' zonal series (cloud-free days)."),
    "sat.kpi_dias_datos": ("Días con datos", "Days with data"),
    "sat.kpi_despejadas": ("{pct} % de celdas despejadas", "{pct} % cloud-free cells"),
    "sat.kpi_dias_datos_ayuda": ("Un día cuenta si al menos un barrio tiene píxeles despejados.",
                                 "A day counts if at least one neighborhood has cloud-free pixels."),
    "sat.kpi_grilla": ("Grilla {ny} × {nx} celdas", "{ny} × {nx} cell grid"),
    "sat.series_gee_cap": ("Promedio de las estadísticas zonales de todos los barrios; los huecos son días nublados.",
                           "Mean of all neighborhoods' zonal statistics; gaps are cloudy days."),
    "sat.faltante": ("{f}: aún no hay datos descargados", "{f}: no data downloaded yet"),
    "sat.faltante_cuerpo": ("Ejecute la descarga desde la raíz del proyecto; el periodo se toma del archivo de CHIRPS.",
                            "Run the download from the project root; the period is taken from the CHIRPS file."),
    "sat.sin_archivos": ("{f} sin archivos", "{f} has no files"),
    "sat.sin_archivos_cuerpo": ("La carpeta existe pero aún no contiene NetCDF ni GeoTIFF para visualizar.",
                                "The folder exists but does not contain any NetCDF or GeoTIFF files to display yet."),
    "col.pixeles": ("Píxeles", "Pixels"),
    "col.hr_media": ("HR media (%)", "Mean RH (%)"),
    "col.hr_diaria": ("HR diaria", "Daily RH"),
    "col.tmax_media": ("Tmax media (°C)", "Mean Tmax (°C)"),
    "col.tmax_max": ("Tmax máx. (°C)", "Max. Tmax (°C)"),
    "col.tmax_diaria": ("Tmax diaria", "Daily Tmax"),
    "col.acumulado": ("Acumulado (mm)", "Total (mm)"),
    "col.max_diario": ("Máx. diario (mm)", "Daily max. (mm)"),
    "col.dias_1mm": ("Días ≥ 1 mm", "Days ≥ 1 mm"),
    "col.precip_diaria": ("Precipitación diaria", "Daily precipitation"),
    "col.celdas_1km": ("Celdas 1 km", "1 km cells"),
    "col.dias_validos": ("Días válidos", "Valid days"),
    "col.ndvi_medio": ("NDVI medio", "Mean NDVI"),
    "col.ndvi_diario": ("NDVI diario", "Daily NDVI"),
    "col.ndwi_medio": ("NDWI medio", "Mean NDWI"),
    "col.ndwi_diario": ("NDWI diario", "Daily NDWI"),
    "col.archivo": ("Archivo", "File"),
    "col.formato": ("Formato", "Format"),
    "col.tamano": ("Tamaño (MB)", "Size (MB)"),

    # ------------------------------------------------------------------ Estaciones
    "est.titulo": ("Red de estaciones meteorológicas", "Weather Station Network"),
    "est.subtitulo": ("Series temporales in situ agregadas por semana, con control de completitud por estación.",
                      "In-situ time series aggregated by week, with per-station completeness control."),
    "est.subtitulo_corto": ("Series temporales in situ.", "In-situ time series."),
    "est.eyebrow": ("Módulo 02 · In situ", "Module 02 · In situ"),
    "est.agregacion": ("Agregación", "Aggregation"),
    "est.semanal": ("semanal", "weekly"),
    "est.sin_datos": ("Sin datos de estaciones", "No station data"),
    "est.sin_csv": ("No se encontró {f} en la carpeta inputs.", "{f} was not found in the inputs folder."),
    "est.variable": ("Variable", "Variable"),
    "est.sin_registros": ("Sin registros", "No records"),
    "est.sin_registros_cuerpo": ("Ninguna estación tiene datos válidos de {v}.", "No station has valid {v} data."),
    "est.estacion_ayuda": ("También puede seleccionarla con un clic en el mapa o en la tabla de la red. El enlace de la "
                           "página conserva la estación y la variable.",
                           "You can also select it by clicking the map or the network table. The page link keeps "
                           "the station and the variable."),
    "est.kpi_ultima": ("Última semana registrada", "Last recorded week"),
    "est.vs_media_hist": ("vs. media histórica", "vs. historical mean"),
    "est.kpi_ultima_ayuda": ("Semana que cierra el {fecha}. Micro-gráfico: últimas 26 semanas.",
                             "Week ending {fecha}. Sparkline: last 26 weeks."),
    "est.kpi_media": ("Media histórica", "Historical mean"),
    "est.kpi_media_ayuda": ("{agg}. Micro-gráfico: media por año.", "{agg}. Sparkline: mean per year."),
    "est.kpi_max": ("Máximo semanal", "Weekly maximum"),
    "est.semana_del": ("Semana del {fecha}", "Week of {fecha}"),
    "est.kpi_completitud": ("Completitud", "Completeness"),
    "est.kpi_completitud_delta": ("{a} de {b} semanas", "{a} of {b} weeks"),
    "est.kpi_completitud_ayuda": ("Semanas con dato sobre las semanas del periodo de operación. Micro-gráfico: % por "
                                  "año.",
                                  "Weeks with data over the weeks of the operating period. Sparkline: % per year."),
    "est.red": ("Red de sensores", "Sensor network"),
    "est.red_cap": ("Color: media de {v} por estación.", "Color: mean {v} per station."),
    "est.grilla_toggle": ("Grilla 1 km (GEE)", "1 km grid (GEE)"),
    "est.grilla_ayuda": ("Celdas de 0.009° (~1 km), las mismas de los NetCDF de GEE. Pase el cursor sobre una celda "
                         "para ver su detalle.",
                         "0.009° (~1 km) cells, the same as in the GEE NetCDF files. Hover over a cell to see its "
                         "details."),
    "est.grilla_agera5_toggle": ("Grilla 11 km (AgERA5)", "11 km grid (AgERA5)"),
    "est.grilla_agera5_ayuda": ("Celdas de 0.1° (~11 km), las mismas de los NetCDF de AgERA5 (C3S). Pase el cursor "
                                "sobre una celda para ver su detalle; con la grilla de 1 km activa, se ve el de la "
                                "celda de 1 km.",
                                "0.1° (~11 km) cells, the same as in the AgERA5 (C3S) NetCDF files. Hover over a cell "
                                "to see its details; with the 1 km grid on, the 1 km cell details are shown."),
    "est.grilla_agera5_sin": ("No hay NetCDF de AgERA5 en inputs/raster/C3S.",
                              "There is no AgERA5 NetCDF in inputs/raster/C3S."),
    "est.leyenda": ("Media por estación · {v}", "Station mean · {v}"),
    "est.fuera_perimetro": ("fuera del perímetro urbano", "outside the urban perimeter"),
    "est.sin_suficientes": ("Sin datos suficientes", "Insufficient data"),
    "est.sin_suficientes_cuerpo": ("No hay registros para graficar esta serie.",
                                   "There are no records to plot this series."),
    "est.estacional": ("Comportamiento estacional", "Seasonal behavior"),
    "est.estacional_cap": ("{v} por semana epidemiológica en {e}: rango habitual de todos los años, el año elegido y "
                           "el calendario completo de registros.",
                           "{v} by epidemiological week at {e}: the usual range across all years, the selected year "
                           "and the full record calendar."),
    "est.anio": ("Año a comparar", "Year to compare"),
    "est.anio_ayuda": ("Se dibuja sobre el rango habitual (percentiles 10–90 de todos los años).",
                       "Drawn over the usual range (10th–90th percentiles across all years)."),
    "est.anio_n": ("Año {a}", "Year {a}"),
    "est.calendario": ("Calendario de registros", "Record calendar"),
    "est.calendario_cap": ("Cada celda es una semana epidemiológica (domingo a sábado); en blanco, semanas sin dato.",
                           "Each cell is one epidemiological week (Sunday to Saturday); blank cells are weeks without "
                           "data."),
    "est.origen": ("Origen de la grilla", "Grid origin"),
    "est.origen_gee": ("NetCDF de GEE", "GEE NetCDF"),
    "est.origen_teorica": ("Teórica (aún sin descarga GEE)", "Theoretical (GEE not downloaded yet)"),
    "est.origen_agera5": ("NetCDF de AgERA5 (C3S)", "AgERA5 (C3S) NetCDF"),
    "est.tamano_celda": ("Tamaño de celda", "Cell size"),
    "est.celdas_extension": ("Celdas en la extensión", "Cells in the extent"),
    "est.celdas_estacion": ("Celdas con estación", "Cells with a station"),
    "est.max_est_celda": ("Máx. estaciones en una celda", "Max. stations in one cell"),
    "est.rurales": ("Estaciones en celdas sin barrios (rurales)", "Stations in cells without neighborhoods (rural)"),
    "est.celdas_con_est": ("Celdas con estaciones ({n})", "Cells with stations ({n})"),
    "est.pct_en_cali": ("% en Cali", "% in Cali"),
    "est.resumen": ("Resumen de la red", "Network summary"),
    "est.resumen_cap": ("Seleccione una fila para enfocar la estación y ver su barrio.",
                        "Select a row to focus the station and see its neighborhood."),
    "est.barrio_ayuda": ("Barrio donde está la estación (— si es rural).",
                         "Neighborhood where the station is located (— if rural)."),
    "est.col_media": ("Media ({u})", "Mean ({u})"),
    "est.col_maximo": ("Máximo ({u})", "Maximum ({u})"),
    "est.col_semanas": ("Semanas con dato", "Weeks with data"),
    "est.col_ultimo": ("Último registro", "Last record"),
    "est.col_52": ("Últimas 52 semanas", "Last 52 weeks"),

    # ------------------------------------------------------------------ Perfil de barrio
    "bar.titulo": ("Perfil de barrio", "Neighborhood Profile"),
    "bar.subtitulo": ("Todas las fuentes para un barrio: posición frente a los demás barrios, series diarias, celdas "
                      "que lo cubren, vecinos y estaciones cercanas.",
                      "All sources for one neighborhood: its position relative to the others, daily series, covering "
                      "cells, neighbors and nearby stations."),
    "bar.eyebrow": ("Módulo 03 · Barrio", "Module 03 · Neighborhood"),
    "bar.placeholder": ("Escriba para buscar…", "Type to search…"),
    "bar.selector_ayuda": ("Escriba parte del nombre, o haga clic en un barrio del mapa. El enlace de la página conserva "
                           "el barrio.",
                           "Type part of the name, or click a neighborhood on the map. The page link keeps the "
                           "neighborhood."),
    "bar.comparar": ("Comparar con", "Compare with"),
    "bar.comparar_placeholder": ("Hasta 2 barrios…", "Up to 2 neighborhoods…"),
    "bar.comparar_ayuda": ("Se agregan a las series y a la posición frente a Cali.",
                           "They are added to the series and to the position chart."),
    "bar.mapa_cap": ("Clic en otro barrio para abrir su perfil. Línea discontinua: celdas de 1 km; puntos grises: las 5 "
                     "estaciones más cercanas.",
                     "Click another neighborhood to open its profile. Dashed lines: 1 km cells; gray dots: the 5 "
                     "nearest stations."),
    "bar.ficha": ("Ficha del barrio", "Neighborhood summary"),
    "bar.area": ("Área", "Area"),
    "bar.centro": ("Centro", "Centroid"),
    "bar.celdas_gee": ("Celdas GEE de 1 km", "1 km GEE cells"),
    "bar.pixeles_fuente": ("Píxeles {f} ({r})", "{f} pixels ({r})"),
    "bar.estacion_cercana": ("Estación más cercana", "Nearest station"),
    "bar.vecinos": ("Barrios vecinos ({n})", "Neighboring Neighborhoods ({n})"),
    "bar.vecinos_ayuda": ("Barrios que comparten límite. Elija uno para abrir su perfil.",
                          "Neighborhoods sharing a boundary. Choose one to open its profile."),
    "bar.sin_fuentes_cuerpo": ("No hay fuentes procesadas para construir el perfil.",
                               "There are no processed sources to build the profile."),
    "bar.indicadores": ("Indicadores del periodo", "Period indicators"),
    "bar.indicadores_cap": ("Valor del barrio, diferencia frente al promedio de los barrios y puesto (1 = valor más "
                            "alto).",
                            "Neighborhood value, difference from the neighborhood average and rank (1 = highest "
                            "value)."),
    "bar.vs_cali_puesto": ("vs. Cali · puesto {p} de {n}", "vs. Cali · rank {p} of {n}"),
    "bar.ayuda_suma": ("Suma del periodo {periodo}.", "Period total, {periodo}."),
    "bar.ayuda_media": ("Media del periodo {periodo}.", "Period mean, {periodo}."),
    "bar.col_fuente": ("Fuente", "Source"),
    "bar.col_indicador": ("Indicador", "Indicator"),
    "bar.col_unidad": ("Unidad", "Unit"),
    "bar.col_promedio": ("Promedio Cali", "Cali average"),
    "bar.col_diferencia": ("Diferencia", "Difference"),
    "bar.col_puesto": ("Puesto", "Rank"),
    "bar.col_de": ("De", "Of"),
    "bar.posicion": ("Posición frente a los demás barrios", "Position relative to other neighborhoods"),
    "bar.posicion_cap": ("Cada punto gris es un barrio; la línea punteada es el promedio de Cali.",
                         "Each gray dot is a neighborhood; the dotted line is the Cali average."),
    "bar.tabla": ("Tabla de indicadores", "Indicator table"),
    "bar.series_cap": ("Barrio en azul frente al promedio de todos los barrios (gris).",
                       "Neighborhood in blue versus the mean of all neighborhoods (gray)."),
    "bar.series_cap_cmp": ("Barrio en azul y barrios comparados frente al promedio de todos los barrios (gris).",
                           "Neighborhood in blue and compared neighborhoods versus the mean of all neighborhoods "
                           "(gray)."),
    "bar.nota_gee": ("NDVI/NDWI: solo hay dato en días despejados; la línea punteada une esos días.",
                     "NDVI/NDWI: data exist only on cloud-free days; the dotted line connects those days."),
    "bar.cercanas": ("Estaciones cercanas", "Nearby stations"),
    "bar.cercanas_cap": ("Distancia al borde del barrio y registro semanal de precipitación.",
                         "Distance to the neighborhood boundary and weekly precipitation record."),
    "bar.col_distancia": ("Distancia (km)", "Distance (km)"),
    "bar.col_precip_media": ("Precipitación media (mm/sem)", "Mean precipitation (mm/week)"),
    "bar.sin_estaciones": ("No hay estaciones registradas para calcular cercanía.",
                           "No stations are available to compute proximity."),
}

TEXTOS: dict[str, dict[str, str]] = {clave: dict(zip(IDIOMAS, par, strict=True)) for clave, par in _TEXTOS.items()}


_PREVIO, _CAMBIO = "_lang_previo", "_lang_cambio"


def marcar_idioma(lang: str):
    """Registra si el idioma cambió en esta ejecución (lo llama app.py tras el selector)."""
    st.session_state[_CAMBIO] = st.session_state.get(_PREVIO, lang) != lang
    st.session_state[_PREVIO] = lang


def conservar(*claves: str):
    """Conserva la selección de widgets cuyas etiquetas se traducen.

    Streamlit transmite el valor de selectbox y segmented_control como la etiqueta visible. Al cambiar de
    idioma esa etiqueta ya no coincide con ninguna opción y el widget volvería a su valor por defecto.
    Leer el valor antes de dibujar el widget (aún se interpreta con las etiquetas de la ejecución anterior)
    y fijarlo en la sesión lo conserva. Solo actúa en la ejecución en que cambió el idioma.
    """
    if not st.session_state.get(_CAMBIO):
        return
    for clave in claves:
        if clave in st.session_state:
            st.session_state[clave] = st.session_state[clave]


def idioma() -> str:
    """Idioma activo de la sesión (lo fija el selector de la barra lateral); español por defecto."""
    try:
        lang = st.session_state.get(CLAVE_IDIOMA)
    except Exception:  # fuera de una sesión de Streamlit (scripts, pruebas unitarias)
        lang = None
    return lang if lang in IDIOMAS else IDIOMA_DEFECTO


def t(clave: str, lang: str | None = None, **valores) -> str:
    """Texto de `clave` en `lang` (o en el idioma activo), con los campos de formato que se pasen."""
    texto = TEXTOS[clave][lang if lang in IDIOMAS else idioma()]
    return texto.format(**valores) if valores else texto


def t_comuna(valor: str, lang: str | None = None) -> str:
    """Traduce los valores de comuna que vienen de los datos («Comuna 19», «Área de expansión», …)."""
    if isinstance(valor, str) and valor.startswith("Comuna ") and valor[7:].isdigit():
        return t("comuna.n", lang, n=valor[7:])
    fijos = {"Área de expansión": "comuna.expansion", "Sin comuna": "comuna.sin",
             "Fuera del perímetro urbano": "comuna.fuera"}
    return t(fijos[valor], lang) if valor in fijos else valor


def meses(lang: str | None = None) -> list[str]:
    return t("fecha.meses", lang).split()


def locale_js(lang: str | None = None) -> str:
    """Configuración regional para formatear números en el navegador (lecturas de los mapas).

    Punto decimal en ambos idiomas, igual que las cifras que formatea Python en tarjetas, tablas y gráficos.
    """
    return "en-US"


def rango_fechas(t0, t1, lang: str | None = None) -> str:
    """Rango compacto: «01–31 ago 2026», «28 ago – 05 sep 2026» o «jun 2014 – ene 2025» (meses en `lang`)."""
    t0, t1 = pd.Timestamp(t0), pd.Timestamp(t1)
    m = meses(lang)
    if (t1 - t0).days > 366:
        return f"{m[t0.month - 1]} {t0.year} – {m[t1.month - 1]} {t1.year}"
    if (t0.year, t0.month) == (t1.year, t1.month):
        return f"{t0.day:02d}–{t1.day:02d} {m[t1.month - 1]} {t1.year}"
    return f"{t0.day:02d} {m[t0.month - 1]} – {t1.day:02d} {m[t1.month - 1]} {t1.year}"


def fecha_corta(fecha, lang: str | None = None) -> str:
    """«16 ago 2026» / «16 Aug 2026»."""
    fecha = pd.Timestamp(fecha)
    return f"{fecha.day:02d} {meses(lang)[fecha.month - 1]} {fecha.year}"
