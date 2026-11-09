"""
30_semaforo_eeuu.py
Fase 2 del seguro de sequía para el maíz de EE. UU.: semáforo de condados (plan en docs/bitacora.md, 2026-11-04).

Con años <= 2018 solamente:
  1. Calidad del dato: años válidos, cifras repetidas y salto de área.
  2. Sensibilidad al clima del verano, con pendientes por condado encogidas hacia la media del estado (Bayes empírico).
  3. Riego: fracción del maíz para grano cosechado con riego.
  4. Color con reglas fijadas de antemano.
Prueba con 2019-2025: AUC, Heidke y % de pérdidas captadas por color, con intervalos por remuestreo de años.

Requiere 28 y 29. Salidas: datos/procesados/semaforo_condados.csv y eeuu_semaforo_prueba.csv
Uso:  python scripts/30_semaforo_eeuu.py
"""
import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
import comun  # noqa: E402
e28 = importlib.import_module("28_base_eeuu")

PROCESADOS = RAIZ / "datos" / "procesados"
CORTE = 2018
MIN_ANIOS_BUENO, MAX_REPETIDOS_BUENO = 25, 0.05
MIN_ANIOS_SENSIBILIDAD = 10
RIEGO_POCO, RIEGO_ALTO = 0.10, 0.25
SEMILLA, N_AZAR = 2026, 1000
COLORES = ["verde", "amarillo", "rojo"]


def calidad():
    d = pd.read_csv(PROCESADOS / "eeuu_base_ciclos.csv", dtype={"fips": str})
    d = d[d["con_dato"].astype(bool) & (d["anio"] <= CORTE)]
    q = d.groupby("fips").agg(estado=("state_alpha", "first"), condado=("county_name", "first"),
                              anios_con_dato=("anio", "size"), pct_repetidos=("repetido", "mean"),
                              salto_area=("excluido_salto_area", "first"))
    q["anios_validos"] = d[~d["repetido"].astype(bool)].groupby("fips").size().reindex(q.index).fillna(0).astype(int)
    q["dato_bueno"] = (q["anios_validos"] >= MIN_ANIOS_BUENO) & (q["pct_repetidos"] <= MAX_REPETIDOS_BUENO) & ~q["salto_area"].astype(bool)
    return q.rename_axis("unidad").reset_index()


def sensibilidad():
    b = pd.read_csv(PROCESADOS / "eeuu_sequia_base.csv", dtype={"unidad": str, "grupo": str})
    b = b[b["anio"] <= CORTE].copy()
    b["palmer_verano"] = b[["palmer_jun", "palmer_jul", "palmer_ago"]].mean(axis=1)
    b["tmax_verano"] = b[["tmax_jun", "tmax_jul", "tmax_ago"]].mean(axis=1)
    z = lambda s: (s - s.mean()) / s.std()
    g = b.groupby("unidad")
    # Índice de estrés: más alto = verano más húmedo, con menos sequía y más fresco
    b["indice"] = (g["lluvia_jun_ago_mm"].transform(z) + g["palmer_verano"].transform(z) - g["tmax_verano"].transform(z)) / 3
    filas = []
    for unidad, d in b.dropna(subset=["indice"]).groupby("unidad"):
        if len(d) < MIN_ANIOS_SENSIBILIDAD:
            continue
        x, y = d["indice"].to_numpy(), d["rend_relativo"].clip(0, 3).to_numpy()
        xc = x - x.mean()
        pendiente = (xc * (y - y.mean())).sum() / (xc ** 2).sum()
        residuo = y - y.mean() - pendiente * xc
        se = np.sqrt((residuo ** 2).sum() / (len(y) - 2) / (xc ** 2).sum())
        filas.append({"unidad": unidad, "grupo": d["grupo"].iloc[0], "anios_sensibilidad": len(d), "pendiente": pendiente,
                      "se": se, "var_indice": x.var(ddof=1), "var_relativo": y.var(ddof=1)})
    s = pd.DataFrame(filas)
    # Encogimiento hacia la media del estado: un condado con pocas pérdidas no se mide bien solo
    for _, idx in s.groupby("grupo").groups.items():
        p, se = s.loc[idx, "pendiente"], s.loc[idx, "se"]
        tau2 = max(0.0, p.var(ddof=1) - (se ** 2).mean())
        peso = tau2 / (tau2 + se ** 2)
        s.loc[idx, "peso_condado"] = peso
        s.loc[idx, "pendiente_encogida"] = peso * p + (1 - peso) * p.mean()
    s["sensibilidad"] = (s["pendiente_encogida"] ** 2 * s["var_indice"] / s["var_relativo"]).clip(0, 1)
    cortes = s["sensibilidad"].quantile([1 / 3, 2 / 3]).to_numpy()
    s["tercil_sensibilidad"] = np.select([s["sensibilidad"] <= cortes[0], s["sensibilidad"] <= cortes[1]], ["bajo", "medio"], "alto")
    print(f"Sensibilidad: cortes de terciles {cortes.round(3)}; peso medio del condado frente al estado {s['peso_condado'].mean():.2f}")
    return s.drop(columns="grupo"), cortes


def semaforo():
    s, cortes = sensibilidad()
    t = calidad().merge(s, on="unidad", how="left").merge(e28.riego(), on="unidad", how="left")
    # Sin ningún dato de riego (no se pudo bajar el censo), la condición de riego no se aplica y se declara
    hay_riego = t["fraccion_riego"].notna().any()
    poco_riego = (t["fraccion_riego"] < RIEGO_POCO) if hay_riego else True
    rojo = ~t["dato_bueno"] | (t["tercil_sensibilidad"] == "bajo") | (t["fraccion_riego"] >= RIEGO_ALTO)
    verde = t["dato_bueno"] & (t["tercil_sensibilidad"] == "alto") & poco_riego
    if not hay_riego:
        print("Semáforo sin la condición de riego: no hay dato de riego")
    t["color"] = np.select([rojo, verde], ["rojo", "verde"], "amarillo")
    razon = []
    for f in t.itertuples():
        r = []
        if not f.dato_bueno:
            r.append("dato insuficiente o dudoso")
        if f.tercil_sensibilidad == "bajo":
            r.append("el rendimiento responde poco al clima del verano")
        if pd.notna(f.fraccion_riego) and f.fraccion_riego >= RIEGO_ALTO:
            r.append("mucho riego")
        if f.color == "verde":
            r = ["dato bueno y responde mucho al clima del verano" + (" y casi sin riego" if hay_riego else "")]
        if f.color == "amarillo" and not r:
            r = ["sensibilidad media, riego intermedio o información incompleta"]
        razon.append("; ".join(r))
    t["razon"] = razon
    ubic = pd.read_csv(PROCESADOS / "eeuu_sequia_base.csv", dtype={"unidad": str}).groupby("unidad")[["latitud", "longitud"]].first()
    t = t.merge(ubic, left_on="unidad", right_index=True, how="left")
    t.to_csv(PROCESADOS / "semaforo_condados.csv", index=False)
    print(t["color"].value_counts().to_string())
    print(pd.crosstab(t["estado"], t["color"]).to_string())
    return t


def metricas_color(d, pun, pag):
    y = d["y"].to_numpy().astype(bool)
    return {"auc": roc_auc_score(y, d[pun]) if 0 < y.sum() < len(y) else np.nan,
            "heidke": comun.heidke(y, d[pag].to_numpy().astype(bool)),
            "pct_perdidas_captadas": 100 * (y & d[pag].to_numpy().astype(bool)).sum() / max(y.sum(), 1)}


def probar(t):
    rng = np.random.default_rng(SEMILLA)
    color = t.set_index("unidad")["color"]
    fija = pd.read_csv(PROCESADOS / "eeuu_sequia_predicciones_fija.csv", dtype={"unidad": str}).rename(columns={"perdida": "y"})
    adel = pd.read_csv(PROCESADOS / "eeuu_sequia_predicciones_adelante.csv", dtype={"unidad": str})
    adel = adel[adel["anio"] > CORTE].rename(columns={"perdida_previa": "y"})
    filas, diferencias = [], []
    for esquema, d in [("particion_fija", fija), ("hacia_adelante", adel)]:
        d = d.assign(color=d["unidad"].map(color))
        for indice, pun, pag in [("modelo", "prob", "pago_igual_regla"), ("regla", "puntaje_regla", "pago_regla")]:
            for c in COLORES:
                g = d[d["color"] == c]
                if g.empty:
                    continue
                filas.append({"esquema": esquema, "indice": indice, "color": c, "condados": g["unidad"].nunique(), "filas": len(g),
                              "perdidas": int(g["y"].sum()), "pct_perdida": 100 * g["y"].mean(), **metricas_color(g, pun, pag)})
            # Diferencia verde - rojo, remuestreando años completos
            anios = sorted(d["anio"].unique())
            por_anio = {a: g for a, g in d.groupby("anio")}
            dif = {"auc": [], "heidke": [], "pct_perdidas_captadas": []}
            for _ in range(N_AZAR):
                m = pd.concat([por_anio[a] for a in rng.choice(anios, len(anios))], ignore_index=True)
                v, r = m[m["color"] == "verde"], m[m["color"] == "rojo"]
                if v.empty or r.empty:
                    continue
                mv, mr = metricas_color(v, pun, pag), metricas_color(r, pun, pag)
                for k in dif:
                    dif[k].append(mv[k] - mr[k])
            v, r = d[d["color"] == "verde"], d[d["color"] == "rojo"]
            mv, mr = metricas_color(v, pun, pag), metricas_color(r, pun, pag)
            for k, valores in dif.items():
                lo, hi = np.nanpercentile(valores, [2.5, 97.5]) if valores else (np.nan, np.nan)
                diferencias.append({"esquema": esquema, "indice": indice, "metrica": k, "verde": mv[k], "rojo": mr[k],
                                    "diferencia": mv[k] - mr[k], "ic_inf": lo, "ic_sup": hi})
    p = pd.DataFrame(filas)
    dif = pd.DataFrame(diferencias)
    pd.concat([p.assign(tabla="por_color"), dif.assign(tabla="verde_menos_rojo")]).to_csv(PROCESADOS / "eeuu_semaforo_prueba.csv", index=False)
    print(p.round(3).to_string(index=False))
    print(dif.round(3).to_string(index=False))
    m = dif[(dif["esquema"] == "particion_fija") & (dif["indice"] == "modelo")].set_index("metrica")
    se_sostiene = bool(m.loc["auc", "ic_inf"] > 0 and m.loc["heidke", "diferencia"] > 0)
    print(f"El semáforo se sostiene en 2019-2025 (criterio fijado): {se_sostiene}")
    return se_sostiene


def main():
    t = semaforo()
    se_sostiene = probar(t)
    (PROCESADOS / "eeuu_semaforo_resultado.txt").write_text(f"se_sostiene={se_sostiene}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
