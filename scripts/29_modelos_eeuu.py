"""
29_modelos_eeuu.py
Fase 1 del seguro de sequía para el maíz de EE. UU.: modelos de probabilidad y de severidad de la pérdida
(plan en docs/bitacora.md, 2026-11-04).

  1. Partición fija por años (1981-2011, 2012-2018, 2019-2025): regla, solo ubicación, regresión logística,
     bosque aleatorio y LightGBM. Hiperparámetros por AUC en validación; calibración isotónica ajustada en validación.
  2. Validación hacia adelante 1991-2025 (medida principal): cada año t, la tendencia, la pérdida, los
     hiperparámetros y la calibración salen solo de años anteriores a t.
  3. Aporte de cada grupo de variables (ubicación, lluvia, temperatura, sequía de Palmer y riego).
  4. Severidad (cuánto se queda corto el rendimiento cuando hay pérdida) y pérdida esperada.
  5. SHAP del mejor modelo y registro en MLflow.
Valores p barajando años completos; intervalos de 95 % por remuestreo de años; con y sin 1988 y 2012.

Requiere 28. Tarda cerca de 40 minutos.
Salidas en datos/procesados/: eeuu_sequia_*.csv y eeuu_sequia_mejor.json
Uso:  python scripts/29_modelos_eeuu.py
"""
import json
import os
import sys
import warnings
from pathlib import Path

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
warnings.filterwarnings("ignore")

import lightgbm as lgb
import mlflow
import numpy as np
import pandas as pd
import shap
from scipy.stats import spearmanr
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss, roc_auc_score

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
import comun  # noqa: E402

PROCESADOS = RAIZ / "datos" / "procesados"
URI_MLFLOW = f"sqlite:///{(RAIZ / 'mlflow.db').as_posix()}"
EXPERIMENTO = "seguro_sequia_maiz_eeuu"
REGISTRO = "perdida_maiz_eeuu"

SEMILLA = 2026
N_AZAR = 1000
DESDE = 1991                     # primer año de la validación hacia adelante
ANIOS_AJUSTE = 3                 # años previos a t para hiperparámetros y calibración
MIN_ANIOS = 8
PERCENTIL_REGLA = 0.15           # regla calibrada: junio a agosto, percentil 15
MIN_ANIOS_REGLA = 10
ANIOS_EXTREMOS = [1988, 2012]
PARAMS_SEVERIDAD = {"n_estimators": 200, "learning_rate": 0.03, "num_leaves": 7, "min_child_samples": 20,
                    "random_state": SEMILLA, "verbose": -1, "n_jobs": -1}
MUESTRA_SHAP = 3000

UBICACION = ["latitud", "longitud"]
GRUPOS = {"lluvia": ["lluvia_may", "lluvia_jun", "lluvia_jul", "lluvia_ago", "lluvia_sep", "racha_meses_secos", "deficit_jul_ago"],
          "temperatura": ["tmax_jun", "tmax_jul", "tmax_ago"],
          "sequia": ["palmer_jun", "palmer_jul", "palmer_ago"]}
# El riego entra solo si hay dato: los censos de NASS no se pudieron bajar (docs/bitacora.md, 2026-11-04)
if (PROCESADOS / "eeuu_sequia_base.csv").exists() and \
        pd.read_csv(PROCESADOS / "eeuu_sequia_base.csv", usecols=["fraccion_riego"])["fraccion_riego"].notna().any():
    GRUPOS["riego"] = ["fraccion_riego"]
CONJUNTOS = {"solo_ubicacion": [], **{f"ubicacion_y_{g}": [g] for g in GRUPOS}, "todas": list(GRUPOS),
             **{f"todas_sin_{g}": [x for x in GRUPOS if x != g] for g in GRUPOS}}
MODELOS = {"solo_ubicacion": ("lightgbm", "solo_ubicacion"), "regresion_logistica": ("regresion_logistica", "todas"),
           "bosque_aleatorio": ("bosque_aleatorio", "todas"), "lightgbm": ("lightgbm", "todas")}


def numericas(conjunto):
    return UBICACION + [v for g in CONJUNTOS[conjunto] for v in GRUPOS[g]]


def crear(nombre, parametros, conjunto):
    return comun.crear(nombre, parametros, numericas(conjunto), ["grupo"])


def columnas(conjunto):
    return numericas(conjunto) + ["grupo"]


# ---------------------------------------------------------------- datos
def cargar():
    b = pd.read_csv(PROCESADOS / "eeuu_sequia_base.csv", dtype={"unidad": str, "grupo": str})
    b["perdida"] = b["perdida"].astype(bool)
    return b


def lluvia_verano():
    """Lluvia de junio a agosto de todos los años con lluvia, también los años sin dato de cosecha."""
    m = pd.read_csv(PROCESADOS / "chirps_mensual_condados_eeuu.csv", dtype={"fips": str})
    m = m[m["mes"].isin([6, 7, 8]) & (m["anio"] <= 2025)]
    v = m.groupby(["fips", "anio"]).agg(mm=("lluvia_mm", "sum"), n=("mes", "size")).reset_index()
    return v[v["n"] == 3].rename(columns={"fips": "unidad"})[["unidad", "anio", "mm"]]


def regla(lluvia, unidades_anio, hasta):
    """Paga si la lluvia de junio a agosto queda bajo el percentil 15 del condado, calculado con años <= hasta."""
    h = lluvia[lluvia["anio"] <= hasta].groupby("unidad")["mm"]
    u = pd.DataFrame({"umbral_regla_mm": h.quantile(PERCENTIL_REGLA), "normal_jun_ago_mm": h.mean(), "n": h.size()})
    u = u[u["n"] >= MIN_ANIOS_REGLA]
    r = unidades_anio.merge(lluvia, on=["unidad", "anio"], how="left").merge(u, left_on="unidad", right_index=True, how="left")
    r["pago_regla"] = (r["mm"] < r["umbral_regla_mm"]).fillna(False)
    r["puntaje_regla"] = -(r["mm"] / r["normal_jun_ago_mm"])
    return r[["unidad", "anio", "pago_regla", "puntaje_regla", "umbral_regla_mm"]]


def etiquetas_previas(b, t):
    """Pérdida previa de cada condado con la tendencia de los años anteriores; además guarda el rendimiento relativo y el esperado."""
    previos = b[b["anio"] < t]
    tend = comun.tendencia(previos, None, MIN_ANIOS)
    tend["perdida_previa"] = tend["relativo"] <= comun.UMBRAL_PERDIDA
    tend["faltante_previo"] = (1 - tend["relativo"].clip(0, 3)).clip(lower=0)
    tr = previos.merge(tend[["unidad", "anio", "perdida_previa", "faltante_previo"]], on=["unidad", "anio"])
    ajuste = []
    for unidad, d in previos.groupby("unidad"):
        if len(d) >= MIN_ANIOS:
            pendiente, intercepto = np.polyfit(d["anio"], d["rendimiento_t_ha"], 1)
            ajuste.append((unidad, intercepto + pendiente * t))
    pr = b[b["anio"] == t].merge(pd.DataFrame(ajuste, columns=["unidad", "esperado_previo_t_ha"]), on="unidad")
    pr = pr[pr["esperado_previo_t_ha"] > 0].copy()
    relativo = pr["rendimiento_t_ha"] / pr["esperado_previo_t_ha"]
    pr["perdida_previa"] = relativo <= comun.UMBRAL_PERDIDA
    pr["faltante_previo"] = (1 - relativo.clip(0, 3)).clip(lower=0)
    return tr, pr


# ---------------------------------------------------------------- métricas
def p_anios(d, y, puntaje, metrica, rng):
    """Valor p barajando años completos: las pérdidas de un año se mueven juntas a otro año."""
    yy = d.pivot(index="unidad", columns="anio", values=y).astype(float).to_numpy()
    pp = d.pivot(index="unidad", columns="anio", values=puntaje).astype(float).to_numpy()

    def valor(orden):
        z = yy[:, orden]
        m = ~np.isnan(z) & ~np.isnan(pp)
        return metrica(z[m].astype(bool), pp[m])

    observado = valor(np.arange(yy.shape[1]))
    mayores = sum(valor(rng.permutation(yy.shape[1])) >= observado for _ in range(N_AZAR))
    return (mayores + 1) / (N_AZAR + 1)


def heidke_metrica(y, pago):
    return comun.heidke(y, pago.astype(bool))


def remuestreo(d, y, puntaje, pago, rng):
    """Intervalos de 95 % remuestreando años completos, con reposición."""
    grupos = {a: g for a, g in d.groupby("anio")}
    anios = list(grupos)
    aucs, heidkes, captadas = [], [], []
    for _ in range(N_AZAR):
        m = pd.concat([grupos[a] for a in rng.choice(anios, len(anios))], ignore_index=True)
        yy, pg = m[y].to_numpy().astype(bool), m[pago].to_numpy().astype(bool)
        if 0 < yy.sum() < len(yy):
            aucs.append(roc_auc_score(yy, m[puntaje]))
        heidkes.append(comun.heidke(yy, pg))
        captadas.append(100 * (yy & pg).sum() / max(yy.sum(), 1))
    q = lambda x: np.nanpercentile(x, [2.5, 97.5]) if len(x) else [np.nan, np.nan]
    (a1, a2), (h1, h2), (c1, c2) = q(aucs), q(heidkes), q(captadas)
    return {"auc_ic_inf": a1, "auc_ic_sup": a2, "heidke_ic_inf": h1, "heidke_ic_sup": h2, "captadas_ic_inf": c1, "captadas_ic_sup": c2}


def medir(d, y, puntaje, pago, prob=None, cal=None, rng=None, completo=True):
    yy, pg = d[y].to_numpy().astype(bool), d[pago].to_numpy().astype(bool)
    aciertos = int((yy & pg).sum())
    r = {"filas": len(d), "anios": d["anio"].nunique(), "perdidas": int(yy.sum()), "pagos": int(pg.sum()),
         "auc": roc_auc_score(yy, d[puntaje]) if 0 < yy.sum() < len(yy) else np.nan,
         "pct_perdidas_captadas": 100 * aciertos / max(yy.sum(), 1),
         "pct_alertas_sin_perdida": 100 * (pg.sum() - aciertos) / max(pg.sum(), 1),
         "heidke": comun.heidke(yy, pg), "aciertos": aciertos, "aciertos_azar": pg.sum() * yy.sum() / len(d),
         "brier": brier_score_loss(yy, d[prob]) if prob else np.nan,
         "brier_calibrado": brier_score_loss(yy, d[cal]) if cal else np.nan,
         "brier_tasa": brier_score_loss(yy, np.full(len(yy), yy.mean()))}
    if completo:
        r["p_auc_anios"] = p_anios(d, y, puntaje, roc_auc_score, rng)
        r["p_heidke_anios"] = p_anios(d.assign(_pago=d[pago].astype(float)), y, "_pago", heidke_metrica, rng)
        r.update(remuestreo(d, y, puntaje, pago, rng))
    return r


def igual_que_regla(d, puntaje):
    """El modelo paga en tantos condado-años como la regla en todo el periodo evaluado.
    No se iguala año por año: así el modelo heredaría de la regla cuáles años fueron secos."""
    return comun.pagar_igual_que_regla(d[puntaje].to_numpy(), d["pago_regla"].mean())


# ---------------------------------------------------------------- ajuste
def escoger(nombre, conjunto, viejos, recientes, y):
    """Hiperparámetros por AUC en los años recientes; devuelve también la probabilidad en esos años.
    Si en los años recientes no hubo ninguna pérdida (2021-2023), no se puede escoger: queda la primera
    opción de la rejilla, fijada de antemano."""
    mejor, mejor_auc, guardado = comun.REJILLAS[nombre][0], -1.0, None
    if recientes[y].nunique() < 2:
        m = crear(nombre, mejor, conjunto).fit(viejos[columnas(conjunto)], viejos[y])
        return mejor, np.nan, m.predict_proba(recientes[columnas(conjunto)])[:, 1]
    for parametros in comun.REJILLAS[nombre]:
        m = crear(nombre, parametros, conjunto).fit(viejos[columnas(conjunto)], viejos[y])
        prob = m.predict_proba(recientes[columnas(conjunto)])[:, 1]
        auc = roc_auc_score(recientes[y], prob)
        if auc > mejor_auc:
            mejor, mejor_auc, guardado = parametros, auc, prob
    return mejor, mejor_auc, guardado


def hacia_adelante(b, lluvia, nombre, conjunto, excluir=(), con_severidad=False):
    partes = []
    for t in range(DESDE, int(b["anio"].max()) + 1):
        if t in excluir:
            continue
        tr, pr = etiquetas_previas(b, t)
        tr = tr[~tr["anio"].isin(excluir)]
        anios = sorted(tr["anio"].unique())
        corte = anios[-ANIOS_AJUSTE]
        viejos, recientes = tr[tr["anio"] < corte], tr[tr["anio"] >= corte]
        if pr.empty or viejos["perdida_previa"].nunique() < 2:
            continue
        parametros, _, prob_rec = escoger(nombre, conjunto, viejos, recientes, "perdida_previa")
        final = crear(nombre, parametros, conjunto).fit(tr[columnas(conjunto)], tr["perdida_previa"])
        r = pr[["unidad", "anio", "perdida", "perdida_previa", "faltante_previo", "esperado_previo_t_ha"]].copy()
        r["prob"] = final.predict_proba(pr[columnas(conjunto)])[:, 1]
        r["calibrado"] = recientes["perdida_previa"].nunique() == 2
        if r["calibrado"].iloc[0]:
            iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(prob_rec, recientes["perdida_previa"])
            r["prob_calibrada"] = iso.predict(r["prob"])
        else:
            r["prob_calibrada"] = r["prob"]          # sin pérdidas recientes no hay con qué calibrar
        r["tasa_historica"] = tr["perdida_previa"].mean()
        # Corte aplicable: la probabilidad que en los 3 años previos paga con la misma frecuencia que la regla
        rr = regla(lluvia, recientes[["unidad", "anio"]], t - 1)
        frecuencia = rr["pago_regla"].mean()
        r["umbral_prob"] = np.quantile(prob_rec, 1 - frecuencia) if frecuencia > 0 else np.inf
        r["pago_umbral"] = r["prob"] >= r["umbral_prob"]
        r = r.merge(regla(lluvia, r[["unidad", "anio"]], t - 1), on=["unidad", "anio"], how="left")
        if con_severidad:
            perd = tr[tr["perdida_previa"]]
            sev = lgb.LGBMRegressor(**PARAMS_SEVERIDAD).fit(perd[numericas(conjunto)], perd["faltante_previo"])
            r["severidad_prevista"] = np.clip(sev.predict(pr[numericas(conjunto)]), 0, 1)
            r["severidad_media_previa"] = perd["faltante_previo"].mean()
        partes.append(r)
    d = pd.concat(partes, ignore_index=True)
    d["pago_regla"] = d["pago_regla"].fillna(False).astype(bool)
    d["pago_igual_regla"] = igual_que_regla(d, "prob")
    return d


def particion_fija(b, lluvia, nombre, conjunto, excluir=()):
    """Entrena con 1981-2011, escoge y calibra con 2012-2018, reentrena con ambos y predice 2019-2025."""
    tr = b[(b["grupo_tiempo"] == "entrenamiento") & ~b["anio"].isin(excluir)]
    va = b[(b["grupo_tiempo"] == "validacion") & ~b["anio"].isin(excluir)]
    pr = b[b["grupo_tiempo"] == "prueba"].copy()
    parametros, auc_val, prob_val = escoger(nombre, conjunto, tr, va, "perdida")
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(prob_val, va["perdida"])
    final = crear(nombre, parametros, conjunto).fit(pd.concat([tr, va])[columnas(conjunto)], pd.concat([tr, va])["perdida"])
    reg_val = regla(lluvia, va[["unidad", "anio"]], tr["anio"].max())
    umbral = np.quantile(prob_val, 1 - reg_val["pago_regla"].mean())
    pr["prob"] = final.predict_proba(pr[columnas(conjunto)])[:, 1]
    pr["prob_calibrada"] = iso.predict(pr["prob"])
    pr["umbral_prob"] = umbral
    pr["pago_umbral"] = pr["prob"] >= umbral
    pr = pr.merge(regla(lluvia, pr[["unidad", "anio"]], tr["anio"].max()), on=["unidad", "anio"], how="left")
    pr["pago_regla"] = pr["pago_regla"].fillna(False).astype(bool)
    pr["pago_igual_regla"] = igual_que_regla(pr, "prob")
    return pr, parametros, auc_val, final, iso


# ---------------------------------------------------------------- explicación
def explicar(pipe, x, conjunto):
    prep, final = pipe[0], pipe[-1]
    z = pd.DataFrame(prep.transform(x), columns=numericas(conjunto) + list(prep.named_transformers_["cat"].get_feature_names_out(["grupo"])))
    if isinstance(final, lgb.LGBMClassifier) or hasattr(final, "estimators_"):
        valores = shap.TreeExplainer(final).shap_values(z)
    else:
        valores = shap.LinearExplainer(final, z).shap_values(z)
    valores = np.asarray(valores[1] if isinstance(valores, list) else valores)
    if valores.ndim == 3:
        valores = valores[:, :, 1]
    filas = []
    for i, v in enumerate(z.columns):
        original = z[v].to_numpy()
        if v.startswith("lluvia_"):
            adverso = original < 100            # mes más seco que lo normal
        elif v.startswith("tmax_"):
            adverso = original > 0              # más caliente que lo normal
        elif v.startswith("palmer_"):
            adverso = original < 0              # más seco que lo normal
        else:
            adverso = np.zeros(len(original), dtype=bool)
        grupo = next((g for g, vs in GRUPOS.items() if v in vs), "ubicacion")
        filas.append({"variable": v, "grupo": grupo, "shap_medio_absoluto": float(np.abs(valores[:, i]).mean()),
                      "shap_si_adverso": float(valores[adverso, i].mean()) if adverso.any() else np.nan,
                      "shap_si_favorable": float(valores[~adverso, i].mean()) if (~adverso).any() and adverso.any() else np.nan})
    imp = pd.DataFrame(filas).sort_values("shap_medio_absoluto", ascending=False)
    return imp


def curva_calibracion(d, cal, y, nombre):
    d = d.assign(decil=pd.qcut(d[cal].rank(method="first"), 10, labels=False))
    c = d.groupby("decil").agg(prob_media=(cal, "mean"), perdida_observada=(y, "mean"), filas=(y, "size")).reset_index()
    return c.assign(esquema=nombre)


def registrar(nombre, conjunto, parametros, metricas, pipe=None, ejemplo=None):
    with mlflow.start_run(run_name=f"eeuu_sequia|{nombre}") as corrida:
        mlflow.set_tags({"cultivo": "maiz", "pais": "eeuu", "modelo": nombre, "conjunto": conjunto})
        mlflow.log_params({"modelo": nombre, "conjunto": conjunto, **{f"hiper_{k}": v for k, v in parametros.items()}})
        mlflow.log_metrics({k: float(v) for k, v in metricas.items() if isinstance(v, (int, float, np.floating)) and pd.notna(v)})
        if pipe is not None:
            mlflow.sklearn.log_model(pipe, name="modelo", input_example=ejemplo, registered_model_name=REGISTRO,
                                     pip_requirements=["scikit-learn", "lightgbm", "pandas", "numpy"], serialization_format="cloudpickle")
        return corrida.info.run_id


# ---------------------------------------------------------------- corrida
def main():
    b = cargar()
    lluvia = lluvia_verano()
    rng = np.random.default_rng(SEMILLA)
    mlflow.set_tracking_uri(URI_MLFLOW)
    if mlflow.get_experiment_by_name(EXPERIMENTO) is None:
        mlflow.create_experiment(EXPERIMENTO, artifact_location=(RAIZ / "mlruns").as_uri())
    mlflow.set_experiment(EXPERIMENTO)
    filas = []

    # 1. Partición fija
    fijos = {}
    pr0 = None
    for clave, (nombre, conjunto) in MODELOS.items():
        pr, parametros, auc_val, pipe, iso = particion_fija(b, lluvia, nombre, conjunto)
        fijos[clave] = (pr, parametros, auc_val, pipe, iso, nombre, conjunto)
        m = medir(pr, "perdida", "prob", "pago_igual_regla", "prob", "prob_calibrada", rng)
        filas.append({"esquema": "particion_fija", "modelo": clave, "conjunto": conjunto, "auc_validacion": auc_val,
                      "parametros": json.dumps(parametros), **m})
        print(f"fija {clave}: AUC validación {auc_val:.3f}, prueba {m['auc']:.3f}, Heidke {m['heidke']:.3f}", flush=True)
        pr0 = pr if pr0 is None else pr0
    m = medir(pr0, "perdida", "puntaje_regla", "pago_regla", rng=rng)
    filas.insert(0, {"esquema": "particion_fija", "modelo": "regla", "conjunto": "lluvia de junio a agosto, p15", **m})
    registrar("regla", "lluvia_jun_ago_p15", {"percentil": PERCENTIL_REGLA}, m)

    candidatos = ["regresion_logistica", "bosque_aleatorio", "lightgbm"]
    mejor = max(candidatos, key=lambda k: fijos[k][2])
    pr, parametros, auc_val, pipe, iso, nombre, conjunto = fijos[mejor]
    print(f"Mejor modelo por validación: {mejor} (AUC {auc_val:.3f})", flush=True)
    for clave in MODELOS:
        f = fijos[clave]
        met = next(x for x in filas if x["esquema"] == "particion_fija" and x["modelo"] == clave)
        registrar(clave, f[6], f[1], {k: v for k, v in met.items() if k not in ("esquema", "modelo", "conjunto", "parametros")},
                  f[3] if clave == mejor else None, b[columnas(f[6])].head(3) if clave == mejor else None)

    # Variante de la partición fija sin 1988 ni 2012 en entrenamiento y validación
    sp, *_ = particion_fija(b, lluvia, nombre, conjunto, excluir=ANIOS_EXTREMOS)
    filas.append({"esquema": "particion_fija_sin_1988_2012", "modelo": mejor, "conjunto": conjunto,
                  **medir(sp, "perdida", "prob", "pago_igual_regla", "prob", "prob_calibrada", rng)})

    # Severidad en la partición fija
    entr = b[b["grupo_tiempo"] != "prueba"]
    perd = entr[entr["perdida"]]
    sev = lgb.LGBMRegressor(**PARAMS_SEVERIDAD).fit(perd[numericas(conjunto)], perd["faltante"])
    pr["severidad_prevista"] = np.clip(sev.predict(pr[numericas(conjunto)]), 0, 1)
    pr["severidad_media_previa"] = perd["faltante"].mean()
    pr["tasa_historica"] = entr["perdida"].mean()

    # 2. Validación hacia adelante: los cinco modelos, la regla y las variantes del mejor
    adelante = {}
    for clave, (nom, conj) in MODELOS.items():
        adelante[clave] = hacia_adelante(b, lluvia, nom, conj, con_severidad=(clave == mejor))
        d = adelante[clave]
        m = medir(d, "perdida_previa", "prob", "pago_igual_regla", "prob", "prob_calibrada", rng)
        filas.append({"esquema": "hacia_adelante", "modelo": clave, "conjunto": conj, **m})
        print(f"adelante {clave}: AUC {m['auc']:.3f}, Heidke {m['heidke']:.3f}", flush=True)
    d = adelante[mejor]
    filas.append({"esquema": "hacia_adelante", "modelo": "regla", "conjunto": "lluvia de junio a agosto, p15",
                  **medir(d, "perdida_previa", "puntaje_regla", "pago_regla", rng=rng)})
    for clave in ["regla", mejor]:
        sin = d[d["anio"] != 2012]
        pun, pag = ("puntaje_regla", "pago_regla") if clave == "regla" else ("prob", "pago_igual_regla")
        filas.append({"esquema": "hacia_adelante_sin_2012_en_evaluacion", "modelo": clave, "conjunto": conjunto,
                      **medir(sin, "perdida_previa", pun, pag, "prob" if clave != "regla" else None, "prob_calibrada" if clave != "regla" else None, rng)})
    sin_ext = hacia_adelante(b, lluvia, nombre, conjunto, excluir=ANIOS_EXTREMOS)
    filas.append({"esquema": "hacia_adelante_sin_1988_2012", "modelo": mejor, "conjunto": conjunto,
                  **medir(sin_ext, "perdida_previa", "prob", "pago_igual_regla", "prob", "prob_calibrada", rng)})
    filas.append({"esquema": "hacia_adelante_sin_1988_2012", "modelo": "regla", "conjunto": "lluvia de junio a agosto, p15",
                  **medir(sin_ext, "perdida_previa", "puntaje_regla", "pago_regla", rng=rng)})
    resultados = pd.DataFrame(filas)
    resultados.to_csv(PROCESADOS / "eeuu_sequia_resultados.csv", index=False)

    # 3. Aporte de cada grupo de variables, con LightGBM y regresión logística
    aporte = []
    for nom in ["lightgbm", "regresion_logistica"]:
        for conj in CONJUNTOS:
            dd = adelante["lightgbm"] if (nom, conj) == ("lightgbm", "todas") else \
                adelante["regresion_logistica"] if (nom, conj) == ("regresion_logistica", "todas") else \
                adelante["solo_ubicacion"] if (nom, conj) == ("lightgbm", "solo_ubicacion") else hacia_adelante(b, lluvia, nom, conj)
            sin = dd[dd["anio"] != 2012]
            aporte.append({"modelo": nom, "conjunto": conj, "auc": roc_auc_score(dd["perdida_previa"], dd["prob"]),
                           "auc_sin_2012": roc_auc_score(sin["perdida_previa"], sin["prob"]),
                           "brier_calibrado": brier_score_loss(dd["perdida_previa"], dd["prob_calibrada"]),
                           "p_auc_anios": p_anios(dd, "perdida_previa", "prob", roc_auc_score, rng),
                           **{k: v for k, v in remuestreo(dd, "perdida_previa", "prob", "pago_igual_regla", rng).items() if k.startswith("auc")}})
            print(f"aporte {nom} {conj}: AUC {aporte[-1]['auc']:.3f}", flush=True)
    aporte = pd.DataFrame(aporte)
    aporte.to_csv(PROCESADOS / "eeuu_sequia_aporte.csv", index=False)

    # 4. Severidad y pérdida esperada (hacia adelante)
    d = adelante[mejor]
    d["perdida_esperada"] = d["prob_calibrada"] * d["severidad_prevista"]
    d["perdida_esperada_base"] = d["tasa_historica"] * d["severidad_media_previa"]
    d["faltante_real"] = d["faltante_previo"].where(d["perdida_previa"], 0.0)
    perd = d[d["perdida_previa"]]
    pr["perdida_esperada"] = pr["prob_calibrada"] * pr["severidad_prevista"]
    pr["faltante_real"] = pr["faltante"].where(pr["perdida"], 0.0)
    pp = pr[pr["perdida"]]
    sev_t = pd.DataFrame([
        {"esquema": "hacia_adelante", "pérdidas": len(perd),
         "mae_severidad_modelo": (perd["severidad_prevista"] - perd["faltante_previo"]).abs().mean(),
         "mae_severidad_media_previa": (perd["severidad_media_previa"] - perd["faltante_previo"]).abs().mean(),
         "spearman_severidad": spearmanr(perd["severidad_prevista"], perd["faltante_previo"])[0],
         "mae_perdida_esperada": (d["perdida_esperada"] - d["faltante_real"]).abs().mean(),
         "mae_perdida_esperada_base": (d["perdida_esperada_base"] - d["faltante_real"]).abs().mean(),
         "spearman_perdida_esperada": spearmanr(d["perdida_esperada"], d["faltante_real"])[0]},
        {"esquema": "particion_fija", "pérdidas": len(pp),
         "mae_severidad_modelo": (pp["severidad_prevista"] - pp["faltante"]).abs().mean(),
         "mae_severidad_media_previa": (pp["severidad_media_previa"] - pp["faltante"]).abs().mean(),
         "spearman_severidad": spearmanr(pp["severidad_prevista"], pp["faltante"])[0] if len(pp) > 2 else np.nan,
         "mae_perdida_esperada": (pr["perdida_esperada"] - pr["faltante_real"]).abs().mean(),
         "mae_perdida_esperada_base": ((pr["tasa_historica"] * pr["severidad_media_previa"]) - pr["faltante_real"]).abs().mean(),
         "spearman_perdida_esperada": spearmanr(pr["perdida_esperada"], pr["faltante_real"])[0]}])
    sev_t.to_csv(PROCESADOS / "eeuu_sequia_severidad.csv", index=False)
    print(sev_t.round(3).T.to_string(), flush=True)

    # Calibración y probabilidad según la lluvia
    cal = pd.concat([curva_calibracion(d, "prob_calibrada", "perdida_previa", "hacia_adelante"),
                     curva_calibracion(pr, "prob_calibrada", "perdida", "particion_fija")])
    cal.to_csv(PROCESADOS / "eeuu_sequia_calibracion.csv", index=False)

    # 5. SHAP del mejor modelo de la partición fija, en validación y prueba
    muestra = b[b["grupo_tiempo"] != "entrenamiento"].sample(min(MUESTRA_SHAP, (b["grupo_tiempo"] != "entrenamiento").sum()), random_state=SEMILLA)
    imp = explicar(pipe, muestra[columnas(conjunto)], conjunto)
    imp.to_csv(PROCESADOS / "eeuu_sequia_shap.csv", index=False)
    print(imp.head(15).round(4).to_string(index=False), flush=True)

    # Predicciones para el semáforo, el impacto y el simulador
    adelante["solo_ubicacion"][["unidad", "anio", "prob"]].rename(columns={"prob": "prob_ubicacion"}).merge(
        d, on=["unidad", "anio"]).to_csv(PROCESADOS / "eeuu_sequia_predicciones_adelante.csv", index=False)
    pr.to_csv(PROCESADOS / "eeuu_sequia_predicciones_fija.csv", index=False)

    cliente = mlflow.MlflowClient()
    versiones = sorted(cliente.search_model_versions(f"name='{REGISTRO}'"), key=lambda v: int(v.version))
    version = versiones[-1].version if versiones else None
    if version:
        cliente.set_registered_model_alias(REGISTRO, "mejor_en_validacion", version)
    (PROCESADOS / "eeuu_sequia_mejor.json").write_text(json.dumps(
        {"modelo": mejor, "conjunto": conjunto, "parametros": parametros, "auc_validacion": auc_val,
         "umbral_prob_validacion": float(pr["umbral_prob"].iloc[0]), "version_registro": version}, indent=1), encoding="utf-8")
    print(resultados[["esquema", "modelo", "auc", "auc_ic_inf", "auc_ic_sup", "heidke", "heidke_ic_inf", "heidke_ic_sup",
                      "pct_perdidas_captadas", "pct_alertas_sin_perdida", "brier", "brier_calibrado", "brier_tasa",
                      "p_auc_anios", "p_heidke_anios"]].round(3).to_string(index=False))
    print(aporte.round(3).to_string(index=False))
    print("Listo: eeuu_sequia_*.csv")


if __name__ == "__main__":
    main()
