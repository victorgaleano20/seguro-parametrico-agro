"""
35_prueba_ciegas.py
Fase 2 de la prueba a ciegas (plan congelado en docs/plan_prueba_ciegas.md).

El modelo de 29_modelos_eeuu.py (LightGBM, variables "todas" sin riego, mismos hiperparámetros, regla de selección,
calibración y corte de pago) se entrena año por año hacia adelante y se aplica a los siete estados nuevos:
  - Prueba principal: se entrena SOLO con Iowa, Illinois e Indiana, con años anteriores a t. Los estados nuevos nunca se usan
    para entrenar, escoger hiperparámetros ni calibrar.
  - Variante secundaria: tres estados + años anteriores a t de los estados nuevos.
Se compara con la regla de lluvia (percentil 15 de cada condado con sus años anteriores), con la tasa histórica de pérdida
de cada condado y con el azar, todos con la misma frecuencia de pago (la de la regla en los estados nuevos, 1991-2025).
Métricas: AUC, Heidke, % de pérdidas captadas, % de alertas sin pérdida, Brier, intervalos de 95 % remuestreando años y
valor p barajando años completos. Todo con y sin 2012, por estado, de 1995 a 2025 y sin condados con más de 25 % de riego.

Requiere 33 y 34. Salidas en datos/procesados/: ciegas_predicciones_principal.csv, ciegas_predicciones_secundaria.csv,
ciegas_resultados.csv, ciegas_criterio.json
Uso:  python scripts/35_prueba_ciegas.py
"""
import importlib
import json
import os
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")      # los procesos en paralelo no deben pedir un juego de hilos cada uno
os.environ.setdefault("MKL_NUM_THREADS", "1")
warnings.filterwarnings("ignore")

import lightgbm as lgb
import mlflow
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
import comun  # noqa: E402
e29 = importlib.import_module("29_modelos_eeuu")

PROCESADOS = RAIZ / "datos" / "procesados"
ORIGINALES = {"17", "18", "19"}
ESTADOS = {"17": "Illinois", "18": "Indiana", "19": "Iowa", "31": "Nebraska", "27": "Minnesota", "39": "Ohio", "29": "Missouri",
           "20": "Kansas", "46": "South Dakota", "55": "Wisconsin"}
NUEVOS = ["31", "27", "39", "29", "20", "46", "55"]
NOMBRE, CONJUNTO = "lightgbm", "todas"
RIEGO_ALTO = 0.25
UMBRAL_AUC, SEMILLA = 0.05, e29.SEMILLA
Y = "perdida_previa"


# ---------------------------------------------------------------- datos
def cargar_base():
    b = pd.read_csv(PROCESADOS / "eeuu_ciegas_base.csv", dtype={"unidad": str, "grupo": str})
    b["perdida"] = b["perdida"].astype(bool)
    return b


def lluvia_todos():
    """Lluvia de junio a agosto de los diez estados (misma lógica de 29.lluvia_verano)."""
    a = pd.read_csv(PROCESADOS / "chirps_mensual_condados_eeuu.csv", dtype={"fips": str})
    n = pd.read_csv(PROCESADOS / "chirps_mensual_condados_nuevos.csv", dtype={"fips": str})
    m = pd.concat([a, n], ignore_index=True)
    m = m[m["mes"].isin([6, 7, 8]) & (m["anio"] <= 2025)]
    v = m.groupby(["fips", "anio"]).agg(mm=("lluvia_mm", "sum"), n=("mes", "size")).reset_index()
    return v[v["n"] == 3].rename(columns={"fips": "unidad"})[["unidad", "anio", "mm"]]


def riego_medio():
    """Fracción de riego de cada condado: promedio de todos los censos 1997-2022 (filtro de evaluación, no una variable del modelo)."""
    r = pd.read_csv(PROCESADOS / "eeuu_riego_censos.csv", dtype={"unidad": str})
    return r.groupby("unidad")["fraccion"].mean().rename("fraccion_riego_censos")


# ---------------------------------------------------------------- modelo hacia adelante
def adelante(b, lluvia, modo):
    """Igual que 29.hacia_adelante. modo = 'principal' (entrena con IA, IL e IN) o 'secundaria' (con los nuevos también).
    Predice en cada año t a los 10 estados; los de IA, IL e IN coinciden con la corrida de 29 en el modo principal."""
    bo, bn = b[b["grupo"].isin(ORIGINALES)], b[~b["grupo"].isin(ORIGINALES)]
    cols = e29.columnas(CONJUNTO)
    partes = []
    for t in range(e29.DESDE, int(b["anio"].max()) + 1):
        tr_o, pr_o = e29.etiquetas_previas(bo, t)
        tr_n, pr_n = e29.etiquetas_previas(bn, t)
        tr = tr_o if modo == "principal" else pd.concat([tr_o, tr_n], ignore_index=True)
        pr = pd.concat([pr_o, pr_n], ignore_index=True)
        anios = sorted(tr["anio"].unique())
        corte = anios[-e29.ANIOS_AJUSTE]
        viejos, recientes = tr[tr["anio"] < corte], tr[tr["anio"] >= corte]
        if pr.empty or viejos[Y].nunique() < 2:
            continue
        parametros, _, prob_rec = e29.escoger(NOMBRE, CONJUNTO, viejos, recientes, Y)
        final = e29.crear(NOMBRE, parametros, CONJUNTO).fit(tr[cols], tr[Y])
        r = pr[["unidad", "anio", "perdida", Y, "faltante_previo", "esperado_previo_t_ha"]].copy()
        r["prob"] = final.predict_proba(pr[cols])[:, 1]
        if recientes[Y].nunique() == 2:
            iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(prob_rec, recientes[Y])
            r["prob_calibrada"] = iso.predict(r["prob"])
        else:
            r["prob_calibrada"] = r["prob"]
        frecuencia = e29.regla(lluvia, recientes[["unidad", "anio"]], t - 1)["pago_regla"].mean()
        r["umbral_prob"] = np.quantile(prob_rec, 1 - frecuencia) if frecuencia > 0 else np.inf
        r["pago_umbral"] = r["prob"] >= r["umbral_prob"]
        r = r.merge(e29.regla(lluvia, r[["unidad", "anio"]], t - 1), on=["unidad", "anio"], how="left")
        perd = tr[tr[Y]]
        sev = lgb.LGBMRegressor(**e29.PARAMS_SEVERIDAD).fit(perd[e29.numericas(CONJUNTO)], perd["faltante_previo"])
        r["severidad_prevista"] = np.clip(sev.predict(pr[e29.numericas(CONJUNTO)]), 0, 1)
        # Tasa histórica de pérdida de cada condado con sus años anteriores (de la base completa de años anteriores a t)
        previas = pd.concat([tr_o, tr_n], ignore_index=True)
        r["tasa_condado"] = r["unidad"].map(previas.groupby("unidad")[Y].mean()).fillna(0.0)
        r["modo"] = modo
        partes.append(r)
        print(f"  {modo} {t}: {len(r)} condados, parámetros {parametros}", flush=True)
    d = pd.concat(partes, ignore_index=True)
    d["pago_regla"] = d["pago_regla"].fillna(False).astype(bool)
    d["grupo"] = d["unidad"].str[:2]
    d["estado"] = d["grupo"].map(ESTADOS)
    d["nuevo"] = ~d["grupo"].isin(ORIGINALES)
    return d


def agregar_pagos(d, semilla=SEMILLA):
    """Puntajes y pagos de los comparadores con la misma frecuencia de pago que la regla, en el conjunto d."""
    rng = np.random.default_rng(semilla)
    f = d["pago_regla"].mean()
    d = d.copy()
    d["puntaje_tasa"] = d["tasa_condado"] + rng.random(len(d)) * 1e-9        # desempate al azar entre condados con la misma tasa
    d["puntaje_azar"] = rng.random(len(d))
    d["pago_modelo"] = comun.pagar_igual_que_regla(d["prob"].to_numpy(), f)
    d["pago_tasa"] = comun.pagar_igual_que_regla(d["puntaje_tasa"].to_numpy(), f)
    d["pago_azar"] = comun.pagar_igual_que_regla(d["puntaje_azar"].to_numpy(), f)
    return d


# ---------------------------------------------------------------- métricas (en paralelo)
INDICES = {"modelo": ("prob", "pago_modelo", "prob", "prob_calibrada"),
           "regla": ("puntaje_regla", "pago_regla", None, None),
           "tasa_historica": ("puntaje_tasa", "pago_tasa", None, None),
           "azar": ("puntaje_azar", "pago_azar", None, None)}


def tarea(args):
    modo, subconjunto, indice, d, semilla = args
    pun, pag, prob, cal = INDICES[indice]
    rng = np.random.default_rng(semilla)
    m = e29.medir(d, Y, pun, pag, prob, cal, rng)
    return {"modo": modo, "subconjunto": subconjunto, "indice": indice, **m}


def subconjuntos(d, riego):
    """Subconjuntos de los estados nuevos. El pago de cada índice se fijó con todo el conjunto (misma frecuencia que la regla)."""
    n = d[d["nuevo"]]
    s = {"todos": n, "sin_2012": n[n["anio"] != 2012], "1995_2025": n[n["anio"] >= 1995],
         "sin_riego_alto": n[~(n["unidad"].map(riego) > RIEGO_ALTO)]}
    for g in NUEVOS:
        e = ESTADOS[g]
        s[f"estado: {e}"] = n[n["grupo"] == g]
        s[f"estado: {e}, sin 2012"] = n[(n["grupo"] == g) & (n["anio"] != 2012)]
    s["originales (IA, IL, IN)"] = d[~d["nuevo"]]
    s["originales, sin 2012"] = d[~d["nuevo"] & (d["anio"] != 2012)]
    return s


def evaluar(d, riego, modo):
    d = agregar_pagos(d[d["nuevo"]]).pipe(lambda n: pd.concat([n, agregar_pagos(d[~d["nuevo"]])], ignore_index=True))
    tareas = []
    for i, (nombre, sub) in enumerate(subconjuntos(d, riego).items()):
        if sub["perdida_previa"].nunique() < 2:
            print(f"  {modo}, {nombre}: sin pérdidas o todas pérdidas, se omite")
            continue
        for j, indice in enumerate(INDICES):
            tareas.append((modo, nombre, indice, sub, SEMILLA + 10 * i + j))
    with ProcessPoolExecutor(max_workers=6) as ex:
        filas = list(ex.map(tarea, tareas))
    return pd.DataFrame(filas), d


def criterio(res):
    t = res[(res["modo"] == "principal") & (res["subconjunto"] == "todos")].set_index("indice")
    m, r = t.loc["modelo"], t.loc["regla"]
    c = {"auc_modelo": m["auc"], "auc_regla": r["auc"], "dif_auc": m["auc"] - r["auc"], "heidke_modelo": m["heidke"],
         "heidke_regla": r["heidke"], "p_auc_modelo": m["p_auc_anios"],
         "cumple_auc_mas_005": bool(m["auc"] - r["auc"] >= UMBRAL_AUC), "cumple_heidke_mayor": bool(m["heidke"] > r["heidke"]),
         "cumple_p_menor_005": bool(m["p_auc_anios"] < 0.05)}
    c["pasa_la_prueba"] = bool(c["cumple_auc_mas_005"] and c["cumple_heidke_mayor"] and c["cumple_p_menor_005"])
    return c


def registrar(res, crit):
    mlflow.set_tracking_uri(e29.URI_MLFLOW)
    mlflow.set_experiment(e29.EXPERIMENTO)
    for (modo, sub, indice), g in res.groupby(["modo", "subconjunto", "indice"]):
        if sub not in ("todos", "sin_2012", "sin_riego_alto", "1995_2025", "originales (IA, IL, IN)"):
            continue
        r = g.iloc[0]
        with mlflow.start_run(run_name=f"prueba_ciegas|{modo}|{sub}|{indice}"):
            mlflow.set_tags({"cultivo": "maiz", "pais": "eeuu", "fase": "prueba_ciegas", "modo": modo, "subconjunto": sub, "indice": indice})
            mlflow.log_metrics({k: float(v) for k, v in r.items() if isinstance(v, (int, float, np.floating)) and pd.notna(v)})
    with mlflow.start_run(run_name="prueba_ciegas|criterio"):
        mlflow.set_tags({"fase": "prueba_ciegas", "indice": "criterio"})
        mlflow.log_metrics({k: float(v) for k, v in crit.items()})


def main():
    b, lluvia, riego = cargar_base(), lluvia_todos(), riego_medio()
    print(f"Base: {len(b):,} condado-años, {b['unidad'].nunique()} condados, {b['grupo'].nunique()} estados", flush=True)
    resultados, cuadros = [], {}
    for modo in ["principal", "secundaria"]:
        print(f"Validación hacia adelante, modo {modo}", flush=True)
        crudo = PROCESADOS / f"ciegas_validacion_{modo}.csv"
        if crudo.exists():
            print(f"  Se usa la validación ya calculada: {crudo.name}")
            d = pd.read_csv(crudo, dtype={"unidad": str, "grupo": str})
        else:
            d = adelante(b, lluvia, modo)
            d.to_csv(crudo, index=False)
        res, d = evaluar(d, riego, modo)
        d.to_csv(PROCESADOS / f"ciegas_predicciones_{modo}.csv", index=False)
        resultados.append(res)
        res.to_csv(PROCESADOS / f"ciegas_resultados_{modo}.csv", index=False)
        cuadros[modo] = d
    res = pd.concat(resultados, ignore_index=True)
    res.to_csv(PROCESADOS / "ciegas_resultados.csv", index=False)
    crit = criterio(res)
    (PROCESADOS / "ciegas_criterio.json").write_text(json.dumps(crit, indent=1), encoding="utf-8")

    # Comprobación: en el modo principal, los tres estados originales deben coincidir con la corrida de 29
    orig = pd.read_csv(PROCESADOS / "eeuu_sequia_predicciones_adelante.csv", dtype={"unidad": str})[["unidad", "anio", "prob"]]
    j = cuadros["principal"].merge(orig, on=["unidad", "anio"], suffixes=("", "_29"))
    print(f"Comprobación con 29 (IA, IL, IN): {len(j):,} filas, diferencia máxima de probabilidad {np.abs(j['prob'] - j['prob_29']).max():.2e}")

    registrar(res, crit)
    pd.set_option("display.width", 250, "display.max_columns", 30)
    cols = ["modo", "subconjunto", "indice", "filas", "perdidas", "auc", "auc_ic_inf", "auc_ic_sup", "heidke", "pct_perdidas_captadas",
            "pct_alertas_sin_perdida", "brier", "brier_calibrado", "brier_tasa", "p_auc_anios", "p_heidke_anios"]
    print(res[res["subconjunto"].isin(["todos", "sin_2012", "sin_riego_alto", "1995_2025"])][cols].round(3).to_string(index=False))
    print(json.dumps(crit, indent=1))


if __name__ == "__main__":
    main()
