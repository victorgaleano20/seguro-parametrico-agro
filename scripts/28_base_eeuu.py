"""
28_base_eeuu.py
Fase 1 del seguro de sequía para el maíz de EE. UU.: base condado x año con todas las variables
(plan en docs/bitacora.md, 2026-11-04).

Parte de eeuu_base_ciclos.csv (script 08: rendimiento de NASS y filtros de calidad) y agrega:
  - Lluvia CHIRPS de mayo a septiembre como % de lo normal de 1981-1994, racha de meses secos y déficit de julio y agosto.
  - Temperatura máxima de junio a agosto (diferencia en °C frente a 1981-1994) y sequía de Palmer de junio a agosto (NOAA).
  - Fracción del maíz para grano cosechado con riego (censos de NASS) y ubicación del condado.
  - Pérdida de la partición fija, con tendencia ajustada solo con años <= 2018.
Todas las variables se conocen al final de septiembre del año de cosecha. No usa rendimientos de años anteriores.

Requiere 08 y 27. Salida: datos/procesados/eeuu_sequia_base.csv
Uso:  python scripts/28_base_eeuu.py
"""
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
import comun  # noqa: E402

CRUDOS = RAIZ / "datos" / "crudos" / "eeuu"
PROCESADOS = RAIZ / "datos" / "procesados"

ESTADOS_NOAA = {"11": "17", "12": "18", "13": "19"}     # código de estado de NOAA -> FIPS (Illinois, Indiana, Iowa)
NOAA_FALTANTE = -99.0                                   # NOAA marca los faltantes con -99,99
NORMAL_INI, NORMAL_FIN = 1981, 1994                     # lo normal: antes del primer año que se predice
MESES_LLUVIA = {5: "may", 6: "jun", 7: "jul", 8: "ago", 9: "sep"}
MESES_VERANO = {6: "jun", 7: "jul", 8: "ago"}
SECO_PCT = 75                                           # mes seco: lluvia < 75 % de lo normal
PISO_NORMAL_MM, TOPE_PCT = 10, 300
MIN_ANIOS_DATO = 15
FIN_DECISIONES = 2018                                   # último año de validación de la partición fija
MIN_ANIOS_TENDENCIA = 10


def leer_noaa(codigo):
    """Archivo mensual por condado de nClimDiv, a formato largo: unidad, anio, mes, valor."""
    ruta = next((CRUDOS / "noaa").glob(f"climdiv-{codigo}-*"))
    filas = []
    with open(ruta, encoding="latin-1") as f:
        for linea in f:
            estado = linea[:2]
            if estado not in ESTADOS_NOAA:
                continue
            anio = int(linea[7:11])
            if anio < NORMAL_INI:
                continue
            valores = [float(v) for v in linea[11:].split()]
            for mes, v in enumerate(valores, start=1):
                filas.append((ESTADOS_NOAA[estado] + linea[2:5], anio, mes, np.nan if v <= NOAA_FALTANTE else v))
    return pd.DataFrame(filas, columns=["unidad", "anio", "mes", "valor"])


def variables_lluvia():
    m = pd.read_csv(PROCESADOS / "chirps_mensual_condados_eeuu.csv", dtype={"fips": str}).rename(columns={"fips": "unidad"})
    m = m[m["mes"].isin(MESES_LLUVIA) & (m["anio"] <= 2025)]
    normal = m[m["anio"].between(NORMAL_INI, NORMAL_FIN)].groupby(["unidad", "mes"])["lluvia_mm"].mean().rename("normal")
    m = m.merge(normal.reset_index(), on=["unidad", "mes"])
    m["pct"] = (100 * m["lluvia_mm"] / m["normal"].clip(lower=PISO_NORMAL_MM)).clip(upper=TOPE_PCT)
    pct = m.pivot_table(index=["unidad", "anio"], columns="mes", values="pct")
    mm = m.pivot_table(index=["unidad", "anio"], columns="mes", values="lluvia_mm")
    nor = m.pivot_table(index=["unidad", "anio"], columns="mes", values="normal")

    x = pct.rename(columns=lambda c: f"lluvia_{MESES_LLUVIA[c]}")
    seco = (pct < SECO_PCT).to_numpy()
    racha = np.zeros(len(seco), dtype=int)
    actual = np.zeros(len(seco), dtype=int)
    for j in range(seco.shape[1]):
        actual = np.where(seco[:, j], actual + 1, 0)
        racha = np.maximum(racha, actual)
    x["racha_meses_secos"] = racha
    x["deficit_jul_ago"] = (100 - 100 * (mm[7] + mm[8]) / (nor[7] + nor[8])).clip(lower=0)
    x["lluvia_jun_ago_mm"] = mm[6] + mm[7] + mm[8]
    return x.reset_index()


def variables_noaa():
    t = leer_noaa("tmaxcy")
    t = t[t["mes"].isin(MESES_VERANO)]
    normal = t[t["anio"].between(NORMAL_INI, NORMAL_FIN)].groupby(["unidad", "mes"])["valor"].mean().rename("normal")
    t = t.merge(normal.reset_index(), on=["unidad", "mes"])
    t["dif_c"] = (t["valor"] - t["normal"]) * 5 / 9                    # grados Fahrenheit a diferencia en Celsius
    tmax = t.pivot_table(index=["unidad", "anio"], columns="mes", values="dif_c").rename(columns=lambda c: f"tmax_{MESES_VERANO[c]}")
    p = leer_noaa("pdsicy")
    p = p[p["mes"].isin(MESES_VERANO)]
    pdsi = p.pivot_table(index=["unidad", "anio"], columns="mes", values="valor").rename(columns=lambda c: f"palmer_{MESES_VERANO[c]}")
    return pd.concat([tmax, pdsi], axis=1).reset_index()


def riego():
    """Fracción del maíz para grano cosechado con riego, promedio de los censos disponibles hasta 2017.
    Un condado sin fila de riego en un censo que sí reporta el total se toma como 0; un dato oculto, (D), queda vacío."""
    partes = [pd.read_csv(f, sep="\t", dtype=str) for f in sorted((CRUDOS / "censo").glob("censo_*_maiz_condados.csv"))]
    if not partes:
        print("Sin censos de riego (los archivos masivos de NASS respondieron 404): la fracción con riego queda vacía")
        return pd.DataFrame({"unidad": pd.Series(dtype=str), "fraccion_riego": pd.Series(dtype=float)})
    c = pd.concat(partes, ignore_index=True)
    c = c[(c["DOMAIN_DESC"] == "TOTAL") & (c["SOURCE_DESC"] == "CENSUS")]
    c["unidad"] = c["STATE_FIPS_CODE"].str.zfill(2) + c["COUNTY_CODE"].str.zfill(3)
    c["valor"] = pd.to_numeric(c["VALUE"].str.replace(",", "").str.strip(), errors="coerce")
    c["anio"] = c["YEAR"].astype(int)
    c = c.drop_duplicates(["unidad", "anio", "SHORT_DESC"])
    total = c[c["SHORT_DESC"] == "CORN, GRAIN - ACRES HARVESTED"].set_index(["unidad", "anio"])["valor"]
    regado = c[c["SHORT_DESC"] == "CORN, GRAIN, IRRIGATED - ACRES HARVESTED"].set_index(["unidad", "anio"])["valor"]
    oculto = c[(c["SHORT_DESC"] == "CORN, GRAIN, IRRIGATED - ACRES HARVESTED") & c["valor"].isna()].set_index(["unidad", "anio"]).index
    r = pd.DataFrame({"total": total}).join(regado.rename("regado"))
    r["regado"] = r["regado"].fillna(0)
    r.loc[r.index.isin(oculto), "regado"] = np.nan
    r["fraccion"] = (r["regado"] / r["total"]).clip(upper=1)
    r = r[r.index.get_level_values("anio") <= FIN_DECISIONES]
    anios = sorted(r.index.get_level_values("anio").unique())
    print(f"Censos con riego: {anios}")
    return r.groupby("unidad")["fraccion"].mean().rename("fraccion_riego").reset_index()


def ubicacion():
    cond = gpd.read_file("zip://" + str(CRUDOS / "condados" / "cb_2023_us_county_500k.zip"))
    cond = cond[cond["STATEFP"].isin(ESTADOS_NOAA.values())]
    punto = cond.geometry.representative_point()
    return pd.DataFrame({"unidad": cond["GEOID"].to_numpy(), "latitud": punto.y.to_numpy(), "longitud": punto.x.to_numpy()})


def main():
    us = pd.read_csv(PROCESADOS / "eeuu_base_ciclos.csv", dtype={"fips": str})
    c = us[us["valido"].astype(bool)].rename(columns={"fips": "unidad", "state_alpha": "nombre_grupo", "county_name": "nombre"})
    c = c[c.groupby("unidad")["anio"].transform("size") >= MIN_ANIOS_DATO].copy()
    c["grupo"] = c["unidad"].str[:2]
    c["rendimiento_bu_acre"] = c["produccion"] / c["area_cosechada"]
    c = c[["unidad", "grupo", "nombre_grupo", "nombre", "anio", "rendimiento_t_ha", "rendimiento_bu_acre", "produccion",
           "area_cosechada"]].rename(columns={"area_cosechada": "area_cosechada_acres"})

    # Pérdida de la partición fija: la tendencia solo ve años de entrenamiento y validación
    t = comun.tendencia(c, FIN_DECISIONES, MIN_ANIOS_TENDENCIA).rename(columns={"esperado": "rend_esperado_t_ha", "relativo": "rend_relativo"})
    b = c.merge(t, on=["unidad", "anio"])
    b["perdida"] = b["rend_relativo"] <= comun.UMBRAL_PERDIDA
    b["faltante"] = (1 - b["rend_relativo"].clip(0, 3)).clip(lower=0)

    b = b.merge(variables_lluvia(), on=["unidad", "anio"]).merge(variables_noaa(), on=["unidad", "anio"], how="left")
    b = b.merge(riego(), on="unidad", how="left").merge(ubicacion(), on="unidad", how="left")
    entrenamiento, validacion, prueba = comun.particion(sorted(b["anio"].unique()))
    b["grupo_tiempo"] = np.select([b["anio"].isin(entrenamiento), b["anio"].isin(validacion)], ["entrenamiento", "validacion"], "prueba")
    b = b.sort_values(["unidad", "anio"])
    b.to_csv(PROCESADOS / "eeuu_sequia_base.csv", index=False)

    print(f"Años: entrenamiento {entrenamiento[0]}-{entrenamiento[-1]}, validación {validacion[0]}-{validacion[-1]}, prueba {prueba[0]}-{prueba[-1]}")
    print(f"Base: {len(b):,} filas, {b['unidad'].nunique()} condados, {b['perdida'].mean():.1%} de pérdidas")
    print(b.groupby("grupo_tiempo").agg(filas=("anio", "size"), condados=("unidad", "nunique"), perdida=("perdida", "mean")).round(3).to_string())
    faltan = b.isna().sum()
    print("Valores vacíos por variable:\n" + faltan[faltan > 0].to_string())
    print(f"Riego: mediana {b.groupby('unidad')['fraccion_riego'].first().median():.3f}, "
          f"condados con 10 % o más: {(b.groupby('unidad')['fraccion_riego'].first() >= 0.10).sum()}")
    print("Pérdidas por año:\n" + b.groupby("anio")["perdida"].agg(["size", "mean"]).round(3).T.to_string())


if __name__ == "__main__":
    main()
