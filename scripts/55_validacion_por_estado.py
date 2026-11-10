"""
55_validacion_por_estado.py
Validación dejando un estado afuera, hacia adelante (plan congelado en docs/bitacora.md, 2026-11-09, segunda parte).

Para cada estado s y cada año t de 1991 a 2025, el modelo final (logística con splines, conjunto A, sin calibrar) se entrena
con los otros nueve estados y los años anteriores a t, y predice el año t en s. Se compara con la prueba a ciegas 3->7
(final_predicciones.csv), con el índice de calor de julio y agosto, con la regla de lluvia y con el azar.

Requiere 34 (eeuu_ciegas_base.csv), 49 (eeuu_grados_dia.csv) y 50 (final_predicciones.csv).
Salidas: datos/procesados/estado_predicciones.csv, estado_resultados.csv y estado_diferencias.csv
Uso:  python scripts/55_validacion_por_estado.py   (alrededor de una hora)
"""
import importlib
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
e47 = importlib.import_module("47_cinco_modelos")
e50 = importlib.import_module("50_comparacion_final")

PROCESADOS = RAIZ / "datos" / "procesados"
SEMILLA = 2026
N_REMUESTREOS = 1000
MIN_PERDIDAS_ANIO = 10
COLS = e50.CONJUNTOS["A"]
PUNTAJES = ["prob_91", "prob_37", "ref_calor", "ref_regla"]
NOMBRES = {"prob_91": "Modelo, 9 estados -> 1", "prob_37": "Modelo, 3 -> 7 (prueba a ciegas)",
           "ref_calor": "Índice de calor jul-ago", "ref_regla": "Regla de lluvia jun-ago"}
PERIODOS = {"todo": (1991, 2025), "seleccion": (1991, 2010), "confirmacion": (2011, 2025)}
COMPARACIONES = [("prob_91", "prob_37"), ("prob_91", "ref_calor"), ("prob_91", "ref_regla"), ("prob_37", "ref_calor")]


def predecir(b, lluvia):
    partes = []
    estados = sorted(b["grupo"].unique())
    for t in range(e50.DESDE, e50.HASTA + 1):
        inicio = time.time()
        tr_todo, pr_todo = e47.etiquetas(b, t)          # la tendencia es por condado: no depende de qué estados entran
        if pr_todo.empty:
            continue
        pago, ref = e47.regla(lluvia, pr_todo[["unidad", "anio"]], t - 1)
        pr_todo = pr_todo.assign(pago_regla=pago, ref_regla=ref, ref_calor=pr_todo["tmax_jul"] + pr_todo["tmax_ago"])
        for s in estados:
            tr, pr = tr_todo[tr_todo["grupo"] != s], pr_todo[pr_todo["grupo"] == s]
            if pr.empty or tr["y"].nunique() < 2:
                continue
            final, _, p = e50.ajustar("splines", COLS, tr)
            r = pr[["unidad", "anio", "grupo", "y", "pago_regla", "ref_regla", "ref_calor"]].copy()
            r["prob_91"] = final.predict_proba(pr[COLS])[:, 1]
            r["C"] = p["C"]
            partes.append(r)
        print(f"{t}: {len(pr_todo)} condados, {int(pr_todo['y'].sum())} pérdidas ({time.time() - inicio:.0f} s)", flush=True)
    d = pd.concat(partes, ignore_index=True)
    d["estado"] = d["grupo"].map(e50.ESTADOS)
    d["nuevo"] = ~d["grupo"].isin(e50.ORIGINALES)
    return d


def dentro(pa, k, pesos=None):
    ok = (pa["perdidas"] >= MIN_PERDIDAS_ANIO) & pa[k].notna()
    w = pa.loc[ok, "perdidas"] * (1 if pesos is None else pesos[ok])
    return np.average(pa.loc[ok, k], weights=w) if w.sum() > 0 else np.nan


def medir(g, puntajes, rng):
    """Métricas puntuales, rangos de 95 % y diferencias pareadas remuestreando años completos."""
    filas_anio = []
    for anio, a in g.groupby("anio"):
        fila = {"anio": anio, "perdidas": int(a["y"].sum())}
        for k in puntajes:
            fila[k] = roc_auc_score(a["y"], a[k]) if a["y"].nunique() == 2 else np.nan
        filas_anio.append(fila)
    pa = pd.DataFrame(filas_anio)
    anios = pa["anio"].to_numpy()
    bloques = {a: (x["y"].to_numpy(), {k: x[k].to_numpy() for k in puntajes}) for a, x in g.groupby("anio")}
    rem = {k: [] for k in puntajes}
    rem_d = {k: [] for k in puntajes}
    for _ in range(N_REMUESTREOS):
        elegidos = rng.choice(anios, len(anios))
        y = np.concatenate([bloques[a][0] for a in elegidos])
        pesos = pa["anio"].map(pd.Series(elegidos).value_counts()).fillna(0)
        for k in puntajes:
            s = np.concatenate([bloques[a][1][k] for a in elegidos])
            rem[k].append(roc_auc_score(y, s) if 0 < y.sum() < len(y) else np.nan)
            rem_d[k].append(dentro(pa, k, pesos))
    sin = g[g["anio"] != 2012]
    puntos = {k: {"auc": roc_auc_score(g["y"], g[k]), "auc_ic_inf": np.nanpercentile(rem[k], 2.5), "auc_ic_sup": np.nanpercentile(rem[k], 97.5),
                  "auc_sin_2012": roc_auc_score(sin["y"], sin[k]) if sin["y"].nunique() == 2 else np.nan,
                  "auc_dentro": dentro(pa, k), "dentro_ic_inf": np.nanpercentile(rem_d[k], 2.5), "dentro_ic_sup": np.nanpercentile(rem_d[k], 97.5)}
              for k in puntajes}
    return puntos, {k: np.array(v) for k, v in rem.items()}, {k: np.array(v) for k, v in rem_d.items()}


def main():
    b, lluvia = e50.cargar()
    d = predecir(b, lluvia)
    previo = pd.read_csv(PROCESADOS / "final_predicciones.csv", dtype={"unidad": str})[["unidad", "anio", "y", "splines_A"]]
    d = d.merge(previo.rename(columns={"y": "y_37", "splines_A": "prob_37"}), on=["unidad", "anio"], how="left")
    nuevos = d[d["nuevo"]]
    coinciden = (nuevos["y"] == nuevos["y_37"]).mean()
    print(f"\nEtiqueta igual a la de la prueba a ciegas en {coinciden:.1%} de las filas de los siete estados; "
          f"sin predicción 3->7: {nuevos['prob_37'].isna().sum()} filas")
    d = d.drop(columns="y_37")
    d["y"] = d["y"].astype(int)
    d.to_csv(PROCESADOS / "estado_predicciones.csv", index=False)

    rng = np.random.default_rng(SEMILLA)
    filas, difs = [], []
    grupos = {"diez": d, "siete": d[d["nuevo"]], "tres": d[~d["nuevo"]]}
    grupos.update({f"estado: {e}": x for e, x in d.groupby("estado")})
    for gnombre, gg in grupos.items():
        for pnombre, (desde, hasta) in PERIODOS.items():
            g = gg[gg["anio"].between(desde, hasta)]
            if g["y"].nunique() < 2:
                continue
            puntajes = [k for k in PUNTAJES if g[k].notna().all()]
            puntos, rem, rem_d = medir(g, puntajes, rng)
            for k, m in puntos.items():
                filas.append({"grupo": gnombre, "periodo": pnombre, "puntaje": k, "nombre": NOMBRES[k], "filas": len(g),
                              "perdidas": int(g["y"].sum()), **m})
            for a, c in COMPARACIONES:
                if a in rem and c in rem:
                    da, dd = rem[a] - rem[c], rem_d[a] - rem_d[c]
                    difs.append({"grupo": gnombre, "periodo": pnombre, "comparacion": f"{a} - {c}",
                                 "dif_auc": puntos[a]["auc"] - puntos[c]["auc"],
                                 "dif_auc_inf": np.nanpercentile(da, 2.5), "dif_auc_sup": np.nanpercentile(da, 97.5),
                                 "no_gana_auc": np.nanmean(da <= 0),
                                 "dif_dentro": puntos[a]["auc_dentro"] - puntos[c]["auc_dentro"],
                                 "dif_dentro_inf": np.nanpercentile(dd, 2.5), "dif_dentro_sup": np.nanpercentile(dd, 97.5),
                                 "no_gana_dentro": np.nanmean(dd <= 0)})
        print(f"Medido: {gnombre}", flush=True)
    res, dif = pd.DataFrame(filas), pd.DataFrame(difs)
    res.to_csv(PROCESADOS / "estado_resultados.csv", index=False)
    dif.to_csv(PROCESADOS / "estado_diferencias.csv", index=False)

    pd.set_option("display.width", 240)
    ver = ["grupo", "periodo", "nombre", "auc", "auc_ic_inf", "auc_ic_sup", "auc_sin_2012", "auc_dentro", "dentro_ic_inf", "dentro_ic_sup"]
    print(res[~res["grupo"].str.startswith("estado")][ver].round(3).to_string(index=False))
    print(dif[~dif["grupo"].str.startswith("estado")].round(3).to_string(index=False))
    por_estado = res[(res["periodo"] == "todo") & res["grupo"].str.startswith("estado")]
    print(por_estado.pivot_table(index="grupo", columns="puntaje", values="auc").round(3).to_string())
    print(dif[(dif["periodo"] == "todo") & dif["grupo"].str.startswith("estado")].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
