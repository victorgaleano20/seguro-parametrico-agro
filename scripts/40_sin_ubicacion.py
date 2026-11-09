"""
40_sin_ubicacion.py
Fase 1 del cierre (plan congelado en docs/plan_cierre.md): ¿el modelo aprende clima o geografía?

Repite la prueba a ciegas principal de 35_prueba_ciegas.py (entrena solo con Iowa, Illinois e Indiana, año por año, y predice los siete
estados nuevos) con el mismo LightGBM, la misma rejilla, la misma calibración y el mismo corte de pago, pero SIN latitud, SIN longitud
y SIN la variable de estado. Se compara con el modelo original y con la regla de lluvia.

Interpretación fijada: si el AUC sin ubicación queda a 0,02 o menos del original (siete estados nuevos, todos los años), el modelo
aprende sobre todo clima; si baja más, parte de lo que aprende es geografía.

Requiere 34 y 35. Salidas en datos/procesados/: cierre_ubicacion_validacion.csv, cierre_ubicacion_predicciones.csv,
  cierre_ubicacion_resultados.csv, cierre_ubicacion_comparacion.csv, cierre_ubicacion_criterio.json
Uso:  python scripts/40_sin_ubicacion.py
"""
import importlib
import json
import os
import sys
import warnings
from pathlib import Path

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import roc_auc_score

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
import comun  # noqa: E402
e29 = importlib.import_module("29_modelos_eeuu")
e35 = importlib.import_module("35_prueba_ciegas")

PROCESADOS = RAIZ / "datos" / "procesados"
ORIGINALES = e35.ORIGINALES
NOMBRE = "lightgbm"
Y = "perdida_previa"
SEMILLA = e29.SEMILLA
UMBRAL_CLIMA = 0.02
# Solo clima: las mismas variables de "todas" sin latitud, longitud ni estado
NUMERICAS = [v for g in e29.CONJUNTOS["todas"] for v in e29.GRUPOS[g]]


def crear(parametros):
    return comun.crear(NOMBRE, parametros, NUMERICAS, [])          # sin columnas categóricas


def escoger(viejos, recientes):
    """Igual que 29.escoger, con las variables de clima solamente."""
    mejor, mejor_auc, guardado = comun.REJILLAS[NOMBRE][0], -1.0, None
    if recientes[Y].nunique() < 2:
        m = crear(mejor).fit(viejos[NUMERICAS], viejos[Y])
        return mejor, m.predict_proba(recientes[NUMERICAS])[:, 1]
    for parametros in comun.REJILLAS[NOMBRE]:
        m = crear(parametros).fit(viejos[NUMERICAS], viejos[Y])
        prob = m.predict_proba(recientes[NUMERICAS])[:, 1]
        auc = roc_auc_score(recientes[Y], prob)
        if auc > mejor_auc:
            mejor, mejor_auc, guardado = parametros, auc, prob
    return mejor, guardado


def adelante(b, lluvia):
    """Igual que 35.adelante (modo principal), sin ubicación. Las columnas de la regla y de la tasa se toman de la corrida original."""
    bo, bn = b[b["grupo"].isin(ORIGINALES)], b[~b["grupo"].isin(ORIGINALES)]
    partes = []
    for t in range(e29.DESDE, int(b["anio"].max()) + 1):
        tr, _ = e29.etiquetas_previas(bo, t)
        _, pr_o = e29.etiquetas_previas(bo, t)
        _, pr_n = e29.etiquetas_previas(bn, t)
        pr = pd.concat([pr_o, pr_n], ignore_index=True)
        anios = sorted(tr["anio"].unique())
        corte = anios[-e29.ANIOS_AJUSTE]
        viejos, recientes = tr[tr["anio"] < corte], tr[tr["anio"] >= corte]
        if pr.empty or viejos[Y].nunique() < 2:
            continue
        parametros, prob_rec = escoger(viejos, recientes)
        final = crear(parametros).fit(tr[NUMERICAS], tr[Y])
        r = pr[["unidad", "anio"]].copy()
        r["prob_sin"] = final.predict_proba(pr[NUMERICAS])[:, 1]
        if recientes[Y].nunique() == 2:
            iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(prob_rec, recientes[Y])
            r["prob_calibrada_sin"] = iso.predict(r["prob_sin"])
        else:
            r["prob_calibrada_sin"] = r["prob_sin"]
        frecuencia = e29.regla(lluvia, recientes[["unidad", "anio"]], t - 1)["pago_regla"].mean()
        umbral = np.quantile(prob_rec, 1 - frecuencia) if frecuencia > 0 else np.inf
        r["pago_umbral_sin"] = r["prob_sin"] >= umbral
        partes.append(r)
        print(f"  sin ubicación {t}: {len(r)} condados, parámetros {parametros}", flush=True)
    return pd.concat(partes, ignore_index=True)


def dif_auc_pareada(d, col_a, col_b, rng, n=1000):
    """AUC de a menos AUC de b, con intervalo de 95 % remuestreando años completos."""
    por = {a: g for a, g in d.groupby("anio")}
    anios = sorted(por)
    obs = roc_auc_score(d[Y], d[col_a]) - roc_auc_score(d[Y], d[col_b])
    dif = []
    for _ in range(n):
        m = pd.concat([por[a] for a in rng.choice(anios, len(anios))], ignore_index=True)
        if 0 < m[Y].sum() < len(m):
            dif.append(roc_auc_score(m[Y], m[col_a]) - roc_auc_score(m[Y], m[col_b]))
    return obs, *np.percentile(dif, [2.5, 97.5])


def main():
    b, lluvia, riego = e35.cargar_base(), e35.lluvia_todos(), e35.riego_medio()
    orig = pd.read_csv(PROCESADOS / "ciegas_validacion_principal.csv", dtype={"unidad": str, "grupo": str})
    ruta = PROCESADOS / "cierre_ubicacion_validacion.csv"
    if ruta.exists():
        print(f"Se usa la validación ya calculada: {ruta.name}")
        v = pd.read_csv(ruta, dtype={"unidad": str, "grupo": str})
    else:
        sin = adelante(b, lluvia)
        v = orig.merge(sin, on=["unidad", "anio"], how="inner")
        assert len(v) == len(orig), f"las filas no coinciden: {len(v)} frente a {len(orig)}"
        v.to_csv(ruta, index=False)
    print(f"Filas: {len(v):,} (original {len(orig):,})")

    # El modelo sin ubicación entra en lugar del original, con el mismo formato que usa 35
    d = v.copy()
    for c in ["prob", "prob_calibrada", "pago_umbral"]:
        d[c + "_original"] = d[c]
    d["prob"], d["prob_calibrada"], d["pago_umbral"] = d["prob_sin"], d["prob_calibrada_sin"], d["pago_umbral_sin"]
    res, dd = e35.evaluar(d, riego, "sin_ubicacion")
    res.to_csv(PROCESADOS / "cierre_ubicacion_resultados.csv", index=False)
    dd.to_csv(PROCESADOS / "cierre_ubicacion_predicciones.csv", index=False)

    # Comparación con el original y con la regla, en los mismos subconjuntos
    orig_res = pd.read_csv(PROCESADOS / "ciegas_resultados_principal.csv")
    cols = ["subconjunto", "auc", "auc_ic_inf", "auc_ic_sup", "heidke", "heidke_ic_inf", "heidke_ic_sup", "pct_perdidas_captadas",
            "p_auc_anios", "p_heidke_anios", "brier_calibrado", "brier_tasa", "filas", "perdidas"]
    piezas = [orig_res[orig_res["indice"] == "modelo"][cols].assign(modelo="Modelo original (con ubicación)"),
              res[res["indice"] == "modelo"][cols].assign(modelo="Modelo sin ubicación"),
              res[res["indice"] == "regla"][cols].assign(modelo="Regla de lluvia")]
    comp = pd.concat(piezas, ignore_index=True)
    comp.to_csv(PROCESADOS / "cierre_ubicacion_comparacion.csv", index=False)

    # Diferencia de AUC original menos sin ubicación (pareada) en los siete estados nuevos
    rng = np.random.default_rng(SEMILLA)
    n = dd[dd["nuevo"]]
    sub = {"todos": n, "sin_2012": n[n["anio"] != 2012], "originales (IA, IL, IN)": dd[~dd["nuevo"]]}
    difs = []
    for nombre, s in sub.items():
        o, lo, hi = dif_auc_pareada(s, "prob_original", "prob", rng)
        difs.append({"subconjunto": nombre, "auc_original_menos_sin_ubicacion": o, "ic_inf": lo, "ic_sup": hi})
    difs = pd.DataFrame(difs)
    difs.to_csv(PROCESADOS / "cierre_ubicacion_diferencias.csv", index=False)

    t = comp[comp["subconjunto"] == "todos"].set_index("modelo")
    dif = t.loc["Modelo original (con ubicación)", "auc"] - t.loc["Modelo sin ubicación", "auc"]
    crit = {"auc_original": float(t.loc["Modelo original (con ubicación)", "auc"]), "auc_sin_ubicacion": float(t.loc["Modelo sin ubicación", "auc"]),
            "auc_regla": float(t.loc["Regla de lluvia", "auc"]), "dif_auc_original_menos_sin": float(dif), "umbral": UMBRAL_CLIMA,
            "aprende_sobre_todo_clima": bool(dif <= UMBRAL_CLIMA + 1e-12),
            "variables_usadas": NUMERICAS}
    (PROCESADOS / "cierre_ubicacion_criterio.json").write_text(json.dumps(crit, indent=1, ensure_ascii=False), encoding="utf-8")

    pd.set_option("display.width", 250, "display.max_columns", 30)
    sel = comp[comp["subconjunto"].isin(["todos", "sin_2012", "1995_2025", "sin_riego_alto"]) | comp["subconjunto"].str.startswith("estado") |
               comp["subconjunto"].str.startswith("originales")]
    print(sel.round(3).to_string(index=False))
    print(difs.round(3).to_string(index=False))
    print(json.dumps(crit, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
