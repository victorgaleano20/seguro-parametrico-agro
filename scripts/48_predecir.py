"""
48_predecir.py
Predice la probabilidad de pérdida de maíz con el modelo final que deja 47_cinco_modelos.py (modelos/modelo_final.joblib).

Entrada: un CSV con una fila por condado y año y las columnas de modelos/modelo_final.json ("variables"):
  latitud, longitud, lluvia_may ... lluvia_sep (% de lo normal), racha_meses_secos, deficit_jul_ago,
  tmax_jun ... tmax_ago (diferencia en °C frente a lo normal), palmer_jun ... palmer_ago y grupo (FIPS del estado: 17, 18 o 19).
  Son las mismas columnas de datos/procesados/eeuu_sequia_base.csv (script 28).
Salida: el mismo CSV con prob_perdida (y prob_perdida_calibrada si el modelo trae calibrador), en <archivo>_predicciones.csv.

Uso:  python scripts/48_predecir.py datos/procesados/eeuu_sequia_base.csv
"""
import json
import sys
from pathlib import Path

import joblib
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
RAIZ = Path(__file__).resolve().parents[1]


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    entrada = Path(sys.argv[1])
    paquete = joblib.load(RAIZ / "modelos" / "modelo_final.joblib")
    meta = json.loads((RAIZ / "modelos" / "modelo_final.json").read_text(encoding="utf-8"))
    d = pd.read_csv(entrada, dtype={"unidad": str, "grupo": str})
    faltan = [c for c in paquete["columnas"] if c not in d.columns]
    if faltan:
        print(f"ERROR: faltan columnas en {entrada.name}: {faltan}")
        sys.exit(1)
    prob = paquete["modelo"].predict_proba(d[paquete["columnas"]])[:, 1]
    d["prob_perdida"] = prob
    if paquete["calibrador"] is not None:
        d["prob_perdida_calibrada"] = paquete["calibrador"].predict(prob)
    salida = entrada.with_name(entrada.stem + "_predicciones.csv")
    d.to_csv(salida, index=False)
    print(f"Modelo: {meta['modelo']} ({meta['entrenado_con']})")
    print(f"Predicciones: {len(d):,} filas -> {salida}")
    print(f"AVISO: {meta['advertencia']}")


if __name__ == "__main__":
    main()
