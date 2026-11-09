"""
36_semaforo_ciegas.py
Fase 3A de la prueba a ciegas (plan congelado en docs/plan_prueba_ciegas.md): el semáforo, ahora con pérdidas.

Regla del color (la de 30_semaforo_eeuu.py, congelada): dato bueno (al menos 25 años válidos, a lo sumo 5 % de repetidos, sin salto
de área), sensibilidad del rendimiento al estrés del verano con encogimiento de Bayes empírico por estado, y terciles.
  verde = dato bueno y tercil alto; rojo = dato malo o tercil bajo; amarillo = el resto.
Variante fijada: la misma regla, más rojo si el 25 % o más del maíz para grano cosechado tiene riego (censos anteriores al año).
  - Prueba 1 (hacia adelante): cada año t de 2006 a 2025 los colores se recalculan SOLO con años anteriores a t, en los diez estados.
  - Prueba 2 (geográfica): colores de los siete estados nuevos con sus años hasta 2018, evaluados en 2019-2025.
Por color: AUC, Heidke, % de pérdidas captadas y de cada $100 pagados cuántos llegan a quien perdió. Diferencia verde menos rojo con
intervalo de 95 % remuestreando años completos (1.000 veces). Criterio: Heidke, % captado y de cada $100 mayores en los verdes, con el
intervalo sin incluir el cero, con el modelo.

Requiere 34 y 35. Salidas en datos/procesados/: ciegas_semaforo_colores.csv, ciegas_semaforo_resultados.csv,
  ciegas_semaforo_diferencias.csv, ciegas_semaforo_criterio.json
Uso:  python scripts/36_semaforo_ciegas.py
"""
import importlib
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
import comun  # noqa: E402
e30 = importlib.import_module("30_semaforo_eeuu")
e31 = importlib.import_module("31_impacto_eeuu")

PROCESADOS = RAIZ / "datos" / "procesados"
ORIGINALES = {"17", "18", "19"}
PRIMER_ANIO_PRUEBA1 = 2006            # 1981 + 25 años de datos
RIEGO_ALTO = 0.25
N_REMUESTREO, SEMILLA = 1000, 2026
COLORES = ["verde", "amarillo", "rojo"]
SUMA = 1.0


def sensibilidad(b, hasta):
    """Igual que 30.sensibilidad, con tendencia, índice y pendientes calculados solo con años <= hasta."""
    b = b[b["anio"] <= hasta].copy()
    t = comun.tendencia(b[["unidad", "anio", "rendimiento_t_ha"]], hasta, e30.MIN_ANIOS_SENSIBILIDAD).rename(columns={"relativo": "rend_relativo"})
    b = b.drop(columns=["rend_relativo"], errors="ignore").merge(t[["unidad", "anio", "rend_relativo"]], on=["unidad", "anio"])   # tendencia con años <= hasta
    b["palmer_verano"] = b[["palmer_jun", "palmer_jul", "palmer_ago"]].mean(axis=1)
    b["tmax_verano"] = b[["tmax_jun", "tmax_jul", "tmax_ago"]].mean(axis=1)
    z = lambda s: (s - s.mean()) / s.std()
    g = b.groupby("unidad")
    b["indice"] = (g["lluvia_jun_ago_mm"].transform(z) + g["palmer_verano"].transform(z) - g["tmax_verano"].transform(z)) / 3
    filas = []
    for unidad, d in b.dropna(subset=["indice", "rend_relativo"]).groupby("unidad"):
        if len(d) < e30.MIN_ANIOS_SENSIBILIDAD:
            continue
        x, y = d["indice"].to_numpy(), d["rend_relativo"].clip(0, 3).to_numpy()
        xc = x - x.mean()
        if (xc ** 2).sum() == 0:
            continue
        pendiente = (xc * (y - y.mean())).sum() / (xc ** 2).sum()
        residuo = y - y.mean() - pendiente * xc
        se = np.sqrt((residuo ** 2).sum() / (len(y) - 2) / (xc ** 2).sum())
        filas.append({"unidad": unidad, "grupo": d["grupo"].iloc[0], "pendiente": pendiente, "se": se,
                      "var_indice": x.var(ddof=1), "var_relativo": y.var(ddof=1)})
    s = pd.DataFrame(filas)
    for _, idx in s.groupby("grupo").groups.items():
        p, se = s.loc[idx, "pendiente"], s.loc[idx, "se"]
        tau2 = max(0.0, p.var(ddof=1) - (se ** 2).mean()) if len(p) > 1 else 0.0
        peso = tau2 / (tau2 + se ** 2)
        s.loc[idx, "pendiente_encogida"] = peso * p + (1 - peso) * p.mean()
    s["sensibilidad"] = (s["pendiente_encogida"] ** 2 * s["var_indice"] / s["var_relativo"]).clip(0, 1)
    cortes = s["sensibilidad"].quantile([1 / 3, 2 / 3]).to_numpy()
    s["tercil"] = np.select([s["sensibilidad"] <= cortes[0], s["sensibilidad"] <= cortes[1]], ["bajo", "medio"], "alto")
    return s[["unidad", "tercil"]]


def calidad(q, hasta):
    """Dato bueno con la misma regla de 30.calidad, usando solo años <= hasta (también el salto de área)."""
    q = q[q["anio"] <= hasta]
    r = q.groupby("unidad").agg(anios_con_dato=("anio", "size"), pct_repetidos=("repetido", "mean"))
    r["anios_validos"] = q[~q["repetido"]].groupby("unidad").size().reindex(r.index).fillna(0).astype(int)
    r["salto"] = q.sort_values("anio").groupby("unidad")["area_cosechada_ha"].apply(comun.salto_de_nivel)
    r["dato_bueno"] = (r["anios_validos"] >= e30.MIN_ANIOS_BUENO) & (r["pct_repetidos"] <= e30.MAX_REPETIDOS_BUENO) & (r["salto"] < comun.SALTO_AREA_MAX)
    return r["dato_bueno"]


def riego_hasta(censos, hasta):
    c = censos[censos["anio_censo"] <= hasta]
    return c.groupby("unidad")["fraccion"].mean()


def colores(b, q, censos, hasta, unidades):
    """Colores de las unidades, con la regla base y con la variante de riego, usando solo años <= hasta."""
    bb = b[b["unidad"].isin(unidades)]
    s = sensibilidad(bb, hasta).set_index("unidad")["tercil"]
    bueno = calidad(q[q["unidad"].isin(unidades)], hasta)
    t = pd.DataFrame({"dato_bueno": bueno})
    t["tercil"] = s.reindex(t.index)
    t["riego"] = riego_hasta(censos, hasta).reindex(t.index)
    malo = ~t["dato_bueno"].fillna(False).astype(bool) | (t["tercil"] == "bajo")
    verde = t["dato_bueno"].fillna(False).astype(bool) & (t["tercil"] == "alto")
    t["color_base"] = np.select([malo, verde], ["rojo", "verde"], "amarillo")
    t["color_riego"] = np.where(t["riego"] >= RIEGO_ALTO, "rojo", t["color_base"])
    return t[["color_base", "color_riego", "riego"]].rename_axis("unidad").reset_index()


# ---------------------------------------------------------------- evaluación por color
def pagos_dolares(d):
    """Dinero que pagaría cada índice (suma 100 % x valor esperado x severidad prevista, cuando se activa)."""
    base = d["valor_esperado_usd"] * SUMA * d["severidad_prevista"]
    return {"modelo": base * d["pago_umbral"].astype(bool), "regla": base * d["pago_regla"].astype(bool)}


def heidke_de(a, b, c, dd):
    den = (a + c) * (c + dd) + (a + b) * (b + dd)
    return 2 * (a * dd - b * c) / den if den else np.nan


def estadisticos_por_anio(d):
    """Conteos por (índice, color, año) para calcular Heidke, % captado y dólares sumando años remuestreados."""
    d = d.copy()
    y = d["perdida_previa"].astype(bool)
    dol = pagos_dolares(d)
    filas = []
    for indice, pago in [("modelo", d["pago_modelo"].astype(bool)), ("regla", d["pago_regla"].astype(bool))]:
        x = pd.DataFrame({"anio": d["anio"], "color": d["color"], "a": (y & pago).astype(int), "b": (~y & pago).astype(int),
                          "c": (y & ~pago).astype(int), "dd": (~y & ~pago).astype(int),
                          "pago_usd": dol[indice], "pago_a_perdida_usd": dol[indice].where(y, 0.0)})
        filas.append(x.groupby(["color", "anio"]).sum().reset_index().assign(indice=indice))
    return pd.concat(filas, ignore_index=True)


def medidas(s):
    """Heidke, % de pérdidas captadas y de cada $100 pagados, a partir de la suma de conteos."""
    a, b, c, dd = s["a"].sum(), s["b"].sum(), s["c"].sum(), s["dd"].sum()
    return {"heidke": heidke_de(a, b, c, dd), "pct_perdidas_captadas": 100 * a / (a + c) if (a + c) else np.nan,
            "de_cada_100": 100 * s["pago_a_perdida_usd"].sum() / s["pago_usd"].sum() if s["pago_usd"].sum() else np.nan}


def probar(d, columna_color, prueba, variante, rng):
    """Métricas por color y diferencia verde - rojo con intervalo de 95 % remuestreando años."""
    d = d.assign(color=d[columna_color])
    est = estadisticos_por_anio(d)
    anios = sorted(d["anio"].unique())
    por_color, difs = [], []
    for indice, pun in [("modelo", "prob"), ("regla", "puntaje_regla")]:
        e = est[est["indice"] == indice]
        auc = {}
        for c in COLORES:
            g = d[d["color"] == c]
            m = medidas(e[e["color"] == c])
            auc[c] = roc_auc_score(g["perdida_previa"], g[pun]) if 0 < g["perdida_previa"].sum() < len(g) else np.nan
            por_color.append({"prueba": prueba, "variante": variante, "indice": indice, "color": c, "condados": g["unidad"].nunique(),
                              "filas": len(g), "perdidas": int(g["perdida_previa"].sum()),
                              "pct_perdida": 100 * g["perdida_previa"].mean() if len(g) else np.nan, "auc": auc[c], **m})
        # Remuestreo de años: sumar conteos y dólares de los años elegidos
        piezas = {(c, a): g for (c, a), g in e.groupby(["color", "anio"])}
        por_anio_d = {a: g for a, g in d.groupby("anio")}
        boot = {"heidke": [], "pct_perdidas_captadas": [], "de_cada_100": [], "auc": []}
        for _ in range(N_REMUESTREO):
            elegidos = rng.choice(anios, len(anios))
            res = {}
            for c in ["verde", "rojo"]:
                partes = [piezas[(c, a)] for a in elegidos if (c, a) in piezas]
                res[c] = medidas(pd.concat(partes)) if partes else {k: np.nan for k in ("heidke", "pct_perdidas_captadas", "de_cada_100")}
            for k in ("heidke", "pct_perdidas_captadas", "de_cada_100"):
                boot[k].append(res["verde"][k] - res["rojo"][k])
            m = pd.concat([por_anio_d[a] for a in elegidos], ignore_index=True)
            av = [m[m["color"] == c] for c in ("verde", "rojo")]
            if all(0 < g["perdida_previa"].sum() < len(g) for g in av):
                boot["auc"].append(roc_auc_score(av[0]["perdida_previa"], av[0][pun]) - roc_auc_score(av[1]["perdida_previa"], av[1][pun]))
        verde = next(r for r in por_color if r["indice"] == indice and r["color"] == "verde")
        rojo = next(r for r in por_color if r["indice"] == indice and r["color"] == "rojo")
        for k in ("heidke", "pct_perdidas_captadas", "de_cada_100", "auc"):
            lo, hi = np.nanpercentile(boot[k], [2.5, 97.5]) if len(boot[k]) > 20 else (np.nan, np.nan)
            v, r = verde[k], rojo[k]
            difs.append({"prueba": prueba, "variante": variante, "indice": indice, "metrica": k, "verde": v, "rojo": r,
                         "diferencia": v - r if pd.notna(v) and pd.notna(r) else np.nan, "ic_inf": lo, "ic_sup": hi,
                         "remuestreos_validos": len(boot[k])})
    return por_color, difs


def preparar_pagos(d, rng_semilla=SEMILLA):
    """Misma frecuencia de pago que la regla en el conjunto evaluado (como en 35), y valor esperado en dólares."""
    d = d.copy()
    d["pago_modelo"] = comun.pagar_igual_que_regla(d["prob"].to_numpy(), d["pago_regla"].mean())
    return d


def main():
    rng = np.random.default_rng(SEMILLA)
    b = pd.read_csv(PROCESADOS / "eeuu_ciegas_base.csv", dtype={"unidad": str, "grupo": str})
    q = pd.read_csv(PROCESADOS / "eeuu_ciegas_calidad_anual.csv", dtype={"unidad": str})
    censos = pd.read_csv(PROCESADOS / "eeuu_riego_censos.csv", dtype={"unidad": str})
    pred = pd.read_csv(PROCESADOS / "ciegas_predicciones_principal.csv", dtype={"unidad": str, "grupo": str})
    # Valor esperado en dólares de 2025 y pérdida (mismo cálculo de 31)
    defl, precio = e31.deflactor(), e31.precios()
    cb = b[["unidad", "anio", "rendimiento_bu_acre", "area_cosechada_acres"]]
    pred = e31.preparar(pred.merge(cb, on=["unidad", "anio"]), "esperado_previo_t_ha", "perdida_previa", precio, defl)
    todas = sorted(b["unidad"].unique())
    todas_nuevas = [u for u in todas if u[:2] not in ORIGINALES]

    # Prueba 1: colores recalculados cada año con años anteriores, diez estados
    partes, tablas = [], []
    for t in range(PRIMER_ANIO_PRUEBA1, int(pred["anio"].max()) + 1):
        col = colores(b, q, censos, t - 1, todas)
        tablas.append(col.assign(anio=t))
        partes.append(pred[pred["anio"] == t].merge(col, on="unidad", how="left"))
        print(f"  Prueba 1, año {t}: " + ", ".join(f"{c} {int((col['color_base'] == c).sum())}" for c in COLORES), flush=True)
    p1 = pd.concat(partes, ignore_index=True).dropna(subset=["color_base"])
    p1 = preparar_pagos(p1)
    pd.concat(tablas).to_csv(PROCESADOS / "ciegas_semaforo_colores_adelante.csv", index=False)

    # Prueba 2: colores de los estados nuevos con años hasta 2018, evaluados en 2019-2025
    col2 = colores(b, q, censos, 2018, todas_nuevas)
    col2.to_csv(PROCESADOS / "ciegas_semaforo_colores_2018.csv", index=False)
    p2 = pred[(pred["anio"] >= 2019) & pred["unidad"].isin(todas_nuevas)].merge(col2, on="unidad", how="left").dropna(subset=["color_base"])
    p2 = preparar_pagos(p2)
    print(f"Prueba 2: colores a 2018 {col2['color_base'].value_counts().to_dict()}; {len(p2):,} condado-años en 2019-2025")

    por_color, difs = [], []
    for prueba, d in [("prueba 1: hacia adelante, 10 estados", p1), ("prueba 2: nuevos hasta 2018 y 2019-2025", p2),
                      ("prueba 1 solo estados nuevos", p1[~p1["grupo"].isin(ORIGINALES)])]:
        for variante, columna in [("regla base", "color_base"), ("base y rojo si hay riego", "color_riego")]:
            pc, df = probar(d, columna, prueba, variante, rng)
            por_color += pc
            difs += df
    pc, df = pd.DataFrame(por_color), pd.DataFrame(difs)
    pc.to_csv(PROCESADOS / "ciegas_semaforo_resultados.csv", index=False)
    df.to_csv(PROCESADOS / "ciegas_semaforo_diferencias.csv", index=False)

    # Criterio con el modelo: tres métricas con diferencia positiva e intervalo sin cero
    crit = {}
    for (prueba, variante), g in df[df["indice"] == "modelo"].groupby(["prueba", "variante"]):
        g = g.set_index("metrica")
        ok = {k: bool(g.loc[k, "diferencia"] > 0 and g.loc[k, "ic_inf"] > 0) for k in ("heidke", "pct_perdidas_captadas", "de_cada_100")}
        crit[f"{prueba} | {variante}"] = {**ok, "cumple": bool(all(ok.values()))}
    (PROCESADOS / "ciegas_semaforo_criterio.json").write_text(json.dumps(crit, indent=1, ensure_ascii=False), encoding="utf-8")

    pd.set_option("display.width", 250, "display.max_columns", 30)
    print(pc[pc["indice"] == "modelo"].round(3).to_string(index=False))
    print(df.round(3).to_string(index=False))
    print(json.dumps(crit, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
