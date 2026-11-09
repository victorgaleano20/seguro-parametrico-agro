"""
47_cinco_modelos.py
Cinco modelos para la probabilidad de pérdida de maíz por condado y elección del mejor
(plan congelado en docs/bitacora.md, 2026-11-08, cuarta parte).

Modelos: regresión logística, logística con splines, bosque aleatorio, boosting de gradiente (equivalente a LightGBM)
y boosting monótono. Referencias: azar, regla de lluvia de junio a agosto, índice de calor de julio y agosto y tasa
previa de pérdida del condado.
Validación año por año 1991-2025 (cada año solo con años anteriores). Se escoge con 1991-2010 (desarrollo);
2011-2025 (prueba) solo se reporta. El elegido se reentrena con 1981-2025 y se guarda en modelos/.

Datos: datos/procesados/eeuu_sequia_base.csv (Iowa, Illinois e Indiana) y chirps_mensual_condados_eeuu.csv.
Salidas: datos/procesados/cinco_modelos_predicciones.csv, cinco_modelos_resultados.csv, cinco_modelos_eleccion.json,
modelos/modelo_final.joblib y modelos/modelo_final.json.
Uso:  python scripts/47_cinco_modelos.py   (unos 20 minutos)
"""
import json
import sys
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, SplineTransformer, StandardScaler

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
import comun  # noqa: E402

PROCESADOS = RAIZ / "datos" / "procesados"
MODELOS_DIR = RAIZ / "modelos"
SEMILLA = 2026
DESDE, FIN_DESARROLLO, HASTA = 1991, 2010, 2025
ANIOS_AJUSTE = 3          # años previos a t para escoger hiperparámetros y calibrar
MIN_ANIOS = 8             # años mínimos para la tendencia de un condado
MIN_PERDIDAS_ANIO = 10    # años con al menos estas pérdidas entran al AUC dentro del año
N_REMUESTREOS = 1000
EMPATE = 0.01

UBICACION = ["latitud", "longitud"]
LLUVIA = ["lluvia_may", "lluvia_jun", "lluvia_jul", "lluvia_ago", "lluvia_sep", "racha_meses_secos", "deficit_jul_ago"]
CALOR = ["tmax_jun", "tmax_jul", "tmax_ago"]
PALMER = ["palmer_jun", "palmer_jul", "palmer_ago"]
NUMERICAS = UBICACION + LLUVIA + CALOR + PALMER
CATEGORICAS = ["grupo"]
COLUMNAS = NUMERICAS + CATEGORICAS
# Signo de la restricción monótona por variable: +1 más riesgo, -1 menos riesgo, 0 libre
SIGNO = {"lluvia_jun": -1, "lluvia_jul": -1, "lluvia_ago": -1, "racha_meses_secos": 1, "deficit_jul_ago": 1,
         "tmax_jun": 1, "tmax_jul": 1, "tmax_ago": 1, "palmer_jun": -1, "palmer_jul": -1, "palmer_ago": -1}
N_ESTADOS = 3             # columnas que agrega el one-hot del estado (IA, IL, IN)

ORDEN_SIMPLEZA = ["logistica", "splines", "monotono", "bosque", "boosting"]
NOMBRES = {"logistica": "Regresión logística", "splines": "Logística con splines", "bosque": "Bosque aleatorio",
           "boosting": "Boosting de gradiente (equivalente a LightGBM)", "monotono": "Boosting monótono",
           "ref_regla": "Referencia: regla de lluvia jun-ago", "ref_calor": "Referencia: índice de calor jul-ago",
           "ref_tasa": "Referencia: tasa previa del condado", "ref_azar": "Referencia: azar"}
REJILLAS = {
    "logistica": [{"C": c} for c in (0.01, 0.1, 1.0)],
    "splines": [{"C": c} for c in (0.01, 0.1, 1.0)],
    "bosque": [{"max_depth": d, "min_samples_leaf": h} for d in (6, 10) for h in (20, 50)],
    "boosting": [{"max_leaf_nodes": n, "min_samples_leaf": h} for n in (15, 31) for h in (20, 50)],
    "monotono": [{"max_leaf_nodes": n, "min_samples_leaf": 50} for n in (7, 15)],
}


def transformador(escalar, splines=False):
    num = [SimpleImputer(strategy="median")] + ([StandardScaler()] if escalar else [])
    if splines:
        num.append(SplineTransformer(n_knots=4, degree=3))
    return ColumnTransformer([("num", make_pipeline(*num), NUMERICAS),
                              ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAS)])


def crear(nombre, p):
    if nombre == "logistica":
        return make_pipeline(transformador(True), LogisticRegression(max_iter=3000, **p))
    if nombre == "splines":
        return make_pipeline(transformador(True, splines=True), LogisticRegression(max_iter=3000, **p))
    if nombre == "bosque":
        return make_pipeline(transformador(False), RandomForestClassifier(n_estimators=300, n_jobs=-1, random_state=SEMILLA, **p))
    restricciones = [SIGNO.get(v, 0) for v in NUMERICAS] + [0] * N_ESTADOS if nombre == "monotono" else None
    return make_pipeline(transformador(False), HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.03, random_state=SEMILLA, monotonic_cst=restricciones, **p))


# ---------------------------------------------------------------- datos y etiquetas
def cargar():
    b = pd.read_csv(PROCESADOS / "eeuu_sequia_base.csv", dtype={"unidad": str, "grupo": str})
    m = pd.read_csv(PROCESADOS / "chirps_mensual_condados_eeuu.csv", dtype={"fips": str})
    m = m[m["mes"].isin([6, 7, 8]) & (m["anio"] <= HASTA)]
    v = m.groupby(["fips", "anio"]).agg(mm=("lluvia_mm", "sum"), n=("mes", "size")).reset_index()
    lluvia = v[v["n"] == 3].rename(columns={"fips": "unidad"})[["unidad", "anio", "mm"]]
    return b, lluvia


def etiquetas(b, t):
    """Igual que 29: pérdida de los años anteriores con su tendencia, y la del año t con la tendencia de años < t."""
    previos = b[b["anio"] < t]
    tend = comun.tendencia(previos, None, MIN_ANIOS)
    tend["y"] = tend["relativo"] <= comun.UMBRAL_PERDIDA
    tr = previos.merge(tend[["unidad", "anio", "y"]], on=["unidad", "anio"])
    ajuste = []
    for unidad, d in previos.groupby("unidad"):
        if len(d) >= MIN_ANIOS:
            pendiente, intercepto = np.polyfit(d["anio"], d["rendimiento_t_ha"], 1)
            ajuste.append((unidad, intercepto + pendiente * t))
    pr = b[b["anio"] == t].merge(pd.DataFrame(ajuste, columns=["unidad", "esperado"]), on="unidad")
    pr = pr[pr["esperado"] > 0].copy()
    pr["y"] = pr["rendimiento_t_ha"] / pr["esperado"] <= comun.UMBRAL_PERDIDA
    return tr, pr


def regla(lluvia, filas, hasta):
    """Paga si la lluvia de junio a agosto queda bajo el percentil 15 del condado (años <= hasta, mínimo 10)."""
    h = lluvia[lluvia["anio"] <= hasta].groupby("unidad")["mm"]
    u = pd.DataFrame({"umbral": h.quantile(0.15), "normal": h.mean(), "n": h.size()})
    u = u[u["n"] >= 10]
    r = filas.merge(lluvia, on=["unidad", "anio"], how="left").merge(u, left_on="unidad", right_index=True, how="left")
    return (r["mm"] < r["umbral"]).fillna(False).to_numpy(), (-(r["mm"] / r["normal"])).to_numpy()


# ---------------------------------------------------------------- ajuste de un modelo para el año t
def ajustar(nombre, tr):
    """Escoge hiperparámetros por AUC en los 3 últimos años de tr, reentrena con todo tr y calibra en esos 3 años."""
    anios = sorted(tr["anio"].unique())
    corte = anios[-ANIOS_AJUSTE]
    viejos, recientes = tr[tr["anio"] < corte], tr[tr["anio"] >= corte]
    mejor, mejor_auc, prob_rec = REJILLAS[nombre][0], -1.0, None
    se_puede = recientes["y"].nunique() == 2 and viejos["y"].nunique() == 2
    for p in (REJILLAS[nombre] if se_puede else REJILLAS[nombre][:1]):
        m = crear(nombre, p).fit(viejos[COLUMNAS], viejos["y"])
        prob = m.predict_proba(recientes[COLUMNAS])[:, 1]
        auc = roc_auc_score(recientes["y"], prob) if se_puede else np.nan
        if not se_puede or auc > mejor_auc:
            mejor, mejor_auc, prob_rec = p, auc, prob
    final = crear(nombre, mejor).fit(tr[COLUMNAS], tr["y"])
    calibrador = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(prob_rec, recientes["y"]) if recientes["y"].nunique() == 2 else None
    return final, calibrador, mejor


def hacia_adelante(b, lluvia):
    partes = []
    for t in range(DESDE, HASTA + 1):
        tr, pr = etiquetas(b, t)
        if pr.empty or tr["y"].nunique() < 2:
            continue
        r = pr[["unidad", "anio", "y"]].copy()
        for nombre in ORDEN_SIMPLEZA:
            final, cal, p = ajustar(nombre, tr)
            prob = final.predict_proba(pr[COLUMNAS])[:, 1]
            r[nombre] = prob
            r[nombre + "_cal"] = cal.predict(prob) if cal is not None else prob
            r[nombre + "_param"] = json.dumps(p)
        r["pago_regla"], r["ref_regla"] = regla(lluvia, pr[["unidad", "anio"]], t - 1)
        r["ref_calor"] = (pr["tmax_jul"] + pr["tmax_ago"]).to_numpy()
        r["ref_tasa"] = pr["unidad"].map(tr.groupby("unidad")["y"].mean()).fillna(tr["y"].mean()).to_numpy()
        r["ref_azar"] = np.random.default_rng(SEMILLA + t).random(len(r))
        partes.append(r)
        print(f"{t}: {len(r)} condados, {int(r['y'].sum())} pérdidas", flush=True)
    return pd.concat(partes, ignore_index=True)


# ---------------------------------------------------------------- métricas
def auc_dentro(d, col):
    w = [(g["y"].sum(), roc_auc_score(g["y"], g[col])) for _, g in d.groupby("anio")
         if g["y"].nunique() == 2 and g["y"].sum() >= MIN_PERDIDAS_ANIO]
    return (np.average([a for _, a in w], weights=[n for n, _ in w]), len(w)) if w else (np.nan, 0)


def medir(d, col, rng, cal=None):
    y = d["y"].to_numpy()
    sin = d[d["anio"] != 2012]
    dentro, n_anios = auc_dentro(d, col)
    pago = comun.pagar_igual_que_regla(d[col].to_numpy(), d["pago_regla"].mean())
    grupos = {a: g for a, g in d.groupby("anio")}
    anios = list(grupos)
    aucs = []
    for _ in range(N_REMUESTREOS):
        m = pd.concat([grupos[a] for a in rng.choice(anios, len(anios))])
        if 0 < m["y"].sum() < len(m):
            aucs.append(roc_auc_score(m["y"], m[col]))
    return {"auc": roc_auc_score(y, d[col]), "auc_ic_inf": np.percentile(aucs, 2.5), "auc_ic_sup": np.percentile(aucs, 97.5),
            "auc_sin_2012": roc_auc_score(sin["y"], sin[col]) if 2012 in grupos else np.nan,
            "auc_dentro_anio": dentro, "anios_dentro": n_anios, "heidke": comun.heidke(y, pago),
            "brier_calibrado": brier_score_loss(y, d[cal]) if cal else np.nan,
            "brier_tasa": brier_score_loss(y, np.full(len(y), y.mean()))}


def main():
    b, lluvia = cargar()
    print(f"Base: {len(b):,} condado-años, {b['unidad'].nunique()} condados, {b['anio'].min()}-{b['anio'].max()}")
    d = hacia_adelante(b, lluvia)
    d.to_csv(PROCESADOS / "cinco_modelos_predicciones.csv", index=False)

    rng = np.random.default_rng(SEMILLA)
    filas = []
    for periodo, sel in [("desarrollo 1991-2010", d["anio"] <= FIN_DESARROLLO), ("prueba 2011-2025", d["anio"] > FIN_DESARROLLO),
                         ("todo 1991-2025", d["anio"] >= DESDE)]:
        g = d[sel]
        for col in ORDEN_SIMPLEZA + ["ref_regla", "ref_calor", "ref_tasa", "ref_azar"]:
            m = medir(g, col, rng, cal=col + "_cal" if col in ORDEN_SIMPLEZA else None)
            filas.append({"periodo": periodo, "clave": col, "modelo": NOMBRES[col], "filas": len(g), "perdidas": int(g["y"].sum()), **m})
    res = pd.DataFrame(filas)
    res["puntaje_eleccion"] = (res["auc"] + res["auc_dentro_anio"]) / 2
    res.to_csv(PROCESADOS / "cinco_modelos_resultados.csv", index=False)

    # Elección con el periodo de desarrollo, según el criterio congelado
    des = res[(res["periodo"] == "desarrollo 1991-2010") & res["clave"].isin(ORDEN_SIMPLEZA)].set_index("clave")
    mejor_puntaje = des["puntaje_eleccion"].max()
    candidatos = [k for k in ORDEN_SIMPLEZA if des.loc[k, "puntaje_eleccion"] >= mejor_puntaje - EMPATE]
    elegido = candidatos[0]                          # el más simple entre los que empatan
    pru = res[res["periodo"] == "prueba 2011-2025"].set_index("clave")
    ventaja_calor = pru.loc[elegido, "auc"] - pru.loc["ref_calor", "auc"]
    eleccion = {"elegido": elegido, "nombre": NOMBRES[elegido], "puntaje_desarrollo": des.loc[elegido, "puntaje_eleccion"],
                "mejor_puntaje_desarrollo": mejor_puntaje, "empatados_dentro_de_0_01": candidatos,
                "auc_prueba": pru.loc[elegido, "auc"], "auc_calor_prueba": pru.loc["ref_calor", "auc"],
                "ventaja_sobre_calor_prueba": ventaja_calor, "supera_calor_por_mas_de_0_02": bool(ventaja_calor > 0.02)}
    (PROCESADOS / "cinco_modelos_eleccion.json").write_text(json.dumps(eleccion, ensure_ascii=False, indent=2, default=float), encoding="utf-8")

    pd.set_option("display.width", 220)
    ver = ["modelo", "auc", "auc_ic_inf", "auc_ic_sup", "auc_sin_2012", "auc_dentro_anio", "heidke", "brier_calibrado", "brier_tasa", "puntaje_eleccion"]
    for periodo in res["periodo"].unique():
        print(f"\n== {periodo}")
        print(res[res["periodo"] == periodo][ver].round(3).to_string(index=False))
    print(f"\nElegido (desarrollo): {NOMBRES[elegido]}; empatados dentro de 0,01: {candidatos}")
    print(f"En prueba: AUC {pru.loc[elegido, 'auc']:.3f} frente a {pru.loc['ref_calor', 'auc']:.3f} del índice de calor "
          f"(ventaja {ventaja_calor:+.3f}; {'supera' if ventaja_calor > 0.02 else 'NO supera'} el umbral de 0,02)")

    # Modelo final: el elegido, con todos los años (1981-2025)
    tr, _ = etiquetas(b, HASTA + 1)
    final, cal, p = ajustar(elegido, tr)
    MODELOS_DIR.mkdir(exist_ok=True)
    joblib.dump({"modelo": final, "calibrador": cal, "columnas": COLUMNAS}, MODELOS_DIR / "modelo_final.joblib")
    meta = {"modelo": NOMBRES[elegido], "clave": elegido, "hiperparametros": p, "entrenado_con": "Iowa, Illinois e Indiana, 1981-2025",
            "filas_entrenamiento": len(tr), "perdidas_entrenamiento": int(tr["y"].sum()), "calibrado": cal is not None,
            "variables": COLUMNAS, "etiqueta": "rendimiento del condado de 80 % o menos de su tendencia lineal",
            "como_predecir": "python scripts/48_predecir.py archivo.csv (columnas: las de 'variables')",
            "advertencia": "No probado todavía en los siete estados nuevos; las probabilidades necesitan recalibrarse con datos locales en otras zonas.",
            "eleccion": eleccion}
    (MODELOS_DIR / "modelo_final.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    print(f"\nModelo final guardado en modelos/modelo_final.joblib ({NOMBRES[elegido]}, {p}; calibrado: {cal is not None})")


if __name__ == "__main__":
    main()
