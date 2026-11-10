"""
53_dolares_modelo_final.py
Predicciones del modelo final y su impacto en dólares (plan en docs/bitacora.md, 2026-11-08, décima parte).

1. Modelo final (logística con splines, clima mensual frente a lo normal, sin calibrar), año por año de 1991 a 2025,
   entrenado solo con Iowa, Illinois e Indiana y años anteriores, prediciendo los diez estados.
2. Dólares: cada disparador (modelo, índice de calor, regla de lluvia) paga en la misma cantidad de condado-años que la
   regla, con monto = valor esperado x tamaño medio de las pérdidas de los años anteriores. Se compara con pagar al azar.

Requiere 34, 38 (ciegas_impacto_detalle.csv) y 50 (final_eleccion.json).
Salidas: datos/procesados/modelo_final_predicciones.csv, modelo_final_dolares.csv y modelo_final_metricas.csv
Uso:  python scripts/53_dolares_modelo_final.py   (unos 5 minutos)
"""
import importlib
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
import comun  # noqa: E402
e47 = importlib.import_module("47_cinco_modelos")
e50 = importlib.import_module("50_comparacion_final")

PROCESADOS = RAIZ / "datos" / "procesados"


def predicciones(b, lluvia, nombre, cols):
    bo = b[b["grupo"].isin(e50.ORIGINALES)]
    partes = []
    for t in range(e50.DESDE, e50.HASTA + 1):
        tr, pr_o = e47.etiquetas(bo, t)
        _, pr_n = e47.etiquetas(b[~b["grupo"].isin(e50.ORIGINALES)], t)
        pr = pd.concat([pr_o, pr_n], ignore_index=True)
        if pr.empty or tr["y"].nunique() < 2:
            continue
        final, _, _ = e50.ajustar(nombre, cols, tr)
        r = pr[["unidad", "anio", "grupo", "y"]].copy()
        r["prob"] = final.predict_proba(pr[cols])[:, 1]
        r["ref_calor"] = (pr["tmax_jul"] + pr["tmax_ago"]).to_numpy()
        r["pago_regla"], r["ref_regla"] = e47.regla(lluvia, pr[["unidad", "anio"]], t - 1)
        # Tamaño medio de las pérdidas en los años anteriores (tres estados originales)
        rel = tr.merge(comun.tendencia(bo[bo["anio"] < t], None, e47.MIN_ANIOS), on=["unidad", "anio"])
        r["severidad_media_previa"] = (1 - rel.loc[rel["y"], "relativo"].clip(0, 1)).mean()
        partes.append(r)
        print(f"{t}: {len(r)} condados", flush=True)
    d = pd.concat(partes, ignore_index=True)
    d["estado"] = d["grupo"].map(e50.ESTADOS)
    d["nuevo"] = ~d["grupo"].isin(e50.ORIGINALES)
    return d


def dolares(g, frecuencia):
    filas = []
    perdida_real = g["perdida_usd"].sum()
    potencial = g["valor_esperado_usd"] * g["severidad_media_previa"]
    for nombre, col in [("Modelo final", "prob"), ("Índice de calor jul-ago", "ref_calor"), ("Regla de lluvia jun-ago", None)]:
        paga = g["pago_regla"].to_numpy() if col is None else comun.pagar_igual_que_regla(g[col].to_numpy(), frecuencia)
        pago = potencial * paga
        total = pago.sum()
        filas.append({"disparador": nombre, "pagos": int(paga.sum()), "pagos_usd": total,
                      "perdida_real_usd": perdida_real, "pct_perdida_cubierta": 100 * np.minimum(pago, g["perdida_usd"]).sum() / perdida_real,
                      "de_cada_100": 100 * pago[g["y"]].sum() / total if total else np.nan})
    filas.append({"disparador": "Pagar al azar", "pagos": np.nan, "pagos_usd": np.nan, "perdida_real_usd": perdida_real,
                  "pct_perdida_cubierta": np.nan, "de_cada_100": 100 * potencial[g["y"]].sum() / potencial.sum()})
    return filas


def main():
    eleccion = json.loads((PROCESADOS / "final_eleccion.json").read_text(encoding="utf-8"))
    nombre, conjunto = eleccion["elegido"].rsplit("_", 1)
    b, lluvia = e50.cargar()
    d = predicciones(b, lluvia, nombre, e50.CONJUNTOS[conjunto])
    det = pd.read_csv(PROCESADOS / "ciegas_impacto_detalle.csv", dtype={"unidad": str})[["unidad", "anio", "valor_esperado_usd", "perdida_usd"]]
    d = d.merge(det, on=["unidad", "anio"], how="inner")
    d.to_csv(PROCESADOS / "modelo_final_predicciones.csv", index=False)

    filas, metricas = [], []
    grupos = {"diez estados": d, "siete estados nuevos (a ciegas)": d[d["nuevo"]], "tres estados originales": d[~d["nuevo"]]}
    for gnombre, g in grupos.items():
        for periodo, gg in [("1991-2025", g), ("1991-2025 sin 2012", g[g["anio"] != 2012])]:
            # Corrección del 2026-11-09 (bitácora, tercera parte): la frecuencia es la de la regla EN ESTE subconjunto,
            # para que los tres disparadores paguen en el mismo número de condado-años (antes se usaba la de los diez estados)
            for f in dolares(gg, gg["pago_regla"].mean()):
                filas.append({"grupo": gnombre, "periodo": periodo, **f})
        for col, etiqueta in [("prob", "Modelo final"), ("ref_calor", "Índice de calor jul-ago"), ("ref_regla", "Regla de lluvia jun-ago")]:
            dentro, n = e47.auc_dentro(g, col)
            metricas.append({"grupo": gnombre, "puntaje": etiqueta, "auc": roc_auc_score(g["y"], g[col]),
                             "auc_sin_2012": roc_auc_score(g.loc[g["anio"] != 2012, "y"], g.loc[g["anio"] != 2012, col]),
                             "auc_dentro_anio": dentro, "anios_dentro": n,
                             "brier": brier_score_loss(g["y"], g[col]) if col == "prob" else np.nan,
                             "brier_tasa": brier_score_loss(g["y"], np.full(len(g), g["y"].mean()))})
    res = pd.DataFrame(filas)
    res.to_csv(PROCESADOS / "modelo_final_dolares.csv", index=False)
    met = pd.DataFrame(metricas)
    met.to_csv(PROCESADOS / "modelo_final_metricas.csv", index=False)
    pd.set_option("display.width", 220)
    ver = res.assign(pagos_mill=res["pagos_usd"] / 1e6, perdida_mill=res["perdida_real_usd"] / 1e6)
    print(ver[["grupo", "periodo", "disparador", "pagos", "pagos_mill", "perdida_mill", "pct_perdida_cubierta", "de_cada_100"]].round(1).to_string(index=False))
    print(met.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
