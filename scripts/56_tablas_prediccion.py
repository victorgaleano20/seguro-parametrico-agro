"""
56_tablas_prediccion.py
Tabla liviana para la página "Predicción" de la app (plan en docs/bitacora.md, 2026-11-12).

Una fila por condado-año (diez estados, 1991-2025) con las 13 variables de clima que usa el modelo final, la pérdida
(misma etiqueta de 53: tendencia con años anteriores), la probabilidad del modelo final guardado, el índice de calor,
la lluvia de junio a agosto en % de lo normal, el valor esperado de la cosecha, el área cosechada y el tamaño medio de
las pérdidas previas. La app no puede leer eeuu_ciegas_base.csv (pesa más de 10 MB y no se sube a git).

Requiere 34 (eeuu_ciegas_base.csv), 38 (ciegas_impacto_detalle.csv), 50 (modelo_final.joblib) y 53.
Salida: datos/procesados/app_prediccion.csv
Uso:  python scripts/56_tablas_prediccion.py
"""
import sys
from pathlib import Path

import joblib
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
RAIZ = Path(__file__).resolve().parents[1]
PROCESADOS = RAIZ / "datos" / "procesados"
ACRE_A_HA = 0.404686


def main():
    paquete = joblib.load(RAIZ / "modelos" / "modelo_final.joblib")
    cols = paquete["columnas"]
    base = pd.read_csv(PROCESADOS / "eeuu_ciegas_base.csv", dtype={"unidad": str, "grupo": str},
                       usecols=["unidad", "anio", "nombre", "nombre_grupo"] + cols)
    pred = pd.read_csv(PROCESADOS / "modelo_final_predicciones.csv", dtype={"unidad": str, "grupo": str},
                       usecols=["unidad", "anio", "grupo", "estado", "y", "valor_esperado_usd", "perdida_usd", "severidad_media_previa"])
    area = pd.read_csv(PROCESADOS / "ciegas_impacto_detalle.csv", dtype={"unidad": str}, usecols=["unidad", "anio", "area_cosechada_acres"])
    d = pred.merge(base, on=["unidad", "anio"], how="inner").merge(area, on=["unidad", "anio"], how="left")
    d["prob_modelo"] = paquete["modelo"].predict_proba(d[cols])[:, 1]          # modelo final guardado (el que usa la página)
    d["indice_calor"] = d["tmax_jul"] + d["tmax_ago"]
    d["lluvia_jja_pct"] = d[["lluvia_jun", "lluvia_jul", "lluvia_ago"]].mean(axis=1)
    d["area_ha"] = d["area_cosechada_acres"] * ACRE_A_HA
    d = d.rename(columns={"nombre": "condado", "nombre_grupo": "sigla", "y": "perdida"}).drop(columns="area_cosechada_acres")
    d["perdida"] = d["perdida"].astype(bool)
    redondeo = {c: 3 for c in cols} | {"prob_modelo": 5, "indice_calor": 3, "lluvia_jja_pct": 2, "valor_esperado_usd": 0,
                                       "perdida_usd": 0, "severidad_media_previa": 4, "area_ha": 1}
    d = d.round(redondeo).sort_values(["unidad", "anio"])
    d.to_csv(PROCESADOS / "app_prediccion.csv", index=False)
    print(f"app_prediccion.csv: {len(d):,} condado-años, {d['unidad'].nunique()} condados, {int(d['perdida'].sum())} pérdidas")


if __name__ == "__main__":
    main()
