"""
44_semaforo_causa.py
Fase 4B del cierre (plan congelado en docs/plan_cierre.md): semáforo por causa de los siniestros, alternativa al de 30 y 36.

Para cada condado y cada año t, con las indemnizaciones de maíz de la RMA de los años 1989 a t - 1 (dólares de 2025), se calcula qué parte
fue por sequía (código 11). Colores, por terciles de esa parte entre los condados elegibles de los diez estados, cada año:
  VERDE: el tercio con más sequía. ROJO: el tercio con menos sequía, o el condado no pasa los filtros de calidad de 36, o tiene menos de
  10 años anteriores con indemnización de maíz. AMARILLO: el resto.
Evaluación hacia adelante en todos los años t con al menos 10 años anteriores de indemnizaciones (1999-2025) y, como comparación pareja con
el semáforo de 36, en 2006-2025. Criterio (el de 36, con el modelo): los verdes superan a los rojos en Heidke, en % de pérdidas captadas y
en "de cada $100 que llegan a quien perdió", con el intervalo de 95 % de la diferencia (remuestreo de años) sin incluir el cero.

Requiere 36 y 43. Salidas en datos/procesados/: cierre_semaforo_causa_colores.csv, cierre_semaforo_causa_resultados.csv,
  cierre_semaforo_causa_diferencias.csv, cierre_semaforo_causa_criterio.json, cierre_semaforo_lado_a_lado.csv
Uso:  python scripts/44_semaforo_causa.py
"""
import importlib
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
import comun  # noqa: E402
e31 = importlib.import_module("31_impacto_eeuu")
e36 = importlib.import_module("36_semaforo_ciegas")

PROCESADOS = RAIZ / "datos" / "procesados"
MIN_ANIOS_SINIESTROS = 10
PRIMER_ANIO_RMA = 1989
SEMILLA = 2026


def colores_por_causa(causas, q, universo, hasta):
    """Colores de todos los condados del universo con indemnizaciones de 1989 a 'hasta' (inclusive)."""
    c = causas[causas["anio"] <= hasta]
    g = c.groupby("unidad")
    t = pd.DataFrame(index=pd.Index(universo, name="unidad"))
    t["anios_con_siniestros"] = c[c["total_usd"] > 0].groupby("unidad").size().reindex(t.index).fillna(0).astype(int)
    total = g["total_usd"].sum().reindex(t.index)
    t["parte_sequia"] = (g["sequia"].sum().reindex(t.index) / total.replace(0, np.nan))
    t["dato_bueno"] = e36.calidad(q[q["unidad"].isin(universo)], hasta).reindex(t.index).fillna(False).astype(bool)
    t["elegible"] = t["dato_bueno"] & (t["anios_con_siniestros"] >= MIN_ANIOS_SINIESTROS) & t["parte_sequia"].notna()
    cortes = t.loc[t["elegible"], "parte_sequia"].quantile([1 / 3, 2 / 3]).to_numpy()
    verde = t["elegible"] & (t["parte_sequia"] > cortes[1])
    rojo = ~t["elegible"] | (t["parte_sequia"] <= cortes[0])
    t["color_causa"] = np.select([rojo, verde], ["rojo", "verde"], "amarillo")
    t["corte_bajo"], t["corte_alto"] = cortes
    return t.reset_index()


def main():
    rng = np.random.default_rng(SEMILLA)
    defl, precio = e31.deflactor(), e31.precios()
    b = pd.read_csv(PROCESADOS / "eeuu_ciegas_base.csv", dtype={"unidad": str, "grupo": str})
    q = pd.read_csv(PROCESADOS / "eeuu_ciegas_calidad_anual.csv", dtype={"unidad": str})
    causas = pd.read_csv(PROCESADOS / "cierre_causas_condado_anio.csv", dtype={"unidad": str})
    pred = pd.read_csv(PROCESADOS / "ciegas_predicciones_principal.csv", dtype={"unidad": str, "grupo": str})
    cb = b[["unidad", "anio", "rendimiento_bu_acre", "area_cosechada_acres"]]
    pred = e31.preparar(pred.merge(cb, on=["unidad", "anio"]), "esperado_previo_t_ha", "perdida_previa", precio, defl)
    universo = sorted(b["unidad"].unique())
    primer = PRIMER_ANIO_RMA + MIN_ANIOS_SINIESTROS                       # 1999: primer año con 10 años anteriores de la RMA
    partes, tablas = [], []
    for t in range(primer, int(pred["anio"].max()) + 1):
        col = colores_por_causa(causas, q, universo, t - 1)
        tablas.append(col.assign(anio=t))
        partes.append(pred[pred["anio"] == t].merge(col[["unidad", "color_causa", "parte_sequia", "anios_con_siniestros"]], on="unidad", how="left"))
        print(f"  Año {t}: " + ", ".join(f"{c} {int((col['color_causa'] == c).sum())}" for c in e36.COLORES) +
              f" (elegibles {int(col['elegible'].sum())})", flush=True)
    colores = pd.concat(tablas, ignore_index=True)
    colores.to_csv(PROCESADOS / "cierre_semaforo_causa_colores.csv", index=False)
    d_todo = pd.concat(partes, ignore_index=True).dropna(subset=["color_causa"])
    d_todo = e36.preparar_pagos(d_todo)

    por_color, difs = [], []
    pruebas = {"causa, 1999-2025 (principal)": d_todo, "causa, 2006-2025 (mismos años que el semáforo de 36)": d_todo[d_todo["anio"] >= 2006]}
    for nombre, d in pruebas.items():
        d = d.assign(pago_modelo=comun.pagar_igual_que_regla(d["prob"].to_numpy(), d["pago_regla"].mean()))
        pc, df = e36.probar(d, "color_causa", nombre, "semáforo por causa", rng)
        por_color += pc
        difs += df
        print(f"{nombre}: {len(d):,} condado-años, {int(d['perdida_previa'].sum())} pérdidas, {d['anio'].nunique()} años")
    pc, df = pd.DataFrame(por_color), pd.DataFrame(difs)
    pc.to_csv(PROCESADOS / "cierre_semaforo_causa_resultados.csv", index=False)
    df.to_csv(PROCESADOS / "cierre_semaforo_causa_diferencias.csv", index=False)

    crit = {}
    for prueba, g in df[df["indice"] == "modelo"].groupby("prueba"):
        g = g.set_index("metrica")
        ok = {k: bool(g.loc[k, "diferencia"] > 0 and g.loc[k, "ic_inf"] > 0) for k in ("heidke", "pct_perdidas_captadas", "de_cada_100")}
        crit[prueba] = {**ok, "cumple": bool(all(ok.values()))}
    crit["algun_semaforo_cumple"] = False                       # se completa abajo con el de 36
    s36 = json.loads((PROCESADOS / "ciegas_semaforo_criterio.json").read_text(encoding="utf-8"))
    cumple36 = s36["prueba 1: hacia adelante, 10 estados | regla base"]["cumple"]
    crit["semaforo_36_cumple"] = bool(cumple36)
    crit["semaforo_causa_cumple"] = bool(crit["causa, 1999-2025 (principal)"]["cumple"])
    crit["algun_semaforo_cumple"] = bool(cumple36 or crit["semaforo_causa_cumple"])
    (PROCESADOS / "cierre_semaforo_causa_criterio.json").write_text(json.dumps(crit, indent=1, ensure_ascii=False), encoding="utf-8")

    # Lado a lado: el de 36 (prueba 1, regla base, 2006-2025) y el de causa (2006-2025 y 1999-2025), con el modelo
    d36 = pd.read_csv(PROCESADOS / "ciegas_semaforo_diferencias.csv")
    d36 = d36[(d36["prueba"] == "prueba 1: hacia adelante, 10 estados") & (d36["variante"] == "regla base") & (d36["indice"] == "modelo")]
    lado = pd.concat([d36.assign(semaforo="Semáforo de 36 (calidad y sensibilidad), 2006-2025"),
                      df[df["indice"] == "modelo"].assign(semaforo=df["prueba"].map(
                          {"causa, 1999-2025 (principal)": "Semáforo por causa, 1999-2025",
                           "causa, 2006-2025 (mismos años que el semáforo de 36)": "Semáforo por causa, 2006-2025"}))], ignore_index=True)
    lado = lado[["semaforo", "metrica", "verde", "rojo", "diferencia", "ic_inf", "ic_sup"]]
    lado["excluye_cero"] = (lado["ic_inf"] > 0) | (lado["ic_sup"] < 0)
    lado.to_csv(PROCESADOS / "cierre_semaforo_lado_a_lado.csv", index=False)

    pd.set_option("display.width", 250, "display.max_columns", 30)
    print(pc[pc["indice"] == "modelo"].round(3).to_string(index=False))
    print(df[df["indice"] == "modelo"].round(3).to_string(index=False))
    print(lado.round(3).to_string(index=False))
    print(json.dumps(crit, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
