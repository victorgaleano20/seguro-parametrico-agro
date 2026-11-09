"""
52_grados_dia_anomalia.py
EXPLORATORIO (plan en docs/bitacora.md, 2026-11-08, octava parte): los mismos 5 modelos y el mismo esquema a ciegas de
50_comparacion_final.py, con el conjunto C = clima mensual + grados-día como diferencia frente al promedio 1981-1994
del mismo condado. No cambia la elección del modelo final: la idea salió de mirar los estados de prueba en el EDA.

Requiere 34 y 49. Salidas: datos/procesados/exploratorio_c_predicciones.csv y exploratorio_c_resultados.csv
Uso:  python scripts/52_grados_dia_anomalia.py   (unos 25 minutos)
"""
import importlib
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
e47 = importlib.import_module("47_cinco_modelos")
e50 = importlib.import_module("50_comparacion_final")

PROCESADOS = RAIZ / "datos" / "procesados"
NORMAL_INI, NORMAL_FIN = 1981, 1994
ANOMALIAS = [v + "_dif" for v in e50.GRADOS_DIA]


def main():
    b, lluvia = e50.cargar()
    g = pd.read_csv(PROCESADOS / "eeuu_grados_dia.csv", dtype={"unidad": str})
    normal = g[g["anio"].between(NORMAL_INI, NORMAL_FIN)].groupby("unidad")[e50.GRADOS_DIA].mean()
    dif = (g.set_index("unidad")[e50.GRADOS_DIA] - normal.reindex(g["unidad"]).to_numpy()).add_suffix("_dif")
    g = pd.concat([g[["unidad", "anio"]].reset_index(drop=True), dif.reset_index(drop=True)], axis=1)
    b = b.merge(g, on=["unidad", "anio"], how="left")

    e50.CONJUNTOS = {"C": e50.CLIMA + ANOMALIAS}
    e50.SIGNO.update({v + "_dif": 1 for v in e50.GRADOS_DIA if v.startswith(("gd_29", "dias_tmax_35"))})
    # Solo los 5 modelos (sin la referencia de LightGBM): hacia_adelante de 50 la agrega solo al conjunto "B"
    d = e50.hacia_adelante(b, lluvia)
    d.to_csv(PROCESADOS / "exploratorio_c_predicciones.csv", index=False)

    rng = np.random.default_rng(e50.SEMILLA)
    filas = []
    for periodo, sel in [("seleccion 1991-2010", d["anio"] <= e50.FIN_SELECCION), ("confirmacion 2011-2025", d["anio"] > e50.FIN_SELECCION),
                         ("todo 1991-2025", d["anio"] >= e50.DESDE)]:
        gg = d[sel]
        for m in e50.MODELOS:
            k = f"{m}_C"
            filas.append({"periodo": periodo, "clave": k, "modelo": e50.NOMBRES[m] + " [clima + grados-día frente a lo normal]",
                          **e47.medir(gg, k, rng, cal=k + "_cal")})
    res = pd.DataFrame(filas)
    res["puntaje_eleccion"] = (res["auc"] + res["auc_dentro_anio"]) / 2
    res.to_csv(PROCESADOS / "exploratorio_c_resultados.csv", index=False)
    pd.set_option("display.width", 220)
    print(res[["periodo", "modelo", "auc", "auc_sin_2012", "auc_dentro_anio", "brier_calibrado", "brier_tasa", "puntaje_eleccion"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
