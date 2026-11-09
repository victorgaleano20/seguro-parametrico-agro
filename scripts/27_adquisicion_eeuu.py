"""
27_adquisicion_eeuu.py
Fase 0 del seguro de sequía para el maíz de EE. UU. (plan en docs/bitacora.md, 2026-11-04).

Baja lo que falta para Iowa, Illinois e Indiana y lo anota en datos/crudos/registro_descargas.csv:
  - Temperatura máxima y sequía de Palmer mensuales por condado (NOAA NCEI, nClimDiv).
  - Censos agropecuarios 2002 y 2017 de NASS (archivos masivos sin clave). Se leen en línea y se guardan
    solo las filas de maíz por condado de los 3 estados.
  - Precio promedio recibido por los agricultores (USDA ERS, Feed Grains Yearbook).
  - Índice de precios al consumidor CPI-U (BLS, API pública v1, sin clave).
No descarga nada de más de 500 MB. Lo que ya existe no se baja de nuevo.
Uso:  python scripts/27_adquisicion_eeuu.py
"""
import csv
import datetime as dt
import gzip
import io
import sys
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
CRUDOS = RAIZ / "datos" / "crudos"
DESTINO = CRUDOS / "eeuu"
REGISTRO = CRUDOS / "registro_descargas.csv"
LIMITE_MB = 500
ESTADOS = {"IA", "IL", "IN"}

NOAA = "https://www.ncei.noaa.gov/monitoring-content/data/us/climdiv/monthly/current/"
VERSION_NOAA = "v1.0.0-20261006"
CENSOS = {2002: "https://www.nass.usda.gov/sites/default/files/datasets/qs.census2002.txt.gz",
          2017: "https://www.nass.usda.gov/sites/default/files/datasets/qs.census2017.txt.gz"}
ERS = "https://www.ers.usda.gov/media/5766/feed-grains-yearbook-tables-all-years.csv"
SERIE_CPI = "CUUR0000SA0"
BLS = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
ANIO_INI, ANIO_FIN = 1981, 2025


def anotar(fuente, url, destino, mb=None):
    with open(REGISTRO, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([fuente, url, destino.relative_to(CRUDOS).as_posix(), dt.date.today().isoformat(),
                                round(mb if mb is not None else destino.stat().st_size / 1e6, 2)])


def tamano_mb(url):
    try:
        r = requests.head(url, allow_redirects=True, timeout=60)
        return int(r.headers.get("Content-Length", 0)) / 1e6 or None
    except requests.RequestException:
        return None


def bajar(fuente, url, destino):
    """Descarga completa de un archivo, si no existe y pesa menos del límite."""
    if destino.exists():
        print(f"Ya existe: {destino.relative_to(CRUDOS)}")
        return True
    mb = tamano_mb(url)
    if mb and mb > LIMITE_MB:
        print(f"No se baja {url}: pesa {mb:.0f} MB, más de {LIMITE_MB} MB")
        return False
    destino.parent.mkdir(parents=True, exist_ok=True)
    print(f"Descargando {destino.name}" + (f" ({mb:.0f} MB)" if mb else ""), flush=True)
    r = requests.get(url, timeout=600)
    r.raise_for_status()
    destino.write_bytes(r.content)
    anotar(fuente, url, destino)
    return True


def censo(anio, url):
    """Lee el censo comprimido en línea y guarda solo el maíz por condado de IA, IL e IN."""
    destino = DESTINO / "censo" / f"censo_{anio}_maiz_condados.csv"
    if destino.exists():
        print(f"Ya existe: {destino.relative_to(CRUDOS)}")
        return
    mb = tamano_mb(url)
    if mb and mb > LIMITE_MB:
        print(f"No se baja el censo {anio}: pesa {mb:.0f} MB")
        return
    destino.parent.mkdir(parents=True, exist_ok=True)
    print(f"Leyendo el censo {anio}; se guardan solo las filas de maíz por condado", flush=True)
    filas = 0
    with requests.get(url, stream=True, timeout=600) as r, open(destino, "w", encoding="utf-8", newline="") as salida:
        r.raise_for_status()
        mb = mb or int(r.headers.get("Content-Length", 0)) / 1e6 or None
        if mb and mb > LIMITE_MB:
            raise RuntimeError(f"El censo {anio} pesa {mb:.0f} MB")
        texto = io.TextIOWrapper(gzip.GzipFile(fileobj=r.raw), encoding="latin-1")
        encabezado = next(texto).rstrip("\n").split("\t")
        i = {c: encabezado.index(c) for c in ["COMMODITY_DESC", "STATE_ALPHA", "AGG_LEVEL_DESC"]}
        salida.write("\t".join(encabezado) + "\n")
        for linea in texto:
            campos = linea.rstrip("\n").split("\t")
            if (campos[i["COMMODITY_DESC"]] == "CORN" and campos[i["AGG_LEVEL_DESC"]] == "COUNTY"
                    and campos[i["STATE_ALPHA"]] in ESTADOS):
                salida.write(linea if linea.endswith("\n") else linea + "\n")
                filas += 1
    anotar(f"Censo Agropecuario {anio}, archivo masivo de Quick Stats - USDA NASS (solo maíz por condado de IA, IL, IN)",
           url, destino, mb)
    print(f"Censo {anio}: {filas:,} filas de maíz por condado")


def cpi():
    """CPI-U anual (promedio de los 12 meses). La API v1 entrega a lo sumo 10 años por consulta."""
    destino = DESTINO / "precios" / "cpi_u_bls.csv"
    if destino.exists():
        print(f"Ya existe: {destino.relative_to(CRUDOS)}")
        return
    destino.parent.mkdir(parents=True, exist_ok=True)
    filas = []
    for ini in range(ANIO_INI, ANIO_FIN + 1, 10):
        # La API solo respeta el rango de años si se pide por POST
        r = requests.post(BLS, json={"seriesid": [SERIE_CPI], "startyear": str(ini), "endyear": str(min(ini + 9, ANIO_FIN))}, timeout=120)
        r.raise_for_status()
        j = r.json()
        if j.get("status") != "REQUEST_SUCCEEDED":
            raise RuntimeError(f"BLS respondió: {j.get('message')}")
        for d in j["Results"]["series"][0]["data"]:
            # Un mes sin publicar viene como "-": se omite y se avisa
            if d["value"].strip() == "-":
                print(f"CPI-U sin dato: {d['year']} {d['periodName']}")
            elif d["period"].startswith("M") and d["period"] != "M13":
                filas.append((int(d["year"]), int(d["period"][1:]), float(d["value"])))
    with open(destino, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["anio", "mes", "cpi_u"])
        w.writerows(sorted(set(filas)))
    anotar("CPI-U, todos los artículos, promedio de ciudades de EE. UU. (CUUR0000SA0) - BLS API v1", BLS, destino)
    print(f"CPI-U: {len(filas)} meses")


def main():
    for codigo, nombre in [("tmaxcy", "Temperatura máxima mensual por condado"), ("pdsicy", "Índice de sequía de Palmer mensual por condado")]:
        archivo = f"climdiv-{codigo}-{VERSION_NOAA}"
        bajar(f"{nombre} - NOAA NCEI nClimDiv", NOAA + archivo, DESTINO / "noaa" / archivo)
    bajar("Lectura de los archivos de condado - NOAA NCEI nClimDiv", NOAA + "county-readme.txt", DESTINO / "noaa" / "county-readme.txt")
    for anio, url in CENSOS.items():
        try:
            censo(anio, url)
        except (requests.RequestException, RuntimeError) as e:
            (DESTINO / "censo" / f"censo_{anio}_maiz_condados.csv").unlink(missing_ok=True)
            print(f"No se pudo leer el censo {anio}: {e}. Se sigue sin el dato de riego.")
    bajar("Feed Grains Yearbook Tables, todos los años - USDA ERS", ERS, DESTINO / "precios" / "ers_feed_grains_yearbook.csv")
    cpi()
    print("Listo. Revisar datos/crudos/registro_descargas.csv")


if __name__ == "__main__":
    main()
