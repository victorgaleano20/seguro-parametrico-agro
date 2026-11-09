"""
49_temperatura_diaria.py
Temperatura diaria por condado (NOAA nClimGrid-Daily) y grados-día de calor útil y de calor dañino
(plan en docs/bitacora.md, 2026-11-08, quinta parte).

1. Descarga los promedios por condado que publica NOAA (temperatura máxima y mínima diarias, en °C), de mayo a
   septiembre de 1981 a 2025: https://www.ncei.noaa.gov/data/nclimgrid-daily/access/averages/<año>/<var>-<aaaamm>-cty-scaled.csv
   (si no existe la versión "scaled", se usa la "prelim"). Cada archivo trae todos los condados de EE. UU.; solo se guardan
   las filas de los diez estados del proyecto, en datos/crudos/eeuu/nclimgrid_diario/.
2. Calcula por condado, año y mes (junio, julio y agosto, y el total de junio a agosto), con el método del seno simple:
   - gd_10_29: grados-día entre 10 y 29 °C (calor útil para el maíz);
   - gd_29: grados-día por encima de 29 °C (calor dañino; Schlenker y Roberts, 2009);
   - dias_tmax_35: días con máxima de 35 °C o más.
Salida: datos/procesados/eeuu_grados_dia.csv
Uso:  python scripts/49_temperatura_diaria.py
"""
import csv
import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
CRUDOS = RAIZ / "datos" / "crudos"
DESTINO = CRUDOS / "eeuu" / "nclimgrid_diario"
REGISTRO = CRUDOS / "registro_descargas.csv"
PROCESADOS = RAIZ / "datos" / "procesados"
BASE_URL = "https://www.ncei.noaa.gov/data/nclimgrid-daily/access/averages"

# FIPS de los diez estados: Iowa, Illinois, Indiana, Nebraska, Minnesota, Ohio, Missouri, Kansas, South Dakota y Wisconsin
ESTADOS = {"19", "17", "18", "31", "27", "39", "29", "20", "46", "55"}
ANIOS = range(1981, 2026)
MESES = [5, 6, 7, 8, 9]
VARIABLES = ["tmax", "tmin"]
FALTANTE = -999.0
UMBRAL_UTIL, UMBRAL_DANINO = 10.0, 29.0
NOMBRE_MES = {6: "jun", 7: "jul", 8: "ago"}


def anotar(url, destino):
    nuevo = not REGISTRO.exists()
    REGISTRO.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRO, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(["fuente", "url", "archivo", "fecha_descarga", "tamano_mb"])
        w.writerow(["NOAA nClimGrid-Daily, promedios por condado (filtrado a 10 estados)", url,
                    destino.relative_to(CRUDOS).as_posix(), dt.date.today().isoformat(), round(destino.stat().st_size / 1e6, 3)])


def bajar(variable, anio, mes):
    """Descarga un mes de una variable y guarda solo los diez estados. Devuelve la ruta o None."""
    destino = DESTINO / f"{variable}_{anio}{mes:02d}.csv"
    if destino.exists():
        return destino
    for tipo in ("scaled", "prelim"):
        url = f"{BASE_URL}/{anio}/{variable}-{anio}{mes:02d}-cty-{tipo}.csv"
        try:
            r = requests.get(url, timeout=120)
        except requests.RequestException as e:
            print(f"ERROR de red en {url}: {e}")
            return None
        if r.status_code == 200:
            lineas = [l for l in r.text.splitlines() if l.startswith("cty,") and l.split(",")[1][:2] in ESTADOS]
            DESTINO.mkdir(parents=True, exist_ok=True)
            destino.write_text("\n".join(lineas) + "\n", encoding="utf-8")
            anotar(url, destino)
            return destino
    print(f"AVISO: no se encontró {variable} {anio}-{mes:02d}")
    return None


def leer(ruta, variable):
    filas = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        partes = linea.split(",")
        unidad, anio, mes = partes[1], int(partes[3]), int(partes[4])
        valores = np.array([float(v) for v in partes[6:]])
        for dia, v in enumerate(valores, start=1):
            if v > FALTANTE:
                filas.append((unidad, anio, mes, dia, v))
    return pd.DataFrame(filas, columns=["unidad", "anio", "mes", "dia", variable])


def grados_dia(tmin, tmax, umbral):
    """Grados-día por encima de un umbral con el método del seno simple (temperatura diaria como una curva seno)."""
    tmin, tmax = np.minimum(tmin, tmax), np.maximum(tmin, tmax)
    media, amplitud = (tmax + tmin) / 2, (tmax - tmin) / 2
    gd = np.zeros_like(media)
    todo_arriba = tmin >= umbral
    gd[todo_arriba] = media[todo_arriba] - umbral
    cruza = (tmax > umbral) & ~todo_arriba
    theta = np.arcsin(np.clip((umbral - media[cruza]) / np.where(amplitud[cruza] > 0, amplitud[cruza], 1e-9), -1, 1))
    gd[cruza] = ((media[cruza] - umbral) * (np.pi / 2 - theta) + amplitud[cruza] * np.cos(theta)) / np.pi
    return gd


def main():
    rutas = {v: [] for v in VARIABLES}
    total = len(ANIOS) * len(MESES) * len(VARIABLES)
    hechos = 0
    for anio in ANIOS:
        for mes in MESES:
            for variable in VARIABLES:
                ruta = bajar(variable, anio, mes)
                if ruta is not None:
                    rutas[variable].append(ruta)
                hechos += 1
        print(f"{anio}: {hechos}/{total} archivos", flush=True)

    d = leer_todo(rutas)
    print(f"Días con máxima y mínima: {len(d):,}; condados: {d['unidad'].nunique()}; años: {d['anio'].min()}-{d['anio'].max()}")
    d["gd_10_29"] = grados_dia(d["tmin"].to_numpy(), d["tmax"].to_numpy(), UMBRAL_UTIL) - grados_dia(d["tmin"].to_numpy(), d["tmax"].to_numpy(), UMBRAL_DANINO)
    d["gd_29"] = grados_dia(d["tmin"].to_numpy(), d["tmax"].to_numpy(), UMBRAL_DANINO)
    d["dias_tmax_35"] = (d["tmax"] >= 35).astype(int)

    verano = d[d["mes"].isin(NOMBRE_MES)]
    por_mes = verano.groupby(["unidad", "anio", "mes"])[["gd_10_29", "gd_29", "dias_tmax_35"]].sum().unstack("mes")
    por_mes.columns = [f"{v}_{NOMBRE_MES[m]}" for v, m in por_mes.columns]
    total_verano = verano.groupby(["unidad", "anio"]).agg(gd_10_29_jun_ago=("gd_10_29", "sum"), gd_29_jun_ago=("gd_29", "sum"),
                                                         dias_tmax_35_jun_ago=("dias_tmax_35", "sum"), dias_verano=("dia", "size"))
    salida = por_mes.join(total_verano).reset_index()
    salida = salida[salida["dias_verano"] == 92].drop(columns="dias_verano")       # solo veranos completos (92 días)
    salida.round(2).to_csv(PROCESADOS / "eeuu_grados_dia.csv", index=False)
    print(f"Guardado eeuu_grados_dia.csv: {len(salida):,} condado-años")
    print(salida.groupby("anio")["gd_29_jun_ago"].mean().round(1).sort_values(ascending=False).head(8).to_string())


def leer_todo(rutas):
    tmax = pd.concat([leer(r, "tmax") for r in rutas["tmax"]], ignore_index=True)
    tmin = pd.concat([leer(r, "tmin") for r in rutas["tmin"]], ignore_index=True)
    return tmax.merge(tmin, on=["unidad", "anio", "mes", "dia"])


if __name__ == "__main__":
    main()
