"""
34_base_ciegas.py
Fase 1 de la prueba a ciegas (plan en docs/plan_prueba_ciegas.md): base condado x año de los siete estados nuevos, con
EXACTAMENTE la misma construcción de 08 y 28, y unión con la base de Iowa, Illinois e Indiana.

  1. Lluvia CHIRPS mensual por condado (mismo método de 08, con comun.py) -> chirps_mensual_condados_nuevos.csv
  2. Rendimiento NASS, filtros de calidad (repetidos, salto de área, 15 años mínimo) y pérdida con tendencia <= 2018.
  3. Variables de lluvia, temperatura máxima y Palmer (mismas funciones de 28, con los códigos de NOAA de los 10 estados).
  4. Riego de los censos (fracción del maíz para grano cosechado con riego), en una tabla aparte: el modelo congelado NO lo usa.
Validación: aplicado a los tres estados originales, el código nuevo debe reproducir eeuu_sequia_base.csv.

Requiere 33 (descargas) y 08, 28 (bases de Iowa, Illinois e Indiana).
Salidas en datos/procesados/: chirps_mensual_condados_nuevos.csv, eeuu_ciegas_base.csv, eeuu_riego_censos.csv,
  eeuu_ciegas_calidad.csv, eeuu_ciegas_calidad_anual.csv
Uso:  python scripts/34_base_ciegas.py
"""
import importlib
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
import comun  # noqa: E402
e28 = importlib.import_module("28_base_eeuu")

EEUU = RAIZ / "datos" / "crudos" / "eeuu"
PROCESADOS = RAIZ / "datos" / "procesados"

# FIPS de estado -> (sigla, código de estado de NOAA nClimDiv, nombre)
NUEVOS = {"31": ("NE", "25", "Nebraska"), "27": ("MN", "21", "Minnesota"), "39": ("OH", "33", "Ohio"), "29": ("MO", "23", "Missouri"),
          "20": ("KS", "14", "Kansas"), "46": ("SD", "39", "South Dakota"), "55": ("WI", "47", "Wisconsin")}
ORIGINALES = {"17": ("IL", "11", "Illinois"), "18": ("IN", "12", "Indiana"), "19": ("IA", "13", "Iowa")}
ANIO_INI, ANIO_FIN = 1981, 2025


# ---------------------------------------------------------------- lluvia
def lluvia_mensual_condados(estados):
    cond = gpd.read_file("zip://" + str(EEUU / "condados" / "cb_2023_us_county_500k.zip"))
    cond = cond[cond["STATEFP"].isin(estados)].copy()
    return cond, cond


def chirps_nuevos():
    destino = PROCESADOS / "chirps_mensual_condados_nuevos.csv"
    if destino.exists():
        return pd.read_csv(destino, dtype={"fips": str})
    cond, _ = lluvia_mensual_condados(NUEVOS)
    archivos = sorted((EEUU / "chirps_nuevos").glob("chirps_mensual_nuevos_*.nc"))
    anios = [int(a.stem[-4:]) for a in archivos]
    faltan = sorted(set(range(ANIO_INI, ANIO_FIN + 1)) - set(anios))
    if faltan:
        raise RuntimeError(f"Faltan archivos CHIRPS de los años {faltan}")
    print(f"Leyendo {len(archivos)} archivos CHIRPS para {len(cond)} condados de los estados nuevos", flush=True)
    m = comun.lluvia_mensual(cond, archivos, columna="GEOID", nombre_codigo="fips")
    m.to_csv(destino, index=False)
    sin = m["lluvia_mm"].isna().sum()
    if sin:
        print(f"Aviso: {sin:,} valores condado-mes sin dato CHIRPS")
    return m


def variables_lluvia(m):
    """Misma lógica de 28_base_eeuu.variables_lluvia, recibiendo la tabla mensual."""
    m = m.rename(columns={"fips": "unidad"})
    m = m[m["mes"].isin(e28.MESES_LLUVIA) & (m["anio"] <= ANIO_FIN)]
    normal = m[m["anio"].between(e28.NORMAL_INI, e28.NORMAL_FIN)].groupby(["unidad", "mes"])["lluvia_mm"].mean().rename("normal")
    m = m.merge(normal.reset_index(), on=["unidad", "mes"])
    m["pct"] = (100 * m["lluvia_mm"] / m["normal"].clip(lower=e28.PISO_NORMAL_MM)).clip(upper=e28.TOPE_PCT)
    pct = m.pivot_table(index=["unidad", "anio"], columns="mes", values="pct")
    mm = m.pivot_table(index=["unidad", "anio"], columns="mes", values="lluvia_mm")
    nor = m.pivot_table(index=["unidad", "anio"], columns="mes", values="normal")
    x = pct.rename(columns=lambda c: f"lluvia_{e28.MESES_LLUVIA[c]}")
    seco = (pct < e28.SECO_PCT).to_numpy()
    racha = np.zeros(len(seco), dtype=int)
    actual = np.zeros(len(seco), dtype=int)
    for j in range(seco.shape[1]):
        actual = np.where(seco[:, j], actual + 1, 0)
        racha = np.maximum(racha, actual)
    x["racha_meses_secos"] = racha
    x["deficit_jul_ago"] = (100 - 100 * (mm[7] + mm[8]) / (nor[7] + nor[8])).clip(lower=0)
    x["lluvia_jun_ago_mm"] = mm[6] + mm[7] + mm[8]
    return x.reset_index()


# ---------------------------------------------------------------- NASS
def leer_nass_nuevos(nombre):
    partes = [pd.read_csv(f, dtype=str) for f in sorted((EEUU / "nass_nuevos").glob(f"nass_maiz_grano_??_{nombre}.csv"))]
    d = pd.concat(partes, ignore_index=True)
    d = d[d["county_code"] != "998"]
    d["fips"] = d["state_fips_code"].str.zfill(2) + d["county_code"].str.zfill(3)
    d["valor"] = pd.to_numeric(d["Value"].str.replace(",", ""), errors="coerce")
    d = d[d["state_fips_code"].isin(NUEVOS)]
    return d.set_index(["fips", d["year"].astype(int).rename("anio")])["valor"].rename(nombre), d


def rendimiento_nuevos():
    """Igual que 08_base_eeuu.rendimiento_nass y los filtros de calidad, para los estados nuevos."""
    prod, d_prod = leer_nass_nuevos("produccion")
    area, _ = leer_nass_nuevos("area_cosechada")
    d = pd.concat([prod, area], axis=1).reset_index()
    nombres = d_prod.drop_duplicates("fips").set_index("fips")[["state_alpha", "county_name"]]
    d = d.merge(nombres, left_on="fips", right_index=True, how="left")
    d["con_dato"] = (d["produccion"] > 0) & (d["area_cosechada"] > 0)
    d["rendimiento_t_ha"] = (d["produccion"] / d["area_cosechada"] * comun.BU_ACRE_A_T_HA).where(d["con_dato"])
    d["area_cosechada_ha"] = d["area_cosechada"] * 0.404686
    d = d.sort_values(["fips", "anio"])
    d = d[d["anio"] >= ANIO_INI]
    previo = d.groupby("fips")[["rendimiento_t_ha", "anio"]].shift()
    d["repetido"] = ((d["rendimiento_t_ha"].round(3) == previo["rendimiento_t_ha"].round(3)) & (d["anio"] == previo["anio"] + 1))
    con = d[d["con_dato"]]
    cal = con.groupby("fips").agg(estado=("state_alpha", "first"), condado=("county_name", "first"), area_mediana_ha=("area_cosechada_ha", "median"))
    cal["salto_area_veces"] = con.groupby("fips")["area_cosechada_ha"].apply(comun.salto_de_nivel).round(1)
    cal["excluido_salto_area"] = cal["salto_area_veces"] >= comun.SALTO_AREA_MAX
    d = d.merge(cal[["excluido_salto_area"]], left_on="fips", right_index=True, how="left")
    d["excluido_salto_area"] = d["excluido_salto_area"].fillna(True).astype(bool)
    return d, cal


def base_estados_nuevos(lluvia, noaa):
    d, cal = rendimiento_nuevos()
    llov = lluvia[["fips", "anio"]].drop_duplicates().rename(columns={"fips": "unidad"})
    d = d.rename(columns={"fips": "unidad"}).merge(llov.assign(hay_lluvia=True), on=["unidad", "anio"], how="left")
    d["valido"] = d["con_dato"] & ~d["repetido"] & ~d["excluido_salto_area"] & d["hay_lluvia"].fillna(False).astype(bool)
    c = d[d["valido"]].copy()
    c = c[c.groupby("unidad")["anio"].transform("size") >= e28.MIN_ANIOS_DATO].copy()
    c["grupo"] = c["unidad"].str[:2]
    c["nombre_grupo"] = c["state_alpha"]
    c["nombre"] = c["county_name"]
    c["rendimiento_bu_acre"] = c["produccion"] / c["area_cosechada"]
    c = c.rename(columns={"area_cosechada": "area_cosechada_acres"})
    c = c[["unidad", "grupo", "nombre_grupo", "nombre", "anio", "rendimiento_t_ha", "rendimiento_bu_acre", "produccion", "area_cosechada_acres"]]
    t = comun.tendencia(c, e28.FIN_DECISIONES, e28.MIN_ANIOS_TENDENCIA).rename(columns={"esperado": "rend_esperado_t_ha", "relativo": "rend_relativo"})
    b = c.merge(t, on=["unidad", "anio"])
    b["perdida"] = b["rend_relativo"] <= comun.UMBRAL_PERDIDA
    b["faltante"] = (1 - b["rend_relativo"].clip(0, 3)).clip(lower=0)
    b = b.merge(variables_lluvia(lluvia), on=["unidad", "anio"]).merge(noaa, on=["unidad", "anio"], how="left")
    cond = gpd.read_file("zip://" + str(EEUU / "condados" / "cb_2023_us_county_500k.zip"))
    cond = cond[cond["STATEFP"].isin(NUEVOS)]
    punto = cond.geometry.representative_point()
    ubic = pd.DataFrame({"unidad": cond["GEOID"].to_numpy(), "latitud": punto.y.to_numpy(), "longitud": punto.x.to_numpy()})
    b = b.merge(ubic, on="unidad", how="left")
    resumen = d[d["con_dato"]].groupby("state_alpha").agg(condados_con_dato=("unidad", "nunique"), condado_anios_con_dato=("anio", "size"),
                                                           repetidos=("repetido", "sum"))
    resumen["condados_con_salto_de_area"] = cal.groupby("estado")["excluido_salto_area"].sum()
    resumen["condados_en_la_base"] = b.groupby("nombre_grupo")["unidad"].nunique()
    resumen["condado_anios_en_la_base"] = b.groupby("nombre_grupo").size()
    return b, resumen


# ---------------------------------------------------------------- riego
def riego_censos():
    """Fracción del maíz para grano cosechado con riego, por condado y año de censo (API de NASS, censos 1997-2022)."""
    partes = [pd.read_csv(f, dtype=str) for f in sorted((EEUU / "censo_api").glob("censo_riego_maiz_??.csv"))]
    c = pd.concat(partes, ignore_index=True)
    c = c[(c["domain_desc"] == "TOTAL") & (c["source_desc"] == "CENSUS") & (c["county_code"] != "998")]
    c["unidad"] = c["state_fips_code"].str.zfill(2) + c["county_code"].str.zfill(3)
    c["valor"] = pd.to_numeric(c["Value"].str.replace(",", "").str.strip(), errors="coerce")
    c["anio_censo"] = c["year"].astype(int)
    c = c.drop_duplicates(["unidad", "anio_censo", "short_desc"])
    total = c[c["short_desc"] == "CORN, GRAIN - ACRES HARVESTED"].set_index(["unidad", "anio_censo"])["valor"]
    regado = c[c["short_desc"] == "CORN, GRAIN, IRRIGATED - ACRES HARVESTED"].set_index(["unidad", "anio_censo"])["valor"]
    oculto = c[(c["short_desc"] == "CORN, GRAIN, IRRIGATED - ACRES HARVESTED") & c["valor"].isna()].set_index(["unidad", "anio_censo"]).index
    r = pd.DataFrame({"total_acres": total}).join(regado.rename("regado_acres"))
    # Igual que 28: sin fila de riego en un censo que sí reporta el total, se toma como 0; un dato oculto queda vacío
    r["regado_acres"] = r["regado_acres"].fillna(0)
    r.loc[r.index.isin(oculto), "regado_acres"] = np.nan
    r["fraccion"] = (r["regado_acres"] / r["total_acres"]).clip(upper=1)
    return r.reset_index()


def guardar_calidad_anual():
    """Calidad por condado y año (con dato, repetido, área) de los 10 estados: el semáforo la recalcula con años anteriores a t."""
    d, _ = rendimiento_nuevos()
    nuevo = d.rename(columns={"fips": "unidad"})[["unidad", "state_alpha", "county_name", "anio", "con_dato", "repetido", "area_cosechada_ha"]]
    ant = pd.read_csv(PROCESADOS / "eeuu_base_ciclos.csv", dtype={"fips": str}).rename(columns={"fips": "unidad"})
    ant = ant[["unidad", "state_alpha", "county_name", "anio", "con_dato", "repetido", "area_cosechada_ha"]]
    q = pd.concat([ant, nuevo], ignore_index=True)
    q = q[q["con_dato"].astype(bool)].copy()
    q["repetido"] = q["repetido"].astype(bool)
    q.to_csv(PROCESADOS / "eeuu_ciegas_calidad_anual.csv", index=False)


def main():
    nuevos_lluvia = chirps_nuevos()
    todos = {**ORIGINALES, **NUEVOS}
    e28.ESTADOS_NOAA = {noaa: fips for fips, (_, noaa, _) in todos.items()}
    noaa = e28.variables_noaa()

    # Validación del código con los tres estados originales
    original = pd.read_csv(PROCESADOS / "eeuu_sequia_base.csv", dtype={"unidad": str, "grupo": str})
    ll_orig = pd.read_csv(PROCESADOS / "chirps_mensual_condados_eeuu.csv", dtype={"fips": str})
    v = variables_lluvia(ll_orig).merge(noaa, on=["unidad", "anio"], how="left")
    cols = [c for c in v.columns if c not in ("unidad", "anio")]
    j = original.merge(v, on=["unidad", "anio"], suffixes=("", "_nuevo"))
    maximo = max(np.nanmax(np.abs(j[c] - j[c + "_nuevo"])) for c in cols)
    print(f"Validación con Iowa, Illinois e Indiana: {len(j):,} filas, {len(cols)} variables, diferencia máxima {maximo:.2e}")
    if maximo > 1e-6:
        raise RuntimeError("El código nuevo no reproduce la base original")

    b_nuevos, resumen = base_estados_nuevos(nuevos_lluvia, noaa)
    guardar_calidad_anual()
    original = original.drop(columns=["fraccion_riego", "grupo_tiempo"], errors="ignore")
    b = pd.concat([original, b_nuevos[original.columns]], ignore_index=True).sort_values(["unidad", "anio"])
    b["estado"] = b["nombre_grupo"]
    b.to_csv(PROCESADOS / "eeuu_ciegas_base.csv", index=False)
    # Versión liviana para el simulador (la base completa pesa más de 10 MB y no se sube a git)
    b[["unidad", "anio", "nombre", "nombre_grupo", "lluvia_jun_ago_mm", "latitud", "longitud"]].to_csv(PROCESADOS / "eeuu_ciegas_app.csv", index=False)
    resumen.to_csv(PROCESADOS / "eeuu_ciegas_calidad.csv")
    r = riego_censos()
    r.to_csv(PROCESADOS / "eeuu_riego_censos.csv", index=False)

    pd.set_option("display.width", 200)
    print("Calidad del dato en los estados nuevos:\n" + resumen.to_string())
    print(f"Base de los diez estados: {len(b):,} condado-años, {b['unidad'].nunique()} condados")
    print(f"Censos de riego: {r['unidad'].nunique()} condados, años {sorted(r['anio_censo'].unique())}")
    faltan = b_nuevos.isna().sum()
    print("Valores vacíos en los estados nuevos:\n" + faltan[faltan > 0].to_string())


if __name__ == "__main__":
    main()
