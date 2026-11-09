"""
41_calibracion_local.py
Fase 2 del cierre (plan congelado en docs/plan_cierre.md): ¿cuántos años locales hacen falta para entrar a un estado nuevo?

En cada uno de los siete estados nuevos, con las probabilidades del modelo original (prueba principal de 35, entrenado solo con
Iowa, Illinois e Indiana), se recalibra con regresión isotónica usando solo los primeros K años disponibles de ese estado,
K = 0, 3, 5, 10 y 15. K = 0 usa la probabilidad calibrada de la prueba principal (con los tres estados originales).
Se evalúa siempre en los años posteriores a los 15 primeros de cada estado (2006-2025 si el estado tiene datos desde 1991).
Se reporta el Brier frente al Brier de la tasa media de ese estado, y la curva de calibración.
Conclusión fijada: el menor K con el que el Brier queda mejor que la tasa media en al menos 5 de los 7 estados.

Requiere 35. Salidas en datos/procesados/: cierre_calibracion_brier.csv, cierre_calibracion_curva.csv, cierre_calibracion_criterio.json
Uso:  python scripts/41_calibracion_local.py
"""
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
PROCESADOS = RAIZ / "datos" / "procesados"
KS = [0, 3, 5, 10, 15]
MAX_K = max(KS)
MINIMO_ESTADOS = 5
Y = "perdida_previa"


def calibrar(d, k):
    """Probabilidad recalibrada para los años de evaluación de un estado, con los primeros k años del estado."""
    anios = sorted(d["anio"].unique())
    evalua = d[d["anio"] > anios[MAX_K - 1]].copy()
    if k == 0:
        evalua["prob_local"] = evalua["prob_calibrada"]               # sin datos locales: la calibración de los tres estados
    else:
        local = d[d["anio"].isin(anios[:k])]
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(local["prob"], local[Y])
        evalua["prob_local"] = iso.predict(evalua["prob"])
    return evalua


def main():
    p = pd.read_csv(PROCESADOS / "ciegas_predicciones_principal.csv", dtype={"unidad": str, "grupo": str})
    p = p[p["nuevo"]]
    filas, curvas = [], []
    for k in KS:
        todos = []
        for estado, d in p.groupby("estado"):
            e = calibrar(d, k)
            brier, tasa = brier_score_loss(e[Y], e["prob_local"]), brier_score_loss(e[Y], np.full(len(e), e[Y].mean()))
            filas.append({"K": k, "estado": estado, "anios_calibracion": k, "anios_evaluacion": e["anio"].nunique(),
                          "primer_anio_evaluacion": int(e["anio"].min()), "filas": len(e), "perdidas": int(e[Y].sum()),
                          "tasa_perdida": e[Y].mean(), "brier": brier, "brier_tasa_media": tasa, "mejor_que_tasa_media": bool(brier < tasa),
                          "ganancia_pct": 100 * (tasa - brier) / tasa})
            todos.append(e.assign(K=k))
        t = pd.concat(todos, ignore_index=True)
        filas.append({"K": k, "estado": "siete estados juntos", "anios_calibracion": k, "anios_evaluacion": t["anio"].nunique(),
                      "primer_anio_evaluacion": int(t["anio"].min()), "filas": len(t), "perdidas": int(t[Y].sum()), "tasa_perdida": t[Y].mean(),
                      "brier": brier_score_loss(t[Y], t["prob_local"]), "brier_tasa_media": brier_score_loss(t[Y], np.full(len(t), t[Y].mean())),
                      "mejor_que_tasa_media": np.nan, "ganancia_pct": np.nan})
        t["grupo_prob"] = pd.qcut(t["prob_local"].rank(method="first"), 10, labels=False)
        c = t.groupby("grupo_prob").agg(prob_media=("prob_local", "mean"), perdida_observada=(Y, "mean"), filas=(Y, "size")).reset_index()
        curvas.append(c.assign(K=k))
    brier = pd.DataFrame(filas)
    curva = pd.concat(curvas, ignore_index=True)
    brier.to_csv(PROCESADOS / "cierre_calibracion_brier.csv", index=False)
    curva.to_csv(PROCESADOS / "cierre_calibracion_curva.csv", index=False)

    por_estado = brier[brier["estado"] != "siete estados juntos"]
    cuenta = por_estado.groupby("K")["mejor_que_tasa_media"].sum().astype(int)
    cumplen = [int(k) for k in KS if cuenta[k] >= MINIMO_ESTADOS]
    crit = {"estados_mejores_que_tasa_media_por_K": {str(k): int(v) for k, v in cuenta.items()}, "minimo_estados": MINIMO_ESTADOS,
            "menor_K_que_cumple": cumplen[0] if cumplen else None, "ninguno_cumple": not cumplen,
            "anios_de_evaluacion": f"{int(brier['primer_anio_evaluacion'].min())}-2025"}
    (PROCESADOS / "cierre_calibracion_criterio.json").write_text(json.dumps(crit, indent=1, ensure_ascii=False), encoding="utf-8")
    pd.set_option("display.width", 250, "display.max_columns", 30)
    print(brier.round(4).to_string(index=False))
    print(json.dumps(crit, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
