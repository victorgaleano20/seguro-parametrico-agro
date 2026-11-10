"""
54_tablas_app.py
Tablas precalculadas para la app (plan en docs/bitacora.md, 2026-11-09).

Para cada grupo de estados (diez, siete nuevos, tres originales) y periodo (1991-2025, sin 2012, 1991-2010, 2011-2025):
AUC global y dentro de cada año del modelo final, del índice de calor y de la regla de lluvia, con rangos de 95 %
remuestreando años completos, y la distribución de las diferencias del modelo frente al calor y a la regla
(en cada remuestreo se usan los mismos años para los tres puntajes).

Requiere 53 (modelo_final_predicciones.csv).
Salidas: datos/procesados/app_metricas.csv, app_diferencias.csv y app_auc_por_anio.csv
Uso:  python scripts/54_tablas_app.py   (unos 3 minutos)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
PROCESADOS = RAIZ / "datos" / "procesados"
SEMILLA = 2026
N_REMUESTREOS = 1000
MIN_PERDIDAS_ANIO = 10            # igual que 47: años con al menos 10 pérdidas entran al AUC dentro del año
PUNTAJES = {"prob": "Modelo final", "ref_calor": "Índice de calor jul-ago", "ref_regla": "Regla de lluvia jun-ago"}
GRUPOS = {"siete": "Siete estados nuevos", "tres": "Tres estados originales", "diez": "Diez estados"}
PERIODOS = {"todo": "1991-2025", "sin_2012": "1991-2025 sin 2012", "seleccion": "1991-2010", "confirmacion": "2011-2025",
            "desde_1995": "1995-2025"}   # 1995-2025: sin los años que entran en lo normal (1981-1994); bitácora, 2026-11-09, tercera parte


def filtrar(d, grupo, periodo):
    g = d if grupo == "diez" else d[d["nuevo"] == (grupo == "siete")]
    if periodo == "sin_2012":
        return g[g["anio"] != 2012]
    if periodo == "seleccion":
        return g[g["anio"] <= 2010]
    if periodo == "confirmacion":
        return g[g["anio"] > 2010]
    if periodo == "desde_1995":
        return g[g["anio"] >= 1995]
    return g


def por_anio(g):
    """AUC de cada año y su número de pérdidas (solo años con pérdidas y sin pérdidas)."""
    filas = []
    for anio, a in g.groupby("anio"):
        fila = {"anio": anio, "filas": len(a), "perdidas": int(a["y"].sum())}
        for k in PUNTAJES:
            fila[k] = roc_auc_score(a["y"], a[k]) if a["y"].nunique() == 2 else np.nan
        filas.append(fila)
    return pd.DataFrame(filas)


def dentro(pa, k, pesos=None):
    """AUC dentro del año, ponderado por pérdidas, en años con 10 o más pérdidas (como 47.auc_dentro)."""
    ok = (pa["perdidas"] >= MIN_PERDIDAS_ANIO) & pa[k].notna()
    w = pa.loc[ok, "perdidas"] * (1 if pesos is None else pesos[ok])
    return np.average(pa.loc[ok, k], weights=w) if w.sum() > 0 else np.nan


def main():
    d = pd.read_csv(PROCESADOS / "modelo_final_predicciones.csv", dtype={"unidad": str})
    d["y"] = d["y"].astype(int)
    rng = np.random.default_rng(SEMILLA)
    metricas, diferencias, anios_tabla = [], [], []
    for grupo, gnombre in GRUPOS.items():
        for periodo, pnombre in PERIODOS.items():
            g = filtrar(d, grupo, periodo)
            pa = por_anio(g)
            if periodo == "todo":
                anios_tabla.append(pa.assign(grupo=grupo))
            anios = pa["anio"].to_numpy()
            bloques = {a: (x["y"].to_numpy(), {k: x[k].to_numpy() for k in PUNTAJES}) for a, x in g.groupby("anio")}
            remuestreos = {k: [] for k in PUNTAJES}
            remuestreos_dentro = {k: [] for k in PUNTAJES}
            for _ in range(N_REMUESTREOS):
                elegidos = rng.choice(anios, len(anios))
                y = np.concatenate([bloques[a][0] for a in elegidos])
                cuenta = pd.Series(elegidos).value_counts()
                pesos = pa["anio"].map(cuenta).fillna(0)
                for k in PUNTAJES:
                    s = np.concatenate([bloques[a][1][k] for a in elegidos])
                    remuestreos[k].append(roc_auc_score(y, s) if 0 < y.sum() < len(y) else np.nan)
                    remuestreos_dentro[k].append(dentro(pa, k, pesos))
            for k, nombre in PUNTAJES.items():
                r, rd = np.array(remuestreos[k]), np.array(remuestreos_dentro[k])
                metricas.append({"grupo": grupo, "periodo": periodo, "puntaje": k, "nombre": nombre, "filas": len(g),
                                 "perdidas": int(g["y"].sum()), "auc": roc_auc_score(g["y"], g[k]),
                                 "auc_ic_inf": np.nanpercentile(r, 2.5), "auc_ic_sup": np.nanpercentile(r, 97.5),
                                 "auc_dentro": dentro(pa, k), "dentro_ic_inf": np.nanpercentile(rd, 2.5),
                                 "dentro_ic_sup": np.nanpercentile(rd, 97.5),
                                 "anios_dentro": int(((pa["perdidas"] >= MIN_PERDIDAS_ANIO) & pa[k].notna()).sum())})
            for comparador in ("ref_calor", "ref_regla"):
                diferencias.append(pd.DataFrame({
                    "grupo": grupo, "periodo": periodo, "comparador": comparador, "remuestreo": range(N_REMUESTREOS),
                    "dif_auc": np.array(remuestreos["prob"]) - np.array(remuestreos[comparador]),
                    "dif_dentro": np.array(remuestreos_dentro["prob"]) - np.array(remuestreos_dentro[comparador])}))
            print(f"{gnombre}, {pnombre}: {len(g):,} filas, {int(g['y'].sum())} pérdidas", flush=True)

    met = pd.DataFrame(metricas)
    met.to_csv(PROCESADOS / "app_metricas.csv", index=False)
    dif = pd.concat(diferencias, ignore_index=True)
    dif.round(5).to_csv(PROCESADOS / "app_diferencias.csv", index=False)
    pd.concat(anios_tabla, ignore_index=True).to_csv(PROCESADOS / "app_auc_por_anio.csv", index=False)

    pd.set_option("display.width", 220)
    print(met[["grupo", "periodo", "nombre", "auc", "auc_ic_inf", "auc_ic_sup", "auc_dentro", "dentro_ic_inf", "dentro_ic_sup"]].round(3).to_string(index=False))
    res = dif.groupby(["grupo", "periodo", "comparador"]).agg(
        dif_auc_inf=("dif_auc", lambda s: s.quantile(0.025)), dif_auc_sup=("dif_auc", lambda s: s.quantile(0.975)),
        no_gana_auc=("dif_auc", lambda s: (s <= 0).mean()), no_gana_dentro=("dif_dentro", lambda s: (s <= 0).mean()))
    print(res.round(3).to_string())


if __name__ == "__main__":
    main()
