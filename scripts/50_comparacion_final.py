"""
50_comparacion_final.py
Comparación final a ciegas: 5 modelos x 2 conjuntos de variables (clima mensual, y clima mensual + grados-día),
entrenados solo con Iowa, Illinois e Indiana y probados año por año en los siete estados nuevos
(plan congelado en docs/bitacora.md, 2026-11-08, sexta parte).

Se escoge con los estados nuevos en 1991-2010; 2011-2025 es la confirmación. El elegido se reentrena con los diez
estados (1981-2025) y se guarda en modelos/modelo_final.joblib.

Requiere 34 (eeuu_ciegas_base.csv) y 49 (eeuu_grados_dia.csv).
Salidas: datos/procesados/final_predicciones.csv, final_resultados.csv, final_por_estado.csv, final_eleccion.json;
modelos/modelo_final.joblib y modelos/modelo_final.json.
Uso:  python scripts/50_comparacion_final.py   (unos 45 minutos)
"""
import importlib
import json
import sys
import warnings
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import SplineTransformer, StandardScaler

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
e47 = importlib.import_module("47_cinco_modelos")

PROCESADOS = RAIZ / "datos" / "procesados"
MODELOS_DIR = RAIZ / "modelos"
SEMILLA = 2026
DESDE, FIN_SELECCION, HASTA = 1991, 2010, 2025
ORIGINALES = {"17", "18", "19"}
ESTADOS = {"17": "Illinois", "18": "Indiana", "19": "Iowa", "31": "Nebraska", "27": "Minnesota", "39": "Ohio", "29": "Missouri",
           "20": "Kansas", "46": "South Dakota", "55": "Wisconsin"}
EMPATE = 0.01
N_REMUESTREOS = 1000

CLIMA = ["lluvia_may", "lluvia_jun", "lluvia_jul", "lluvia_ago", "lluvia_sep", "racha_meses_secos", "deficit_jul_ago",
         "tmax_jun", "tmax_jul", "tmax_ago", "palmer_jun", "palmer_jul", "palmer_ago"]
GRADOS_DIA = ["gd_10_29_jun", "gd_10_29_jul", "gd_10_29_ago", "gd_29_jun", "gd_29_jul", "gd_29_ago",
              "gd_10_29_jun_ago", "gd_29_jun_ago", "dias_tmax_35_jun_ago"]
CONJUNTOS = {"A": CLIMA, "B": CLIMA + GRADOS_DIA}
SIGNO = dict(e47.SIGNO, **{v: 1 for v in GRADOS_DIA if v.startswith(("gd_29", "dias_tmax_35"))})
MODELOS = ["logistica", "splines", "monotono", "bosque", "boosting"]
NOMBRES = {"logistica": "Regresión logística", "splines": "Logística con splines", "monotono": "Boosting monótono",
           "bosque": "Bosque aleatorio", "boosting": "Boosting de gradiente", "lgbm": "LightGBM (referencia)",
           "ref_regla": "Referencia: regla de lluvia jun-ago", "ref_calor": "Referencia: índice de calor jul-ago",
           "ref_gd29": "Referencia: grados-día > 29 °C jun-ago", "ref_tasa": "Referencia: tasa previa del condado", "ref_azar": "Referencia: azar"}
REJILLAS = dict(e47.REJILLAS, lgbm=[{"num_leaves": n, "min_child_samples": m} for n in (7, 15, 31) for m in (20, 50)])


def crear(nombre, p, cols):
    escalar = nombre in ("logistica", "splines")
    pasos = [SimpleImputer(strategy="median")] + ([StandardScaler()] if escalar else []) + ([SplineTransformer(n_knots=4, degree=3)] if nombre == "splines" else [])
    prep = ColumnTransformer([("num", make_pipeline(*pasos), cols)])
    if nombre in ("logistica", "splines"):
        final = LogisticRegression(max_iter=3000, **p)
    elif nombre == "bosque":
        final = RandomForestClassifier(n_estimators=300, n_jobs=-1, random_state=SEMILLA, **p)
    elif nombre == "lgbm":
        final = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.03, subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
                                   random_state=SEMILLA, verbose=-1, n_jobs=-1, **p)
    else:
        cst = [SIGNO.get(v, 0) for v in cols] if nombre == "monotono" else None
        final = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.03, random_state=SEMILLA, monotonic_cst=cst, **p)
    return make_pipeline(prep, final)


def ajustar(nombre, cols, tr):
    """Hiperparámetros por AUC en los 3 últimos años de tr; reentrena con todo tr; calibra con isotónica en esos 3 años."""
    anios = sorted(tr["anio"].unique())
    corte = anios[-e47.ANIOS_AJUSTE]
    viejos, recientes = tr[tr["anio"] < corte], tr[tr["anio"] >= corte]
    se_puede = recientes["y"].nunique() == 2 and viejos["y"].nunique() == 2
    mejor, mejor_auc, prob_rec = REJILLAS[nombre][0], -1.0, None
    for p in (REJILLAS[nombre] if se_puede else REJILLAS[nombre][:1]):
        m = crear(nombre, p, cols).fit(viejos[cols], viejos["y"])
        prob = m.predict_proba(recientes[cols])[:, 1]
        auc = roc_auc_score(recientes["y"], prob) if se_puede else np.nan
        if not se_puede or auc > mejor_auc:
            mejor, mejor_auc, prob_rec = p, auc, prob
    final = crear(nombre, mejor, cols).fit(tr[cols], tr["y"])
    cal = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(prob_rec, recientes["y"]) if recientes["y"].nunique() == 2 else None
    return final, cal, mejor


def cargar():
    b = pd.read_csv(PROCESADOS / "eeuu_ciegas_base.csv", dtype={"unidad": str, "grupo": str})
    g = pd.read_csv(PROCESADOS / "eeuu_grados_dia.csv", dtype={"unidad": str})
    b = b.merge(g, on=["unidad", "anio"], how="left")
    print(f"Base: {len(b):,} condado-años; con grados-día: {b['gd_29_jun_ago'].notna().mean():.1%}")
    a = pd.read_csv(PROCESADOS / "chirps_mensual_condados_eeuu.csv", dtype={"fips": str})
    n = pd.read_csv(PROCESADOS / "chirps_mensual_condados_nuevos.csv", dtype={"fips": str})
    m = pd.concat([a, n], ignore_index=True)
    m = m[m["mes"].isin([6, 7, 8]) & (m["anio"] <= HASTA)]
    v = m.groupby(["fips", "anio"]).agg(mm=("lluvia_mm", "sum"), n=("mes", "size")).reset_index()
    lluvia = v[v["n"] == 3].rename(columns={"fips": "unidad"})[["unidad", "anio", "mm"]]
    return b, lluvia


def hacia_adelante(b, lluvia):
    bo, bn = b[b["grupo"].isin(ORIGINALES)], b[~b["grupo"].isin(ORIGINALES)]
    partes = []
    for t in range(DESDE, HASTA + 1):
        tr, _ = e47.etiquetas(bo, t)                 # entrenamiento: solo los tres estados originales
        tr_n, pr = e47.etiquetas(bn, t)              # predicción: los siete estados nuevos
        if pr.empty or tr["y"].nunique() < 2:
            continue
        r = pr[["unidad", "anio", "grupo", "y"]].copy()
        for conjunto, cols in CONJUNTOS.items():
            for nombre in MODELOS + (["lgbm"] if conjunto == "B" else []):
                final, cal, p = ajustar(nombre, cols, tr)
                prob = final.predict_proba(pr[cols])[:, 1]
                clave = f"{nombre}_{conjunto}"
                r[clave] = prob
                r[clave + "_cal"] = cal.predict(prob) if cal is not None else prob
        r["pago_regla"], r["ref_regla"] = e47.regla(lluvia, pr[["unidad", "anio"]], t - 1)
        r["ref_calor"] = (pr["tmax_jul"] + pr["tmax_ago"]).to_numpy()
        r["ref_gd29"] = pr["gd_29_jun_ago"].fillna(pr["gd_29_jun_ago"].median()).to_numpy()
        r["ref_tasa"] = pr["unidad"].map(tr_n.groupby("unidad")["y"].mean()).fillna(tr_n["y"].mean() if len(tr_n) else 0).to_numpy()
        r["ref_azar"] = np.random.default_rng(SEMILLA + t).random(len(r))
        partes.append(r)
        print(f"{t}: {len(r)} condados nuevos, {int(r['y'].sum())} pérdidas; entrenamiento {len(tr)} filas", flush=True)
    d = pd.concat(partes, ignore_index=True)
    d["estado"] = d["grupo"].map(ESTADOS)
    return d


def claves():
    return [f"{m}_{c}" for c in CONJUNTOS for m in MODELOS] + ["lgbm_B"]


def nombre_clave(k):
    if k.startswith("ref_"):
        return NOMBRES[k]
    m, c = k.rsplit("_", 1)
    return f"{NOMBRES[m]} [{'clima mensual' if c == 'A' else 'clima + grados-día'}]"


def main():
    b, lluvia = cargar()
    d = hacia_adelante(b, lluvia)
    d.to_csv(PROCESADOS / "final_predicciones.csv", index=False)

    rng = np.random.default_rng(SEMILLA)
    puntajes = claves() + ["ref_regla", "ref_calor", "ref_gd29", "ref_tasa", "ref_azar"]
    filas, por_estado = [], []
    for periodo, sel in [("seleccion 1991-2010", d["anio"] <= FIN_SELECCION), ("confirmacion 2011-2025", d["anio"] > FIN_SELECCION),
                         ("todo 1991-2025", d["anio"] >= DESDE)]:
        g = d[sel]
        for k in puntajes:
            m = e47.medir(g, k, rng, cal=k + "_cal" if not k.startswith("ref_") else None)
            filas.append({"periodo": periodo, "clave": k, "modelo": nombre_clave(k), "filas": len(g), "perdidas": int(g["y"].sum()), **m})
            if periodo == "todo 1991-2025":
                for est, ge in g.groupby("estado"):
                    if ge["y"].nunique() == 2:
                        por_estado.append({"clave": k, "modelo": nombre_clave(k), "estado": est, "perdidas": int(ge["y"].sum()),
                                           "auc": roc_auc_score(ge["y"], ge[k])})
    res = pd.DataFrame(filas)
    res["puntaje_eleccion"] = (res["auc"] + res["auc_dentro_anio"]) / 2
    res.to_csv(PROCESADOS / "final_resultados.csv", index=False)
    pe = pd.DataFrame(por_estado)
    pe.to_csv(PROCESADOS / "final_por_estado.csv", index=False)

    # Elección congelada: selección 1991-2010, el más simple dentro de 0,01 (modelos en orden de simpleza; A antes que B)
    sel = res[(res["periodo"] == "seleccion 1991-2010") & res["clave"].isin([f"{m}_{c}" for c in CONJUNTOS for m in MODELOS])].set_index("clave")
    mejor = sel["puntaje_eleccion"].max()
    orden = [f"{m}_{c}" for c in ["A", "B"] for m in MODELOS]
    orden = sorted(orden, key=lambda k: (MODELOS.index(k.rsplit("_", 1)[0]), k.endswith("_B")))
    candidatos = [k for k in orden if sel.loc[k, "puntaje_eleccion"] >= mejor - EMPATE]
    elegido = candidatos[0]
    conf = res[res["periodo"] == "confirmacion 2011-2025"].set_index("clave")
    mejor_simple = max(conf.loc["ref_calor", "auc"], conf.loc["ref_gd29", "auc"])
    ventaja = conf.loc[elegido, "auc"] - mejor_simple
    eleccion = {"elegido": elegido, "nombre": nombre_clave(elegido), "puntaje_seleccion": sel.loc[elegido, "puntaje_eleccion"],
                "mejor_puntaje_seleccion": mejor, "empatados_dentro_de_0_01": candidatos,
                "auc_confirmacion": conf.loc[elegido, "auc"], "auc_dentro_confirmacion": conf.loc[elegido, "auc_dentro_anio"],
                "mejor_indice_simple_confirmacion": mejor_simple, "ventaja_sobre_indice_simple": ventaja,
                "supera_indice_simple_por_mas_de_0_02": bool(ventaja > 0.02)}
    (PROCESADOS / "final_eleccion.json").write_text(json.dumps(eleccion, ensure_ascii=False, indent=2, default=float), encoding="utf-8")

    pd.set_option("display.width", 240)
    pd.set_option("display.max_colwidth", 70)
    ver = ["modelo", "auc", "auc_ic_inf", "auc_ic_sup", "auc_sin_2012", "auc_dentro_anio", "anios_dentro", "heidke", "brier_calibrado", "brier_tasa", "puntaje_eleccion"]
    for periodo in res["periodo"].unique():
        print(f"\n== {periodo} (siete estados nuevos)")
        print(res[res["periodo"] == periodo].sort_values("puntaje_eleccion", ascending=False)[ver].round(3).to_string(index=False))
    print("\n== AUC por estado, todo 1991-2025")
    print(pe.pivot_table(index="modelo", columns="estado", values="auc").round(3).to_string())
    print(f"\nElegido: {nombre_clave(elegido)}; empatados dentro de 0,01: {candidatos}")
    print(f"Confirmación: AUC {conf.loc[elegido, 'auc']:.3f} frente a {mejor_simple:.3f} del mejor índice simple (ventaja {ventaja:+.3f})")

    # Modelo final: diez estados, 1981-2025
    nombre, conjunto = elegido.rsplit("_", 1)
    cols = CONJUNTOS[conjunto]
    tr = pd.concat([e47.etiquetas(b[b["grupo"].isin(ORIGINALES)], HASTA + 1)[0], e47.etiquetas(b[~b["grupo"].isin(ORIGINALES)], HASTA + 1)[0]], ignore_index=True)
    final, cal, p = ajustar(nombre, cols, tr)
    MODELOS_DIR.mkdir(exist_ok=True)
    joblib.dump({"modelo": final, "calibrador": cal, "columnas": cols}, MODELOS_DIR / "modelo_final.joblib")
    meta = {"modelo": nombre_clave(elegido), "clave": elegido, "hiperparametros": p, "entrenado_con": "diez estados, 1981-2025",
            "filas_entrenamiento": len(tr), "perdidas_entrenamiento": int(tr["y"].sum()), "calibrado": cal is not None, "variables": cols,
            "etiqueta": "rendimiento del condado de 80 % o menos de su tendencia lineal (años anteriores)",
            "como_predecir": "python scripts/48_predecir.py archivo.csv (columnas: las de 'variables')",
            "advertencia": "Probabilidades calibradas con los tres años más recientes de los diez estados; en otra zona hay que recalibrar con datos locales.",
            "eleccion": eleccion}
    (MODELOS_DIR / "modelo_final.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    print(f"\nModelo final guardado: {nombre_clave(elegido)}, {p}; calibrado: {cal is not None}; {len(tr):,} filas de entrenamiento")


if __name__ == "__main__":
    main()
