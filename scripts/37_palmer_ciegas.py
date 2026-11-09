"""
37_palmer_ciegas.py
Fase 3B de la prueba a ciegas (plan congelado en docs/plan_prueba_ciegas.md): contrato simple con el índice de Palmer.

Contrato Palmer: el Palmer promedio de julio y agosto del condado queda por debajo del percentil 15 de los valores de los años anteriores
a t (mínimo 10 años). El pago es proporcional: 0 en el percentil 15 y 100 % de la suma asegurada en el percentil 2, en línea recta, y
100 % por debajo del percentil 2. La misma fórmula se aplica a la lluvia de junio a agosto (regla de lluvia).
Comparación con la misma frecuencia de pago (la del contrato Palmer en el conjunto evaluado): Palmer, regla de lluvia y modelo
(prueba principal de 35). Se mide AUC, Heidke, % de la pérdida en dólares cubierta y de cada $100 cuántos llegan a quien perdió.
Interpretación fijada: si el AUC del Palmer queda a 0,03 o menos del AUC del modelo, se puede proponer como contrato simple.

Requiere 34 y 35. Salidas en datos/procesados/: ciegas_palmer_predicciones.csv, ciegas_palmer_resultados.csv, ciegas_palmer_dolares.csv
Uso:  python scripts/37_palmer_ciegas.py
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

import mlflow
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
import comun  # noqa: E402
e28 = importlib.import_module("28_base_eeuu")
e29 = importlib.import_module("29_modelos_eeuu")
e31 = importlib.import_module("31_impacto_eeuu")

PROCESADOS = RAIZ / "datos" / "procesados"
ORIGINALES = {"17", "18", "19"}
P_DISPARO, P_TOPE = 0.15, 0.02
MIN_ANIOS = 10
UMBRAL_AUC = 0.03
Y = "perdida_previa"
N_REMUESTREO, SEMILLA = 1000, 2026


def palmer_julio_agosto():
    """Promedio del Palmer de julio y agosto por condado y año, para todos los años de NOAA (1981-2025) de los diez estados."""
    e28.ESTADOS_NOAA = {"11": "17", "12": "18", "13": "19", "25": "31", "21": "27", "33": "39", "23": "29", "14": "20", "39": "46", "47": "55"}
    p = e28.leer_noaa("pdsicy")
    p = p[p["mes"].isin([7, 8]) & (p["anio"] <= 2025)]
    v = p.groupby(["unidad", "anio"]).agg(x=("valor", "mean"), n=("valor", "count")).reset_index()
    return v[v["n"] == 2].rename(columns={"x": "palmer_jul_ago"})[["unidad", "anio", "palmer_jul_ago"]]


def contrato(serie, columna, nombre):
    """Para cada condado-año t con predicción: umbrales del condado con años anteriores a t, pago proporcional y puntaje."""
    s = serie.sort_values(["unidad", "anio"])
    filas = []
    for unidad, d in s.groupby("unidad"):
        x, a = d[columna].to_numpy(), d["anio"].to_numpy()
        for i in range(len(d)):
            previos = x[:i][~np.isnan(x[:i])]
            if len(previos) < MIN_ANIOS or np.isnan(x[i]):
                continue
            p15, p2 = np.quantile(previos, [P_DISPARO, P_TOPE])
            fraccion = 1.0 if x[i] <= p2 else (0.0 if x[i] >= p15 else (p15 - x[i]) / (p15 - p2))
            filas.append((unidad, a[i], fraccion, -(x[i] - previos.mean()) / (previos.std(ddof=1) or 1.0)))
    return pd.DataFrame(filas, columns=["unidad", "anio", f"fraccion_{nombre}", f"puntaje_{nombre}"])


def tarea(args):
    nombre_conjunto, indice, d, pun, pag, prob, cal, semilla = args
    m = e29.medir(d, Y, pun, pag, prob, cal, np.random.default_rng(semilla))
    return {"conjunto": nombre_conjunto, "indice": indice, **m}


def dolares(d, nombre):
    """% de la pérdida en dólares cubierta y de cada $100 pagados que llegan a quien perdió."""
    filas = []
    pagos = {"Palmer": d["valor_esperado_usd"] * d["fraccion_palmer"], "Regla de lluvia": d["valor_esperado_usd"] * d["fraccion_lluvia"],
             "Modelo": d["valor_esperado_usd"] * d["severidad_prevista"] * d["pago_modelo"]}
    perdida = d["perdida_usd"]
    y = d[Y].astype(bool)
    for indice, pago in pagos.items():
        total = pago.sum()
        filas.append({"conjunto": nombre, "indice": indice, "condado_anios": len(d), "frecuencia_pago_pct": 100 * (pago > 0).mean(),
                      "pagos_usd": total, "perdida_real_usd": perdida.sum(),
                      "pct_perdida_cubierta": 100 * np.minimum(pago, perdida).sum() / perdida.sum() if perdida.sum() else np.nan,
                      "de_cada_100": 100 * pago[y].sum() / total if total else np.nan})
    return filas


def dif_auc(d, rng):
    """AUC del Palmer menos AUC del modelo, con intervalo de 95 % remuestreando años completos (pareado)."""
    anios = sorted(d["anio"].unique())
    por = {a: g for a, g in d.groupby("anio")}
    obs = roc_auc_score(d[Y], d["puntaje_palmer"]) - roc_auc_score(d[Y], d["prob"])
    dif = []
    for _ in range(N_REMUESTREO):
        m = pd.concat([por[a] for a in rng.choice(anios, len(anios))], ignore_index=True)
        if 0 < m[Y].sum() < len(m):
            dif.append(roc_auc_score(m[Y], m["puntaje_palmer"]) - roc_auc_score(m[Y], m["prob"]))
    return obs, *np.percentile(dif, [2.5, 97.5])


def main():
    b = pd.read_csv(PROCESADOS / "eeuu_ciegas_base.csv", dtype={"unidad": str, "grupo": str})
    pred = pd.read_csv(PROCESADOS / "ciegas_predicciones_principal.csv", dtype={"unidad": str, "grupo": str})
    lluvia = e29_lluvia = importlib.import_module("35_prueba_ciegas").lluvia_todos()
    pal = contrato(palmer_julio_agosto(), "palmer_jul_ago", "palmer")
    llu = contrato(lluvia.rename(columns={"mm": "lluvia_jja"}), "lluvia_jja", "lluvia")
    d = pred.merge(pal, on=["unidad", "anio"]).merge(llu, on=["unidad", "anio"])
    # Dólares, con el mismo cálculo de 31
    defl, precio = e31.deflactor(), e31.precios()
    d = e31.preparar(d.merge(b[["unidad", "anio", "rendimiento_bu_acre", "area_cosechada_acres"]], on=["unidad", "anio"]),
                     "esperado_previo_t_ha", Y, precio, defl)
    d["nuevo"] = ~d["grupo"].isin(ORIGINALES)
    d["pago_palmer"] = d["fraccion_palmer"] > 0
    d["pago_lluvia_p15"] = d["fraccion_lluvia"] > 0

    conjuntos = {"nuevos": d[d["nuevo"]], "nuevos, sin 2012": d[d["nuevo"] & (d["anio"] != 2012)],
                 "originales": d[~d["nuevo"]], "originales, sin 2012": d[~d["nuevo"] & (d["anio"] != 2012)], "diez estados": d}
    salida, tareas, dol, difs = [], [], [], []
    rng = np.random.default_rng(SEMILLA)
    pagos_igualados = []
    for i, (nombre, c) in enumerate(conjuntos.items()):
        base = d[d["nuevo"]] if nombre.startswith("nuevos") else (d[~d["nuevo"]] if nombre.startswith("originales") else d)
        f = base["pago_palmer"].mean()                     # frecuencia del contrato Palmer en el conjunto completo
        c = c.copy()
        # Regla y modelo se igualan a la frecuencia del Palmer en el conjunto completo; los subconjuntos usan ese mismo corte
        igual = lambda col: pd.Series(comun.pagar_igual_que_regla(base[col].to_numpy(), f), index=base.index)
        c["pago_regla_igual"] = igual("puntaje_regla").reindex(c.index).to_numpy()
        c["pago_modelo"] = igual("prob").reindex(c.index).to_numpy()
        c["frecuencia_palmer_pct"] = 100 * f
        pagos_igualados.append(c.assign(conjunto=nombre))
        for j, (indice, pun, pag, prob, cal) in enumerate([("Palmer", "puntaje_palmer", "pago_palmer", None, None),
                                                          ("Regla de lluvia", "puntaje_regla", "pago_regla_igual", None, None),
                                                          ("Modelo", "prob", "pago_modelo", "prob", "prob_calibrada")]):
            tareas.append((nombre, indice, c, pun, pag, prob, cal, SEMILLA + 10 * i + j))
        dol += dolares(c, nombre)
        o, lo, hi = dif_auc(c, rng)
        difs.append({"conjunto": nombre, "auc_palmer_menos_modelo": o, "ic_inf": lo, "ic_sup": hi,
                     "palmer_a_0_03_o_menos": bool(o >= -UMBRAL_AUC)})
    with ProcessPoolExecutor(max_workers=6) as ex:
        res = pd.DataFrame(list(ex.map(tarea, tareas)))
    dol, difs = pd.DataFrame(dol), pd.DataFrame(difs)
    res.to_csv(PROCESADOS / "ciegas_palmer_resultados.csv", index=False)
    dol.to_csv(PROCESADOS / "ciegas_palmer_dolares.csv", index=False)
    difs.to_csv(PROCESADOS / "ciegas_palmer_diferencias.csv", index=False)
    pagos_igualados[4][["unidad", "anio", "conjunto", "fraccion_palmer", "puntaje_palmer", "fraccion_lluvia", "puntaje_lluvia",
                        "pago_regla_igual", "pago_modelo"]].to_csv(PROCESADOS / "ciegas_palmer_predicciones.csv", index=False)   # diez estados

    mlflow.set_tracking_uri(e29.URI_MLFLOW)
    mlflow.set_experiment(e29.EXPERIMENTO)
    for r in res.itertuples():
        with mlflow.start_run(run_name=f"contrato_palmer|{r.conjunto}|{r.indice}"):
            mlflow.set_tags({"fase": "contrato_palmer", "conjunto": r.conjunto, "indice": r.indice})
            mlflow.log_metrics({k: float(v) for k, v in r._asdict().items() if isinstance(v, (int, float, np.floating)) and pd.notna(v) and k != "Index"})

    pd.set_option("display.width", 250, "display.max_columns", 30)
    print(res[["conjunto", "indice", "filas", "perdidas", "pagos", "auc", "auc_ic_inf", "auc_ic_sup", "heidke", "pct_perdidas_captadas",
               "p_auc_anios"]].round(3).to_string(index=False))
    print(dol.round(2).to_string(index=False))
    print(difs.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
