"""Precipitación diaria MSWEP (0.1°) desde la carpeta de Google Drive de GloH2O.

Requisitos (una sola vez):
  1. Solicitar acceso a MSWEP en https://www.gloh2o.org/mswep/ con su cuenta de Google.
     GloH2O comparte la carpeta de Drive con esa cuenta.
  2. Crear un cliente OAuth tipo "Aplicación de escritorio" en Google Cloud Console
     (API de Google Drive habilitada) y descargar su JSON.

Uso:
    uv run --group descarga python -m descargas.mswep --client-secret /ruta/client.json

- Periodo: el mismo del NetCDF de CHIRPS (se puede forzar con --inicio/--fin).
- Cada archivo diario global se descarga a un temporal, se recorta a la extensión de
  Cali y se descarta; solo se conserva el recorte.
- El token OAuth (solo lectura de Drive) se guarda fuera del repositorio:
  ~/.config/geoclima/mswep_token.json

Salida: inputs/raster/MSWEP/mswep_<AAAA_MM>_cali.nc  (time, lat, lon) variable "precipitation"
"""

import argparse
import io
import tempfile
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from descargas.comun import MARGEN, RASTER, bounds_cali, guardar_netcdf, periodo_chirps

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
TOKEN = Path.home() / ".config" / "geoclima" / "mswep_token.json"
# Carpetas diarias de MSWEP en Drive (tomadas de climate_data_downloader)
CARPETA_HASTA_2020 = "1gWoZ2bK2u5osJ8Iw-dvguZ56Kmz2QWrL"
CARPETA_DESDE_2021 = "1aehP6YDNOO73ab3tvTZet2Sh5uPdG9I_"
RES_MSWEP = 0.1


def servicio_drive(client_secret: Path):
    creds = Credentials.from_authorized_user_file(TOKEN, SCOPES) if TOKEN.exists() else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES).run_local_server(port=0)
        TOKEN.parent.mkdir(parents=True, exist_ok=True)
        TOKEN.write_text(creds.to_json())
        TOKEN.chmod(0o600)
    return build("drive", "v3", credentials=creds)


def _buscar(service, carpeta: str, nombre: str):
    r = service.files().list(
        q=f"name='{nombre}' and '{carpeta}' in parents and trashed=false",
        fields="files(id, name)", includeItemsFromAllDrives=True, supportsAllDrives=True,
    ).execute()
    archivos = r.get("files", [])
    return archivos[0]["id"] if archivos else None


def _recortar(ruta: Path, bounds) -> xr.DataArray:
    minx, miny, maxx, maxy = bounds
    m = MARGEN + RES_MSWEP / 2
    with xr.open_dataset(ruta) as ds:
        var = "precipitation" if "precipitation" in ds.data_vars else list(ds.data_vars)[0]
        da = ds[var]
        ren = {}
        for d in da.dims:
            if d.lower() in ("latitude", "y"):
                ren[d] = "lat"
            elif d.lower() in ("longitude", "x"):
                ren[d] = "lon"
        da = da.rename(ren)
        if float(da.lon.max()) > 180:
            da = da.assign_coords(lon=((da.lon + 180) % 360) - 180).sortby("lon")
        lat_desc = da.lat.values[0] > da.lat.values[-1]
        da = da.sel(lat=slice(maxy + m, miny - m) if lat_desc else slice(miny - m, maxy + m),
                    lon=slice(minx - m, maxx + m)).load()
    da = da.assign_coords(lat=np.round(da.lat.values.astype(float), 4), lon=np.round(da.lon.values.astype(float), 4))
    return da.sortby("lat", ascending=False)


def descargar(client_secret: Path, inicio: date, fin: date):
    service = servicio_drive(client_secret)
    bounds = bounds_cali()
    dias, faltantes = [], []

    with tempfile.TemporaryDirectory() as tmp:
        d = inicio
        while d <= fin:
            nombre = f"{d.year}{d.timetuple().tm_yday:03d}.nc"
            carpeta = CARPETA_HASTA_2020 if d.year <= 2020 else CARPETA_DESDE_2021
            file_id = _buscar(service, carpeta, nombre)
            if not file_id:
                print(f"{d}: {nombre} no encontrado en Drive")
                faltantes.append(d)
                d += timedelta(days=1)
                continue
            destino = Path(tmp) / nombre
            with io.FileIO(destino, "wb") as fh:
                dl = MediaIoBaseDownload(fh, service.files().get_media(fileId=file_id))
                hecho = False
                while not hecho:
                    _, hecho = dl.next_chunk()
            da = _recortar(destino, bounds)
            da = da.squeeze(drop=True) if "time" in da.dims and da.sizes["time"] == 1 else da
            dias.append(da.expand_dims(time=[pd.Timestamp(d)]) if "time" not in da.dims else da)
            destino.unlink()
            print(f"{d}: {nombre} ✓ ({da.sizes['lat']}×{da.sizes['lon']} píxeles)")
            d += timedelta(days=1)

    if not dias:
        raise SystemExit("No se descargó ningún día: verifique el acceso a la carpeta de MSWEP en Drive.")

    serie = xr.concat(dias, dim="time").reindex(time=pd.date_range(inicio, fin, freq="D"))
    ds = serie.astype("float32").to_dataset(name="precipitation")
    ds["precipitation"].attrs.update(units="mm/day", long_name="Precipitación diaria")
    ds.attrs.update(
        title="MSWEP precipitación diaria (0.1°) recortada a Cali",
        source="GloH2O MSWEP · https://www.gloh2o.org/mswep/",
        missing_days=", ".join(str(x) for x in faltantes) or "ninguno",
    )
    sufijo = f"{inicio:%Y_%m}" if (inicio.year, inicio.month) == (fin.year, fin.month) else f"{inicio:%Y%m%d}_{fin:%Y%m%d}"
    destino = RASTER / "MSWEP" / f"mswep_{sufijo}_cali.nc"
    guardar_netcdf(ds, destino)
    print(f"Guardado: {destino} · días faltantes: {len(faltantes)} · NaN: {int(np.isnan(ds.precipitation).sum())}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--client-secret", type=Path, required=True, help="JSON del cliente OAuth de escritorio")
    p.add_argument("--inicio", type=date.fromisoformat, help="AAAA-MM-DD (por defecto: inicio de CHIRPS)")
    p.add_argument("--fin", type=date.fromisoformat, help="AAAA-MM-DD (por defecto: fin de CHIRPS)")
    a = p.parse_args()
    ini, fin = periodo_chirps()
    descargar(a.client_secret, a.inicio or ini, a.fin or fin)


if __name__ == "__main__":
    main()
