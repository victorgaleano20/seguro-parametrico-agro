"""
01_descargar_datos.py
Descarga las fuentes crudas de EE. UU. que usa la base de Iowa, Illinois e Indiana (script 08), sin modificarlas.

Fuentes (datos/crudos/):
  - Índice ONI (NOAA CPC), para la fase de El Niño en el impacto en dólares.
  - Límites de condados del Census Bureau y calendario de siembra y cosecha del USDA.
  - CHIRPS mensual recortado al recuadro de Iowa, Illinois e Indiana.
  - RMA Cause of Loss y Summary of Business (todos los estados; se filtran después).
  - NASS Quick Stats, maíz para grano por condado (requiere la variable de entorno NASS_API_KEY).
Las demás fuentes (NOAA por condado, censos, precios y los siete estados nuevos) las bajan 27 y 33.

Cada descarga queda anotada en datos/crudos/registro_descargas.csv
(fuente, url, archivo, fecha de descarga, tamaño). Si un archivo ya existe,
no se vuelve a bajar. Uso:  python scripts/01_descargar_datos.py
"""
import csv
import datetime as dt
import os
import sys
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
CRUDOS = RAIZ / "datos" / "crudos"
REGISTRO = CRUDOS / "registro_descargas.csv"
LIMITE_MB = 500  # por encima de esto no se descarga sin preguntar

CAJA_EEUU = (-97, -84, 36.5, 44)       # recuadro (lon_min, lon_max, lat_min, lat_max) de Iowa, Illinois e Indiana
PRIMER_ANIO_CHIRPS = 1981

ESTADOS_EEUU = ["IA", "IL", "IN"]
PRIMER_ANIO_RMA = 1989                 # primer año de los archivos de la RMA
RMA = "https://pubfs-rma.fpac.usda.gov/pub/Web_Data_Files/Summary_of_Business"
NASS_API = "https://quickstats.nass.usda.gov/api/api_GET/"
NASS_SERIES = {                        # short_desc de NASS -> nombre corto del archivo
    "CORN, GRAIN - PRODUCTION, MEASURED IN BU": "produccion",
    "CORN, GRAIN - ACRES HARVESTED": "area_cosechada",
    "CORN, GRAIN - YIELD, MEASURED IN BU / ACRE": "rendimiento",
}

FUENTES = [
    {
        "fuente": "Índice ONI - NOAA Climate Prediction Center",
        "url": "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt",
        "archivo": "oni/oni.ascii.txt",
    },
    {
        "fuente": "Límites de condados cartográficos 2023 1:500k - US Census Bureau",
        "url": "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_500k.zip",
        "archivo": "eeuu/condados/cb_2023_us_county_500k.zip",
    },
    {
        "fuente": "Usual Planting and Harvesting Dates for U.S. Field Crops (oct-2010) - USDA NASS",
        "url": "https://esmis.nal.usda.gov/sites/default/release-files/vm40xr56k/dv13zw65p/z603r1055/planting-10-29-2010.txt",
        "archivo": "eeuu/calendario/planting-10-29-2010.txt",
    },
]


def url_chirps(anio, caja=CAJA_EEUU):
    """URL de la IRI Data Library que recorta CHIRPS mensual a un recuadro para un año."""
    lon_min, lon_max, lat_min, lat_max = caja
    return (
        "https://iridl.ldeo.columbia.edu/SOURCES/.UCSB/.CHIRPS/.v2p0/.monthly/.global/.precipitation/"
        f"X/{lon_min}/{lon_max}/RANGEEDGES/Y/{lat_min}/{lat_max}/RANGEEDGES/"
        f"T/(Jan%20{anio})/(Dec%20{anio})/RANGEEDGES/data.nc"
    )


def tamano_remoto_mb(url):
    """Pregunta el tamaño al servidor (HEAD). Devuelve None si no lo informa."""
    try:
        r = requests.head(url, allow_redirects=True, timeout=60)
        largo = r.headers.get("Content-Length")
        return int(largo) / 1e6 if largo else None
    except requests.RequestException:
        return None


def anotar_registro(fuente, url, destino):
    """Agrega una fila al registro de descargas."""
    nuevo = not REGISTRO.exists()
    with open(REGISTRO, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(["fuente", "url", "archivo", "fecha_descarga", "tamano_mb"])
        w.writerow([
            fuente, url, destino.relative_to(CRUDOS).as_posix(),
            dt.date.today().isoformat(), round(destino.stat().st_size / 1e6, 2),
        ])


def descargar(fuente, url, archivo):
    """Descarga un archivo si no existe todavía. Devuelve True si quedó en disco."""
    destino = CRUDOS / archivo
    if destino.exists():
        print(f"Ya existe, no se descarga de nuevo: {archivo}")
        return True

    mb = tamano_remoto_mb(url)
    if mb is not None and mb > LIMITE_MB:
        print(f"AVISO: {archivo} pesa {mb:.0f} MB (más de {LIMITE_MB} MB). No se descarga sin confirmar.")
        return False

    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(destino.suffix + ".parcial")
    print(f"Descargando {archivo}" + (f" ({mb:.0f} MB)" if mb else "") + " ...")
    try:
        with requests.get(url, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(temporal, "wb") as f:
                for bloque in r.iter_content(chunk_size=1 << 20):
                    f.write(bloque)
        temporal.rename(destino)
    except requests.RequestException as e:
        temporal.unlink(missing_ok=True)
        print(f"ERROR: falló la descarga de {archivo}: {e}")
        print(f"   Bájalo a mano desde: {url}")
        print(f"   y guárdalo como: {destino}")
        return False

    anotar_registro(fuente, url, destino)
    print(f"Listo: {archivo} ({destino.stat().st_size / 1e6:.1f} MB)")
    return True


def descargar_nass():
    """Maíz para grano por condado (IA, IL, IN) desde la API de NASS Quick Stats."""
    clave = os.environ.get("NASS_API_KEY", "").strip()
    if not clave:
        print("AVISO: falta la API key de NASS Quick Stats (variable de entorno NASS_API_KEY).")
        print("   Pídela gratis en https://quickstats.nass.usda.gov/api (botón 'Request API Key';")
        print("   llega al correo). Luego, en PowerShell:  $env:NASS_API_KEY = 'tu_clave'")
        print("   y vuelve a correr este script. Sigo con las demás descargas.")
        return
    for estado in ESTADOS_EEUU:
        for short_desc, nombre in NASS_SERIES.items():
            archivo = f"eeuu/nass/nass_maiz_grano_{estado}_{nombre}.csv"
            destino = CRUDOS / archivo
            if destino.exists():
                print(f"Ya existe, no se descarga de nuevo: {archivo}")
                continue
            params = {"source_desc": "SURVEY", "agg_level_desc": "COUNTY", "state_alpha": estado,
                      "short_desc": short_desc, "reference_period_desc": "YEAR",
                      "year__GE": PRIMER_ANIO_CHIRPS, "format": "CSV"}
            print(f"Descargando {archivo} ...")
            try:
                r = requests.get(NASS_API, params={"key": clave, **params}, timeout=300)
                r.raise_for_status()
            except requests.RequestException as e:
                print(f"ERROR: falló NASS {estado} {nombre}: {e}")
                continue
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(r.content)
            # En el registro se guarda la consulta SIN la clave
            url_sin_clave = requests.Request("GET", NASS_API, params=params).prepare().url
            anotar_registro("NASS Quick Stats API - USDA (maíz para grano, condado)", url_sin_clave, destino)
            print(f"Listo: {archivo} ({destino.stat().st_size / 1e6:.2f} MB)")


def main():
    CRUDOS.mkdir(parents=True, exist_ok=True)

    for f in FUENTES:
        descargar(f["fuente"], f["url"], f["archivo"])

    # CHIRPS: un archivo NetCDF por año (~2 MB cada uno)
    anio_actual = dt.date.today().year
    for anio in range(PRIMER_ANIO_CHIRPS, anio_actual + 1):
        archivo = f"eeuu/chirps/chirps_mensual_eeuu_{anio}.nc"
        # El año en curso está incompleto: se baja de nuevo cada vez
        if anio == anio_actual:
            (CRUDOS / archivo).unlink(missing_ok=True)
        descargar("CHIRPS v2.0 mensual, recorte eeuu - IRI Data Library / Climate Hazards Center UCSB",
                  url_chirps(anio), archivo)

    # RMA: Cause of Loss y Summary of Business por año (años completos)
    for anio in range(PRIMER_ANIO_RMA, anio_actual):
        descargar("RMA Cause of Loss - Summary of Business with Month (USDA)",
                  f"{RMA}/cause_of_loss/colsom_{anio}.zip", f"eeuu/rma/colsom_{anio}.zip")
        descargar("RMA Summary of Business - State/County/Crop with Coverage Level (USDA)",
                  f"{RMA}/state_county_crop/sobcov_{anio}.zip", f"eeuu/rma/sobcov_{anio}.zip")

    descargar_nass()
    print("Descargas terminadas. Revisa datos/crudos/registro_descargas.csv")


if __name__ == "__main__":
    main()
