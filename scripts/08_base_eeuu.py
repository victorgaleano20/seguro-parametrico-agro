"""
08_base_eeuu.py
Base de análisis del maíz en Estados Unidos (Iowa, Illinois e Indiana), por condado y año,
por condado y año:
  1. Ventana del ciclo según el calendario de siembra y cosecha del USDA.
  2. Lluvia CHIRPS del ciclo, con déficit y exceso frente al promedio 1981-2025 del condado.
  3. Rendimiento = producción / área cosechada (NASS), en t/ha.
  4. Filtro de calidad: rendimiento repetido y cambio de nivel de área >= 5x.
  5. Tendencia lineal por condado y pérdida = rendimiento <= 80 % del esperado.
Usa las funciones de comun.py (lluvia por polígono, salto de nivel y tendencia).

Salidas en datos/procesados/: chirps_mensual_condados_eeuu.csv, eeuu_ventanas_ciclo.csv,
  eeuu_lluvia_ciclo.csv, eeuu_calidad_condados.csv, eeuu_base_ciclos.csv
Uso:  python scripts/08_base_eeuu.py
"""
import re
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
import comun  # noqa: E402

EEUU = RAIZ / "datos" / "crudos" / "eeuu"
PROCESADOS = RAIZ / "datos" / "procesados"

ESTADOS = {"19": "Iowa", "17": "Illinois", "18": "Indiana"}   # FIPS de estado
ANIO_INI, CLIMA_FIN = 1981, 2025
BU_ACRE_A_T_HA = comun.BU_ACRE_A_T_HA
MESES = {m: i + 1 for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}


# ---------------------------------------------------------------- 1. calendario
def ventanas_ciclo():
    """Mes del punto medio del rango 'most active' de siembra y de cosecha (tabla de maíz del USDA)."""
    texto = (EEUU / "calendario" / "planting-10-29-2010.txt").read_text(encoding="latin-1")
    tabla = texto.split("Corn for Grain Usual Planting and Harvesting Dates - States")[2]
    filas = []
    for estado in ESTADOS.values():
        linea = next(l for l in tabla.splitlines() if l.startswith(estado + " "))
        fechas = re.findall(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec) (\d+)", linea)
        # Orden: siembra (inicio, activo desde, activo hasta, fin), cosecha (igual)
        dias = [pd.Timestamp(2010, MESES[m[:3]], int(d)) for m, d in fechas]
        siembra = dias[1] + (dias[2] - dias[1]) / 2
        cosecha = dias[5] + (dias[6] - dias[5]) / 2
        filas.append({"estado": estado, "siembra_activa": f"{dias[1]:%d-%b} a {dias[2]:%d-%b}",
                      "cosecha_activa": f"{dias[5]:%d-%b} a {dias[6]:%d-%b}",
                      "mes_siembra": siembra.month, "mes_cosecha": cosecha.month,
                      "meses_ciclo": cosecha.month - siembra.month})
    v = pd.DataFrame(filas)
    print("Ventanas del ciclo (USDA): " + "; ".join(
        f"{f.estado} siembra mes {f.mes_siembra}, cosecha mes {f.mes_cosecha}" for f in v.itertuples()))
    return v


# ---------------------------------------------------------------- 2. lluvia del ciclo
def lluvia_ciclo(ventanas):
    cond = gpd.read_file("zip://" + str(EEUU / "condados" / "cb_2023_us_county_500k.zip"))
    cond = cond[cond["STATEFP"].isin(ESTADOS)].copy()
    archivos = sorted((EEUU / "chirps").glob("chirps_mensual_eeuu_*.nc"))
    print(f"Leyendo {len(archivos)} archivos CHIRPS para {len(cond)} condados...")
    mensual = comun.lluvia_mensual(cond, archivos, columna="GEOID", nombre_codigo="fips")
    mensual.to_csv(PROCESADOS / "chirps_mensual_condados_eeuu.csv", index=False)

    v = ventanas.assign(cod_estado=ventanas["estado"].map({e: c for c, e in ESTADOS.items()}))
    m = mensual.assign(cod_estado=mensual["fips"].str[:2]).merge(v, on="cod_estado")
    # Meses del ciclo: desde el mes de siembra hasta el mes anterior a la cosecha (mismo año)
    m = m[(m["mes"] >= m["mes_siembra"]) & (m["mes"] < m["mes_cosecha"])]
    lc = (m.groupby(["fips", "anio", "mes_siembra", "mes_cosecha", "meses_ciclo"])
            .agg(lluvia_ciclo_mm=("lluvia_mm", "sum"), n_meses=("mes", "size")).reset_index())
    lc = lc[(lc["n_meses"] == lc["meses_ciclo"]) & lc["anio"].between(ANIO_INI, CLIMA_FIN)].drop(columns="n_meses")
    lc["lluvia_ciclo_mm"] = lc["lluvia_ciclo_mm"].round(1)

    # Déficit y exceso frente al promedio histórico del mismo condado
    lc["lluvia_media_hist_mm"] = lc.groupby("fips")["lluvia_ciclo_mm"].transform("mean").round(1)
    anomalia = lc["lluvia_ciclo_mm"] - lc["lluvia_media_hist_mm"]
    lc["deficit_mm"] = (-anomalia).clip(lower=0).round(1)
    lc["exceso_mm"] = anomalia.clip(lower=0).round(1)
    lc["anomalia_pct"] = (100 * anomalia / lc["lluvia_media_hist_mm"]).round(1)
    print(f"Lluvia del ciclo para {lc['fips'].nunique()} condados, {ANIO_INI}-{CLIMA_FIN}")
    return lc


# ---------------------------------------------------------------- 3. rendimiento NASS
def leer_nass(nombre):
    partes = [pd.read_csv(f, dtype=str) for f in sorted((EEUU / "nass").glob(f"*_{nombre}.csv"))]
    d = pd.concat(partes, ignore_index=True)
    d = d[d["county_code"] != "998"]   # 'Other (combined) counties' no es un condado
    d["fips"] = d["state_fips_code"].str.zfill(2) + d["county_code"].str.zfill(3)
    d["valor"] = pd.to_numeric(d["Value"].str.replace(",", ""), errors="coerce")  # '(D)' = oculto
    return d.set_index(["fips", d["year"].astype(int).rename("anio")])["valor"].rename(nombre)


def rendimiento_nass():
    d = pd.concat([leer_nass("produccion"), leer_nass("area_cosechada")], axis=1).reset_index()
    nombres = pd.concat([pd.read_csv(f, dtype=str) for f in (EEUU / "nass").glob("*_produccion.csv")])
    nombres["fips"] = nombres["state_fips_code"].str.zfill(2) + nombres["county_code"].str.zfill(3)
    nombres = nombres.drop_duplicates("fips").set_index("fips")[["state_alpha", "county_name"]]
    d = d.merge(nombres, left_on="fips", right_index=True, how="left")
    d["con_dato"] = (d["produccion"] > 0) & (d["area_cosechada"] > 0)
    # Producción / área cosechada, pasado a t/ha
    d["rendimiento_t_ha"] = (d["produccion"] / d["area_cosechada"] * BU_ACRE_A_T_HA).where(d["con_dato"])
    d["area_cosechada_ha"] = d["area_cosechada"] * 0.404686
    print(f"NASS: {d['con_dato'].sum():,} condado-años con dato, {d['fips'].nunique()} condados, "
          f"{d['anio'].min()}-{d['anio'].max()}")
    return d


def main():
    v = ventanas_ciclo()
    v.to_csv(PROCESADOS / "eeuu_ventanas_ciclo.csv", index=False)
    lc = lluvia_ciclo(v)
    lc.to_csv(PROCESADOS / "eeuu_lluvia_ciclo.csv", index=False)

    d = rendimiento_nass().sort_values(["fips", "anio"])
    d = d[d["anio"] >= ANIO_INI]

    # 4. Filtro de calidad
    previo = d.groupby("fips")[["rendimiento_t_ha", "anio"]].shift()
    d["repetido"] = ((d["rendimiento_t_ha"].round(3) == previo["rendimiento_t_ha"].round(3)) &
                     (d["anio"] == previo["anio"] + 1))
    con = d[d["con_dato"]]
    cal = con.groupby("fips").agg(estado=("state_alpha", "first"), condado=("county_name", "first"),
                                  area_mediana_ha=("area_cosechada_ha", "median"))
    cal["salto_area_veces"] = con.groupby("fips")["area_cosechada_ha"].apply(comun.salto_de_nivel).round(1)
    cal["excluido_salto_area"] = cal["salto_area_veces"] >= comun.SALTO_AREA_MAX
    cal.to_csv(PROCESADOS / "eeuu_calidad_condados.csv")
    d = d.merge(cal[["excluido_salto_area"]], left_on="fips", right_index=True, how="left")
    d["excluido_salto_area"] = d["excluido_salto_area"].fillna(True).astype(bool)
    d = d.merge(lc, on=["fips", "anio"], how="left")
    d["valido"] = d["con_dato"] & ~d["repetido"] & ~d["excluido_salto_area"] & d["lluvia_ciclo_mm"].notna()

    # 5. Tendencia lineal y pérdida
    t = comun.tendencia_ciclos(d[d["valido"]], ["fips"], comun.MIN_ANIOS_TENDENCIA)
    d = d.merge(t[["fips", "anio", "rend_esperado_t_ha", "rend_relativo", "perdida"]],
                on=["fips", "anio"], how="left")
    d["en_analisis"] = d["rend_esperado_t_ha"].notna()
    d["perdida"] = d["perdida"].fillna(False).astype(bool)
    d.to_csv(PROCESADOS / "eeuu_base_ciclos.csv", index=False)

    c = d[d["con_dato"]]
    a = d[d["en_analisis"]]
    print("\nFiltro de calidad (condado-años con dato):")
    print(f"   Con dato:                       {len(c):,}")
    print(f"   Repetidos vs. año anterior:  {c['repetido'].sum():,} ({c['repetido'].mean():.1%})")
    print(f"   Condado con salto de área:   {c['excluido_salto_area'].sum():,} "
          f"({cal['excluido_salto_area'].sum()} de {len(cal)} condados)")
    print(f"   Válidos:                      {d['valido'].sum():,}")
    print(f"   En análisis: {len(a):,} ciclos en {a['fips'].nunique()} condados")
    print(f"   Pérdidas (rend. <= 80 % del esperado): {a['perdida'].sum():,} ({a['perdida'].mean():.1%})")
    print("\nGuardado eeuu_base_ciclos.csv")


if __name__ == "__main__":
    main()
