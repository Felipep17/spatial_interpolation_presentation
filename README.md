# GeoClima Cali

Plataforma web (Streamlit) de análisis espaciotemporal y monitoreo hidrometeorológico de **Santiago de Cali**, desarrollada en el marco del proyecto **Dengue.IA Cali**.

Integra tres fuentes de información sobre la capa de barrios de la ciudad:

| Módulo | Fuente | Qué muestra |
|---|---|---|
| **Fuentes satelitales** | Copernicus C3S · AgERA5 (0.1°) | Humedad relativa y temperatura máxima diarias, visor temporal y estadísticas zonales por barrio |
| | CHIRPS v3.0 (0.05°) | Precipitación diaria, visor temporal y acumulados por barrio |
| | MSWEP (0.1°) | Precipitación diaria multi-fuente, mismo visor que CHIRPS |
| | Google Earth Engine · MODIS (1 km) | NDVI y NDWI diarios sin nubes, visor temporal y estadísticas por barrio |
| **Estaciones in situ** | Red de estaciones meteorológicas (CSV) | Series agregadas por **semana epidemiológica (INS/CDC, domingo a sábado)**, mapa de la red, completitud y **grilla de 1 km** activable |

---

## Tabla de contenido

1. [Requisitos](#1-requisitos)
2. [Instalación rápida](#2-instalación-rápida)
3. [Ejecutar la aplicación](#3-ejecutar-la-aplicación)
4. [Datos de entrada](#4-datos-de-entrada) · [Descarga de GEE y MSWEP](#44-descarga-de-gee-y-mswep)
5. [Estructura del proyecto](#5-estructura-del-proyecto)
6. [Configuración y personalización](#6-configuración-y-personalización)
7. [Metodología](#7-metodología)
8. [Desarrollo](#8-desarrollo)
9. [Solución de problemas](#9-solución-de-problemas)
10. [Créditos](#10-créditos)

---

## 1. Requisitos

| Requisito | Versión | Notas |
|---|---|---|
| Sistema operativo | macOS (Apple Silicon o Intel), Linux o Windows | Probado en macOS arm64 |
| [uv](https://docs.astral.sh/uv/) | ≥ 0.5 | Gestor de paquetes y entornos virtuales (recomendado) |
| Python | 3.11 – 3.13 | **No hace falta instalarlo a mano**: `uv` descarga la versión fijada en `.python-version` (3.12) |
| Navegador | Chrome, Edge, Firefox o Safari recientes | |
| Conexión a internet | — | Necesaria para los mosaicos de OpenStreetMap y la fuente tipográfica Inter |

> **No se requiere GDAL del sistema.** `geopandas`, `pyogrio` y `pyproj` se instalan como *wheels* que incluyen sus propias librerías nativas.

### Instalar `uv`

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# o con Homebrew
brew install uv

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Verifica la instalación:

```bash
uv --version
```

---

## 2. Instalación rápida

```bash
git clone https://github.com/Felipep17/spatial_interpolation_presentation.git
cd spatial_interpolation_presentation
uv sync
```

`uv sync`:

1. Descarga Python 3.12 si no está disponible.
2. Crea el entorno virtual local en `.venv/`.
3. Instala **exactamente** las versiones fijadas en `uv.lock` (instalación reproducible).

> Si trabajas dentro de una carpeta que ya tiene otro `.venv` activado (por ejemplo `~/Downloads/.venv`), desactívalo antes con `deactivate`. `uv` siempre usa el `.venv` del proyecto.

### Alternativa sin `uv` (pip)

```bash
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt` se genera desde `uv.lock`; no lo edites a mano (ver [Desarrollo](#8-desarrollo)).

---

## 3. Ejecutar la aplicación

```bash
uv run streamlit run app.py
```

Abre **http://localhost:8501** en el navegador.

| Página | URL |
|---|---|
| Fuentes satelitales (por defecto) | `http://localhost:8501/` |
| Estaciones in situ | `http://localhost:8501/estaciones` |

Opciones útiles:

```bash
# Otro puerto
uv run streamlit run app.py --server.port 8600

# Exponer en la red local (p. ej. para presentar desde otro equipo)
uv run streamlit run app.py --server.address 0.0.0.0

# Recargar automáticamente al guardar archivos
uv run streamlit run app.py --server.runOnSave true
```

Para detener el servidor: `Ctrl + C` en la terminal.

> La **primera carga** de cada fuente tarda algunos segundos mientras se procesan los NetCDF y el CSV; luego los resultados quedan en caché y la navegación es inmediata. La caché se invalida sola si cambias un archivo de entrada.

---

## 4. Datos de entrada

Todo se lee desde la carpeta `inputs/`. La aplicación se detiene con un mensaje claro si falta `inputs/` o la capa de barrios; el resto de fuentes son opcionales y muestran un estado vacío si no existen.

```
inputs/
├── shapefiles/
│   └── cali.parquet                  # Capa de barrios (obligatoria)
├── raster/
│   ├── C3S/                          # NetCDF AgERA5
│   │   ├── 2m_relative_humidity_2026_09.nc
│   │   └── 2m_temperature_maximum_2026_09.nc
│   ├── CHIRPS/
│   │   └── chirps_2026_08_cali.nc
│   ├── MSWEP/                        # (opcional) solo se listan los archivos
│   └── GEE/                          # (opcional) solo se listan los archivos
├── climaticas_post_calidad.csv       # Estaciones in situ
└── logo.png                          # (opcional) franja institucional de aliados
```

### 4.1 Capa de barrios — `inputs/shapefiles/`

- Formatos aceptados (en este orden de prioridad): `.parquet` (GeoParquet), `.shp`, `.geojson`, `.gpkg`. Se usa el primer archivo encontrado.
- Se reproyecta automáticamente a **EPSG:4326** si viene en otro CRS.
- El nombre del barrio se toma de la columna `nombre` (sin distinguir mayúsculas); si no existe, de la primera columna.

### 4.2 Raster — `inputs/raster/<FUENTE>/`

Cada subcarpeta es una fuente y aparece como una opción del selector. Se indexan archivos `.nc` y `.tif`.

| Fuente | Archivos que se buscan | Variable |
|---|---|---|
| **C3S** | uno cuyo nombre contenga `relative_humidity` y otro que contenga `temperature_maximu` o `t2m` | La primera variable con ≥ 2 dimensiones; coordenadas `lat/latitude/y` y `lon/longitude/x`; dimensión `time` |
| **CHIRPS** | un `.nc` cuyo nombre contenga `chirps` | `precipitation`, coordenadas `lat`/`lon` (o `latitude`/`longitude`) |
| Otras | cualquier `.nc` / `.tif` | Solo se muestra el inventario (nombre, formato y tamaño) |

Detalles:

- C3S se **recorta** automáticamente a la extensión de Cali (con medio píxel de margen); el archivo puede cubrir un área mayor.
- Las longitudes en 0–360° se convierten a −180–180°.
- Las temperaturas en Kelvin se convierten a °C.
- CHIRPS se asume **ya recortado** al área de estudio.

### 4.3 Estaciones — `inputs/climaticas_post_calidad.csv`

Columnas requeridas (pueden existir otras; se ignoran):

| Columna | Tipo | Unidad |
|---|---|---|
| `Estacion` | texto | — |
| `Fecha` | fecha `YYYY-MM-DD` (diaria) | — |
| `Precipitacion` | número | mm |
| `Tmin`, `Tmax` | número | °C |
| `Humedad relativa` | número | % |
| `Velocidad del viento` | número | m/s |
| `Radiación solar` | número | W/m² |
| `Latitud`, `Longitud` | número | grados (EPSG:4326) |

Los valores vacíos se tratan como dato faltante.

### 4.4 Descarga de GEE y MSWEP

Los scripts de `descargas/` (adaptados de [climate_data_downloader](https://github.com/dagudelo30/climate_data_downloader)) toman **el mismo periodo del NetCDF de CHIRPS**, recortan a Cali y escriben NetCDF listos para la app. Sus dependencias van en un grupo aparte:

```bash
uv sync --group descarga
```

**Google Earth Engine — NDVI y NDWI a 1 km** → `inputs/raster/GEE/{ndvi,ndwi}_modis_1km_<AAAA_MM>_cali.nc`

1. Tener un proyecto de Google Cloud registrado en Earth Engine (<https://code.earthengine.google.com/register>).
2. Autenticarse una vez: `uv run --group descarga earthengine authenticate`
3. Descargar:
   ```bash
   uv run --group descarga python -m descargas.gee --project <ID_PROYECTO_GCP>
   ```

- Fuente: `MODIS/061/MOD09GA` diario. NDVI = (b02 − b01)/(b02 + b01); NDWI (Gao) = (b02 − b06)/(b02 + b06).
- Los píxeles de 500 m se **promedian** sobre una grilla fija de **0.009° (~1 km)** definida en `descargas/comun.py`.
- Nubes, sombras y nubes internas se enmascaran con la banda QA `state_1km` (`--sin-mascara-nubes` lo desactiva). En días nublados las celdas quedan vacías.

**MSWEP — precipitación diaria 0.1°** → `inputs/raster/MSWEP/mswep_<AAAA_MM>_cali.nc`

1. Solicitar acceso en <https://www.gloh2o.org/mswep/> con su cuenta de Google (GloH2O comparte la carpeta de Drive).
2. En Google Cloud Console: habilitar la API de Google Drive y crear un cliente OAuth tipo **Aplicación de escritorio**; descargar su JSON.
3. Descargar:
   ```bash
   uv run --group descarga python -m descargas.mswep --client-secret /ruta/client.json
   ```

- Cada archivo global se descarga a un temporal, se recorta a Cali y se descarta.
- El token (solo lectura de Drive) se guarda en `~/.config/geoclima/mswep_token.json`, fuera del repositorio.

Ambos scripts aceptan `--inicio AAAA-MM-DD --fin AAAA-MM-DD` para otro periodo. Si falta algún archivo, la vista correspondiente muestra el comando exacto de descarga.

### 4.5 Logo institucional — `inputs/logo.png` (opcional)

PNG con fondo transparente. Si existe, se muestra en versión compacta arriba a la derecha de cada página y en tamaño completo en el pie de página. El margen transparente se recorta automáticamente.

---

## 5. Estructura del proyecto

```
.
├── app.py                  # Punto de entrada: configuración, barra lateral y navegación
├── utils.py                # Carga de datos, estadísticas zonales y construcción de mapas
├── descargas/              # Scripts de descarga: GEE (NDVI/NDWI 1 km) y MSWEP; grilla de 1 km común
├── views/
│   ├── satelital.py        # Módulo 01 · Fuentes satelitales (C3S, CHIRPS, inventario)
│   └── estaciones.py       # Módulo 02 · Estaciones in situ
├── components/
│   ├── theme.py            # Tokens de diseño: colores, variables, paletas, leyendas, plantilla Plotly
│   ├── ui.py               # Componentes de interfaz: encabezados, KPIs, insignias, footer
│   └── charts.py           # Series temporales Plotly
├── assets/                 # Logo e ícono de la aplicación (SVG)
├── .streamlit/config.toml  # Tema visual y opciones del servidor
├── inputs/                 # Datos de entrada (ver sección 4)
├── outputs/                # Productos generados fuera de la app
├── pyproject.toml          # Dependencias del proyecto
├── uv.lock                 # Versiones exactas (no editar a mano)
├── requirements.txt        # Exportado de uv.lock para instalaciones con pip
└── .python-version         # Versión de Python del proyecto (3.12)
```

---

## 6. Configuración y personalización

| Qué cambiar | Dónde |
|---|---|
| Colores, tipografía y radios del tema | `.streamlit/config.toml` **y** `COLORS` en `components/theme.py` (mantener sincronizados) |
| Paleta, unidad o tipo de gráfico de cada variable | `VARIABLES` y `RASTER_VARS` en `components/theme.py` |
| Mapa base | `TILES_URL` y `TILES_ATTR` en `components/theme.py` |
| Opacidad del raster y estilo de los límites de barrio | `RASTER_OPACITY` y `BARRIO_LINE` en `components/theme.py` |
| Zoom inicial de todos los mapas | `MAP_ZOOM` en `utils.py` |
| Altura de los visores raster | `MAP_HEIGHT` en `components/theme.py` |
| Textos y enlaces de cada fuente satelital | `FUENTES_META` en `views/satelital.py` |

**Mapa base.** Se usa el servidor estándar de OpenStreetMap (`tile.openstreetmap.org`), que muestra calles, nombres de vías y edificios (desde zoom 16). Es un servicio comunitario con una [política de uso](https://operations.osmfoundation.org/policies/tiles/) que no admite tráfico intensivo: para un despliegue con muchos usuarios conviene un proveedor con API key (MapTiler, Stadia, CARTO, etc.), cambiando solo `TILES_URL`/`TILES_ATTR`.

---

## 7. Metodología

### Estadísticas zonales (raster → barrio)

Para cada barrio y cada día se calcula el **promedio simple de los píxeles cuya celda intersecta el polígono** del barrio, ignorando píxeles sin dato. La intersección se resuelve con un índice espacial (STRtree de Shapely). El número de píxeles intersectados se muestra en el mapa y en las tablas.

> Con resoluciones de 0.1° (~11 km) la mayoría de barrios cae en 1–2 píxeles, por lo que barrios vecinos suelen compartir valores. Es una limitación de la resolución de la fuente, no un error.

### Escalas de color

Los límites de cada paleta se fijan en los **percentiles 2 y 98** de los datos (la precipitación parte de 0), para que los valores extremos no saturen el mapa. Las leyendas se generan desde el mismo colormap que pinta los datos.

### Grilla de 1 km en estaciones

El interruptor **Grilla 1 km (GEE)** del mapa de estaciones dibuja, totalmente transparentes, las celdas de 0.009° que tocan los barrios de Cali: las mismas del NetCDF de GEE (o la grilla teórica idéntica si aún no se ha descargado). Al pasar el cursor por una celda se ve su identificador, centro, estaciones que contiene, barrios que toca y porcentaje de su área dentro de Cali; debajo del mapa se resume cuántas celdas quedan en el área, cuántas tienen estación y cuántas celdas abarca cada barrio.

### Agregación semanal de estaciones

Los datos diarios se agrupan por **semana epidemiológica según INS Colombia / CDC (MMWR)**:

- Cada semana va de **domingo a sábado** y se etiqueta con la fecha del **sábado** de cierre.
- La **semana 1** es la primera semana con al menos 4 días en enero (la que contiene el primer miércoles del año); algunos años tienen semana 53.
- Se incluyen las columnas `Año epi` y `Semana epi`. El cálculo se validó contra la librería [`epiweeks`](https://pypi.org/project/epiweeks/) (sistema CDC) con 100 % de coincidencia.
- Precipitación: **suma** semanal. Resto de variables: **media** semanal.

> Esta definición difiere de la ISO 8601 (lunes a domingo, semana 1 = la del primer jueves).

---

## 8. Desarrollo

```bash
# Agregar una dependencia (actualiza pyproject.toml y uv.lock)
uv add nombre-paquete

# Actualizar todas las dependencias dentro de los rangos permitidos
uv lock --upgrade && uv sync

# Regenerar requirements.txt tras cambiar dependencias
uv export --no-hashes --no-dev --no-emit-project -o requirements.txt

# Linter
uv run ruff check app.py utils.py components views descargas
```

Recomendado: instalar `watchdog` para que la recarga automática sea más eficiente.

```bash
uv add --dev watchdog
```

---

## 9. Solución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| `command not found: uv` | `uv` no está en el `PATH` | Reinicia la terminal tras instalarlo o ejecuta `source ~/.zshrc` |
| `uv run` usa otro Python u otras librerías | Hay otro entorno virtual activado | `deactivate` y vuelve a ejecutar; confirma con `uv run python -c "import sys; print(sys.prefix)"` que apunta a `./.venv` |
| `ImportError: ... pyarrow` o `No module named 'streamlit_folium'` | Entorno incompleto o se ejecutó con otro intérprete | `uv sync` y ejecutar siempre con `uv run streamlit run app.py` |
| `No se encontró la carpeta 'inputs'` | La app se lanzó desde otra ruta o falta la carpeta | Verifica que `inputs/` esté junto a `app.py` |
| `No se encontró la capa vectorial de barrios` | `inputs/shapefiles/` vacía o con formato no soportado | Agrega un `.parquet`, `.shp` (con sus `.dbf/.shx/.prj`), `.geojson` o `.gpkg` |
| El mapa se ve gris, sin calles | Sin internet, firewall o bloqueo del servidor de OSM | Revisa la conexión; en redes corporativas permite `tile.openstreetmap.org`. Si persiste, cambia el proveedor (sección 6) |
| "Archivos incompletos" en C3S | Los nombres no contienen `relative_humidity` / `temperature_maximu` | Renombra los archivos o ajusta la búsqueda en `views/satelital.py` |
| `Port 8501 is already in use` | Ya hay otra app corriendo | Ciérrala o usa `--server.port 8600` |
| Datos viejos tras reemplazar un archivo | Caché del navegador o de Streamlit | Menú ⋮ → **Clear cache** y recarga, o reinicia el servidor |
| "Page not found" al abrir `/satelital` | La página por defecto se sirve en `/` | Usa `http://localhost:8501/` |
| Error al compilar `netCDF4` o `geopandas` | Python fuera del rango soportado | Usa Python 3.11–3.13 (`uv python pin 3.12 && uv sync`) |

Para reinstalar el entorno desde cero:

```bash
rm -rf .venv
uv sync
```

---

## 10. Créditos

Proyecto **Dengue.IA Cali**, en alianza con la Universidad Icesi, la Universidad del Valle, la Alcaldía de Santiago de Cali y Cubo Social, con financiación de The Rockefeller Foundation.

Fuentes de datos:

- **AgERA5** — Copernicus Climate Change Service (C3S). DOI: [10.24381/cds.6c68c9bb](https://doi.org/10.24381/cds.6c68c9bb)
- **CHIRPS v3.0** — Climate Hazards Center, UC Santa Barbara. <https://www.chc.ucsb.edu/data/chirps3>
- **Mapa base** — © colaboradores de [OpenStreetMap](https://www.openstreetmap.org/copyright)
