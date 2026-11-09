"""
33_adquisicion_ciegas.py
Fase 1 de la prueba a ciegas (plan en docs/plan_prueba_ciegas.md, congelado el 2026-11-05).

Baja los datos de los siete estados nuevos (Nebraska, Minnesota, Ohio, Missouri, Kansas, South Dakota y Wisconsin):
  - NASS (API, con la clave en la variable de entorno NASS_API_KEY): producción, área cosechada, rendimiento y área sembrada
    de maíz por condado, 1981-2025. Se guarda en datos/crudos/eeuu/nass_nuevos/ (no en la carpeta de los 3 estados originales).
  - NASS (API): área de maíz para grano cosechada, total y con riego, de los censos agropecuarios 1997, 2002, 2007, 2012,
    2017 y 2022, para los siete estados nuevos y los tres originales.
  - CHIRPS mensual de la IRI Data Library para un recuadro que cubre los siete estados, un archivo por año.
Todo se anota en datos/crudos/registro_descargas.csv, sin la clave. No descarga nada de más de 500 MB.
Uso:  python scripts/33_adquisicion_ciegas.py
"""
import csv
import datetime as dt
import os
import sys
import time
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
CRUDOS = RAIZ / "datos" / "crudos"
EEUU = CRUDOS / "eeuu"
REGISTRO = CRUDOS / "registro_descargas.csv"
LIMITE_MB = 500
NASS_API = "https://quickstats.nass.usda.gov/api/api_GET/"

ESTADOS_NUEVOS = ["NE", "MN", "OH", "MO", "KS", "SD", "WI"]      # en orden de prioridad
ESTADOS_ORIGINALES = ["IA", "IL", "IN"]
ANIO_INI, ANIO_FIN = 1981, 2025
CENSOS = [1997, 2002, 2007, 2012, 2017, 2022]
SERIES = {"CORN, GRAIN - PRODUCTION, MEASURED IN BU": "produccion",
          "CORN, GRAIN - ACRES HARVESTED": "area_cosechada",
          "CORN, GRAIN - YIELD, MEASURED IN BU / ACRE": "rendimiento",
          "CORN - ACRES PLANTED": "area_sembrada"}
SERIES_CENSO = ["CORN, GRAIN - ACRES HARVESTED", "CORN, GRAIN, IRRIGATED - ACRES HARVESTED"]
CAJA_NUEVOS = (-104.1, -80.4, 36.0, 49.5)                        # lon_min, lon_max, lat_min, lat_max: cubre los 7 estados


def anotar(fuente, url, destino):
    nuevo = not REGISTRO.exists()
    with open(REGISTRO, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(["fuente", "url", "archivo", "fecha_descarga", "tamano_mb"])
        w.writerow([fuente, url, destino.relative_to(CRUDOS).as_posix(), dt.date.today().isoformat(),
                    round(destino.stat().st_size / 1e6, 2)])


def clave():
    k = os.environ.get("NASS_API_KEY", "").strip()
    if not k:
        sys.exit("Falta la variable de entorno NASS_API_KEY (ver docs/plan_prueba_ciegas.md).")
    return k


def consulta_nass(params):
    """Consulta a la API de NASS. Devuelve (texto_csv, url_sin_clave) o (None, mensaje) si falla o no hay datos."""
    k = clave()
    url_sin_clave = requests.Request("GET", NASS_API, params=params).prepare().url
    for intento in range(3):
        try:
            r = requests.get(NASS_API, params={"key": k, **params}, timeout=300)
        except requests.RequestException as e:
            time.sleep(5 * (intento + 1))
            ultimo = str(e)[:80]
            continue
        if r.status_code == 200:
            return r.text, url_sin_clave
        if r.status_code == 400:                    # NASS responde 400 cuando no hay registros
            return None, f"sin registros (400): {r.text[:80]}"
        ultimo = f"HTTP {r.status_code}"
        time.sleep(5 * (intento + 1))
    return None, ultimo


def nass_encuesta():
    for estado in ESTADOS_NUEVOS + ESTADOS_ORIGINALES:
        for short_desc, nombre in SERIES.items():
            if estado in ESTADOS_ORIGINALES and nombre != "area_sembrada":
                continue                                  # lo demás de los 3 originales ya está en eeuu/nass
            destino = EEUU / "nass_nuevos" / f"nass_maiz_grano_{estado}_{nombre}.csv"
            if destino.exists():
                print(f"Ya existe: {destino.name}")
                continue
            params = {"source_desc": "SURVEY", "agg_level_desc": "COUNTY", "state_alpha": estado, "short_desc": short_desc,
                      "reference_period_desc": "YEAR", "year__GE": ANIO_INI, "year__LE": ANIO_FIN, "format": "CSV"}
            texto, url = consulta_nass(params)
            if texto is None:
                print(f"NASS {estado} {nombre}: {url}")
                continue
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(texto, encoding="utf-8")
            anotar("NASS Quick Stats API - USDA (maíz, encuesta, condado)", url, destino)
            print(f"NASS {estado} {nombre}: {max(texto.count(chr(10)) - 1, 0)} filas")


def nass_censos():
    for estado in ESTADOS_NUEVOS + ESTADOS_ORIGINALES:
        destino = EEUU / "censo_api" / f"censo_riego_maiz_{estado}.csv"
        if destino.exists():
            print(f"Ya existe: {destino.name}")
            continue
        partes, cabecera = [], None
        for short_desc in SERIES_CENSO:
            for anio in CENSOS:
                params = {"source_desc": "CENSUS", "agg_level_desc": "COUNTY", "state_alpha": estado, "short_desc": short_desc,
                          "domain_desc": "TOTAL", "year": anio, "format": "CSV"}
                texto, url = consulta_nass(params)
                if texto is None:
                    print(f"Censo {anio} {estado} {short_desc}: {url}")
                    continue
                lineas = texto.splitlines()
                cabecera = cabecera or lineas[0]
                partes += lineas[1:]
        if not partes:
            print(f"Censo {estado}: sin filas")
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text("\n".join([cabecera] + partes) + "\n", encoding="utf-8")
        anotar("NASS Quick Stats API - USDA (maíz para grano, censos agropecuarios 1997-2022, total y con riego, condado)",
               NASS_API + "?source_desc=CENSUS&agg_level_desc=COUNTY&state_alpha=" + estado, destino)
        print(f"Censos {estado}: {len(partes)} filas")


def url_chirps(anio):
    lon_min, lon_max, lat_min, lat_max = CAJA_NUEVOS
    return ("https://iridl.ldeo.columbia.edu/SOURCES/.UCSB/.CHIRPS/.v2p0/.monthly/.global/.precipitation/"
            f"X/{lon_min}/{lon_max}/RANGEEDGES/Y/{lat_min}/{lat_max}/RANGEEDGES/"
            f"T/(Jan%20{anio})/(Dec%20{anio})/RANGEEDGES/data.nc")


def chirps(anios=None):
    total_mb = 0.0
    for anio in anios or range(ANIO_INI, ANIO_FIN + 1):
        destino = EEUU / "chirps_nuevos" / f"chirps_mensual_nuevos_{anio}.nc"
        if destino.exists():
            continue
        url = url_chirps(anio)
        destino.parent.mkdir(parents=True, exist_ok=True)
        temporal = destino.with_suffix(".nc.parcial")
        for intento in range(3):
            try:
                with requests.get(url, stream=True, timeout=600) as r:
                    r.raise_for_status()
                    with open(temporal, "wb") as f:
                        for bloque in r.iter_content(chunk_size=1 << 20):
                            f.write(bloque)
                temporal.rename(destino)
                break
            except requests.RequestException as e:
                temporal.unlink(missing_ok=True)
                print(f"CHIRPS {anio}: falló ({str(e)[:60]}), intento {intento + 1}")
                time.sleep(10)
        if destino.exists():
            total_mb += destino.stat().st_size / 1e6
            anotar("CHIRPS v2.0 mensual, recorte de los 7 estados nuevos - IRI Data Library / Climate Hazards Center UCSB", url, destino)
            print(f"CHIRPS {anio}: {destino.stat().st_size / 1e6:.1f} MB", flush=True)
            if total_mb > LIMITE_MB:
                print("Se pasa del límite de 500 MB: se detiene la descarga de CHIRPS")
                return


def main():
    pasos = sys.argv[1:] or ["nass", "censos", "chirps"]
    if "nass" in pasos:
        nass_encuesta()
    if "censos" in pasos:
        nass_censos()
    if "chirps" in pasos:
        chirps()
    if "chirps_prueba" in pasos:
        chirps([2012])
    print("Listo. Revisar datos/crudos/registro_descargas.csv")


if __name__ == "__main__":
    main()
