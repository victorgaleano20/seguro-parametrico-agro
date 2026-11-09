"""
31_impacto_eeuu.py
Fase 3 del seguro de sequía para el maíz de EE. UU.: impacto económico en dólares de 2025
(plan en docs/bitacora.md, 2026-11-04).

  1. Pérdida real: (rendimiento esperado - observado) x área cosechada x precio, por año, estado y fase del clima.
  2. Lo que pagó el sistema real (RMA): indemnización, prima, subsidio y prima del agricultor, y la parte por sequía.
  3. Seguro paramétrico simulado con la regla y con el modelo: pagos mal dirigidos, pérdida sin pago,
     pérdida cubierta y de cada $100 cuántos llegan a quien perdió, también por color del semáforo.
  4. Prima pura, con recargo (SUPUESTO) y subsidio con el porcentaje real de la RMA.
  5. Sensibilidad a la suma asegurada, el recargo y el subsidio.
Precios: ERS (nacionales, por campaña). Dólares de 2025 con el CPI-U del BLS.

Requiere 28, 29 y 30. Salidas: datos/procesados/eeuu_impacto_*.csv y eeuu_impacto_resumen.json
Uso:  python scripts/31_impacto_eeuu.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
import comun  # noqa: E402

CRUDOS = RAIZ / "datos" / "crudos" / "eeuu"
PROCESADOS = RAIZ / "datos" / "procesados"

ANIO_DOLARES = 2025
MIN_ANIOS_PERDIDA = 7            # para que 1988 tenga rendimiento esperado (1981-1987)
SUMAS = [0.75, 1.00]             # SUPUESTO: suma asegurada como fracción del valor esperado
RECARGO = 0.30                   # SUPUESTO
RECARGOS = [0.0, 0.30, 0.50]
PERIODO_SUBSIDIO = (2014, 2018)  # porcentaje real de subsidio: últimos 5 años antes del corte
CAUSA_SEQUIA = "11"
UMBRAL_ONI = 0.5


def deflactor():
    c = pd.read_csv(CRUDOS / "precios" / "cpi_u_bls.csv")
    anual = c.groupby("anio")["cpi_u"].mean()
    return anual.loc[ANIO_DOLARES] / anual


def precios():
    """Precio promedio recibido por los agricultores por campaña (ERS, dato de NASS), en dólares por bushel."""
    p = pd.read_csv(CRUDOS / "precios" / "ers_feed_grains_yearbook.csv", low_memory=False)
    # Campaña de septiembre a agosto: el año 2012 es la campaña 2012/13, la de la cosecha de 2012
    p = p[(p["commodity"] == "Corn") & (p["attribute"] == "Price received by farmers") & (p["frequency"] == "Annual")
          & (p["geography"] == "United States") & p["table_name"].str.startswith("Table 1-")]
    p["anio"] = p["year"].astype(int)
    return p.groupby("anio")["amount"].mean().rename("precio_bu")


def oni_verano():
    oni = comun.leer_oni()
    v = {a: oni.reindex([a * 12 + 5, a * 12 + 6, a * 12 + 7]).mean() for a in range(1981, ANIO_DOLARES + 1)}
    s = pd.Series(v, name="oni_jun_ago")
    return pd.DataFrame({"oni_jun_ago": s, "fase_clima": comun.fase_oni(s.to_numpy())})


def perdida_real(b, precio, defl, fase):
    """Faltante en bushels con la tendencia de años anteriores, valorado al precio de la campaña."""
    filas = []
    for t in range(1988, int(b["anio"].max()) + 1):
        previos = b[b["anio"] < t]
        for unidad, d in previos.groupby("unidad"):
            if len(d) < MIN_ANIOS_PERDIDA:
                continue
            pendiente, intercepto = np.polyfit(d["anio"], d["rendimiento_bu_acre"], 1)
            filas.append((unidad, t, intercepto + pendiente * t))
    e = pd.DataFrame(filas, columns=["unidad", "anio", "esperado_bu_acre"])
    r = b.merge(e, on=["unidad", "anio"])
    r = r[r["esperado_bu_acre"] > 0].copy()
    r["perdida"] = r["rendimiento_bu_acre"] / r["esperado_bu_acre"] <= comun.UMBRAL_PERDIDA
    r["precio_bu"] = r["anio"].map(precio)
    r["perdida_usd"] = ((r["esperado_bu_acre"] - r["rendimiento_bu_acre"]) * r["area_cosechada_acres"] * r["precio_bu"]
                        * r["anio"].map(defl)).where(r["perdida"], 0.0)
    r = r.merge(fase, left_on="anio", right_index=True, how="left")
    por_anio = r.groupby("anio").agg(condados=("unidad", "size"), condados_con_perdida=("perdida", "sum"),
                                     perdida_usd=("perdida_usd", "sum"), fase_clima=("fase_clima", "first"),
                                     oni_jun_ago=("oni_jun_ago", "first"), precio_bu=("precio_bu", "first"))
    por_estado = r.groupby(["nombre_grupo"]).agg(perdida_usd=("perdida_usd", "sum"), condado_anios_con_perdida=("perdida", "sum"))
    por_fase = r.groupby("fase_clima").agg(anios=("anio", "nunique"), perdida_usd=("perdida_usd", "sum"),
                                           pct_condado_anios_con_perdida=("perdida", "mean"))
    por_fase["perdida_media_por_anio_usd"] = por_fase["perdida_usd"] / por_fase["anios"]
    return r, por_anio, por_estado, por_fase


def rma(defl):
    sob = comun.leer_rma("sobcov", {0: "anio", 1: "cod_estado", 2: "estado", 3: "cod_condado", 5: "cultivo", 20: "responsabilidad",
                                  21: "prima_total", 22: "subsidio", 23: "subsidio_estatal", 24: "subsidio_adicional",
                                  25: "descuento_efa", 26: "indemnizacion"})
    col = comun.leer_rma("colsom", {0: "anio", 1: "cod_estado", 2: "estado", 3: "cod_condado", 5: "cultivo", 11: "causa", 28: "indemnizacion"})
    numeros = ["responsabilidad", "prima_total", "subsidio", "subsidio_estatal", "subsidio_adicional", "descuento_efa", "indemnizacion"]
    sob[numeros] = sob[numeros].apply(pd.to_numeric, errors="coerce").fillna(0)
    col["indemnizacion"] = pd.to_numeric(col["indemnizacion"], errors="coerce").fillna(0)
    s = sob.groupby(["fips", "anio"])[numeros].sum()
    s["prima_agricultor"] = s["prima_total"] - s["subsidio"] - s["subsidio_estatal"] - s["subsidio_adicional"] - s["descuento_efa"]
    s["indemnizacion_sequia"] = col[col["causa"] == CAUSA_SEQUIA].groupby(["fips", "anio"])["indemnizacion"].sum()
    s["indemnizacion_causas"] = col.groupby(["fips", "anio"])["indemnizacion"].sum()
    s = s.fillna({"indemnizacion_sequia": 0, "indemnizacion_causas": 0}).reset_index().rename(columns={"fips": "unidad"})
    s["estado"] = s["unidad"].str[:2].map({"17": "IL", "18": "IN", "19": "IA"})
    nominal = s.copy()
    for c in numeros + ["prima_agricultor", "indemnizacion_sequia", "indemnizacion_causas"]:
        s[c] = s[c] * s["anio"].map(defl)
    return s, nominal


def simular(d, suma, recargo, subsidio, prefijo=""):
    """d trae valor_esperado_usd, perdida_usd, severidad_prevista, perdida y los disparadores."""
    filas = []
    for nombre, col in [("Regla", "pago_regla"), ("Modelo", "pago_umbral")]:
        paga = d[col].astype(bool)
        pago = d["valor_esperado_usd"] * suma * d["severidad_prevista"] * paga
        perdida = d["perdida_usd"]
        bien = pago[d["perdida"]].sum()
        total = pago.sum()
        potencial = d["valor_esperado_usd"] * suma * d["severidad_prevista"]
        anios = d["anio"].nunique()
        prima_pura = total / anios
        prima = prima_pura * (1 + recargo)
        filas.append({"disparador": nombre, "suma_asegurada": suma, "recargo": recargo, "subsidio": subsidio,
                      "condado_anios": len(d), "anios": anios, "pagos": int(paga.sum()),
                      "pagos_usd": total, "pagos_a_perdida_usd": bien, "pagos_sin_perdida_usd": total - bien,
                      "perdida_real_usd": perdida.sum(), "perdida_sin_pago_usd": perdida[~paga].sum(),
                      "pct_perdida_cubierta": 100 * np.minimum(pago, perdida).sum() / perdida.sum() if perdida.sum() else np.nan,
                      "de_cada_100_pagados": 100 * bien / total if total else np.nan,
                      "de_cada_100_al_azar": 100 * potencial[d["perdida"]].sum() / potencial.sum(),
                      "de_cada_100_subsidio": 100 * bien / total / (1 + recargo) if total else np.nan,
                      "prima_pura_anual_usd": prima_pura, "prima_con_recargo_anual_usd": prima,
                      "subsidio_anual_usd": prima * subsidio, "prima_agricultor_anual_usd": prima * (1 - subsidio),
                      "tasa_prima_pura_pct": 100 * prima_pura / (d["valor_esperado_usd"].sum() * suma / anios)})
    return filas


def preparar(d, esperado_t_ha, perdida, precio, defl):
    d = d.copy()
    d["perdida"] = d[perdida].astype(bool)
    d["esperado_bu_acre"] = d[esperado_t_ha] / comun.BU_ACRE_A_T_HA
    d["precio_bu"] = d["anio"].map(precio)
    factor = d["anio"].map(defl)
    d["valor_esperado_usd"] = d["esperado_bu_acre"] * d["area_cosechada_acres"] * d["precio_bu"] * factor
    d["perdida_usd"] = ((d["esperado_bu_acre"] - d["rendimiento_bu_acre"]).clip(lower=0) * d["area_cosechada_acres"]
                        * d["precio_bu"] * factor).where(d["perdida"], 0.0)
    return d


def main():
    defl, precio, fase = deflactor(), precios(), oni_verano()
    print(f"Precio por campaña (ERS), {precio.index.min()}-{precio.index.max()}; 2012: ${precio.loc[2012]:.2f}/bu; 2025: ${precio.get(2025, np.nan):.2f}/bu")
    b = pd.read_csv(PROCESADOS / "eeuu_sequia_base.csv", dtype={"unidad": str, "grupo": str})
    color = pd.read_csv(PROCESADOS / "semaforo_condados.csv", dtype={"unidad": str}).set_index("unidad")["color"]

    # 1. Pérdida real
    r, por_anio, por_estado, por_fase = perdida_real(b, precio, defl, fase)
    por_anio.to_csv(PROCESADOS / "eeuu_impacto_perdida_por_anio.csv")
    por_estado.to_csv(PROCESADOS / "eeuu_impacto_perdida_por_estado.csv")
    por_fase.to_csv(PROCESADOS / "eeuu_impacto_perdida_por_fase.csv")
    print(por_anio.loc[[1988, 2012]].to_string())
    print(por_fase.round(3).to_string())

    # 2. Sistema real (RMA)
    s, nominal = rma(defl)
    s.to_csv(PROCESADOS / "eeuu_impacto_rma_condado_anio.csv", index=False)
    rma_anio = s.groupby("anio")[["responsabilidad", "prima_total", "subsidio", "prima_agricultor", "indemnizacion",
                                   "indemnizacion_sequia", "indemnizacion_causas"]].sum()
    rma_anio = rma_anio.join(por_anio[["perdida_usd"]], how="left")
    rma_anio.to_csv(PROCESADOS / "eeuu_impacto_rma_por_anio.csv")
    n = nominal[nominal["anio"].between(*PERIODO_SUBSIDIO)]
    subsidio_real = n["subsidio"].sum() / n["prima_total"].sum()
    n2 = nominal[nominal["anio"] >= 2019]
    subsidio_reciente = n2["subsidio"].sum() / n2["prima_total"].sum()
    print(f"Subsidio real de la RMA (maíz, IA-IL-IN): {subsidio_real:.1%} en {PERIODO_SUBSIDIO[0]}-{PERIODO_SUBSIDIO[1]}; "
          f"{subsidio_reciente:.1%} en 2019-2025")

    # 3. Seguro simulado: prueba 2019-2025 (partición fija) y periodo ampliado (hacia adelante)
    columnas_base = b[["unidad", "anio", "rendimiento_bu_acre", "area_cosechada_acres", "nombre_grupo"]]
    fija = pd.read_csv(PROCESADOS / "eeuu_sequia_predicciones_fija.csv", dtype={"unidad": str})
    fija = preparar(fija.drop(columns=["rendimiento_bu_acre", "area_cosechada_acres", "nombre_grupo"], errors="ignore").merge(
        columnas_base, on=["unidad", "anio"]), "rend_esperado_t_ha", "perdida", precio, defl)
    adel = pd.read_csv(PROCESADOS / "eeuu_sequia_predicciones_adelante.csv", dtype={"unidad": str}).merge(columnas_base, on=["unidad", "anio"])
    adel = preparar(adel, "esperado_previo_t_ha", "perdida_previa", precio, defl)
    filas = []
    for periodo, d in [("prueba 2019-2025", fija), ("hacia adelante 1991-2025", adel)]:
        d = d.assign(color=d["unidad"].map(color))
        for suma in SUMAS:
            for f in simular(d, suma, RECARGO, subsidio_real):
                filas.append({"periodo": periodo, "grupo": "todos", **f})
            if suma == SUMAS[-1]:
                for c in ["verde", "amarillo", "rojo"]:
                    g = d[d["color"] == c]
                    if len(g):
                        for f in simular(g, suma, RECARGO, subsidio_real):
                            filas.append({"periodo": periodo, "grupo": c, **f})
        # Lo que pagó la RMA en esos mismos condado-años
        m = d.merge(s, on=["unidad", "anio"], how="left")
        filas.append({"periodo": periodo, "grupo": "todos", "disparador": "RMA real (todas las causas)",
                      "condado_anios": len(d), "anios": d["anio"].nunique(), "pagos_usd": m["indemnizacion"].sum(),
                      "pagos_a_perdida_usd": m.loc[m["perdida"], "indemnizacion"].sum(),
                      "pagos_sin_perdida_usd": m.loc[~m["perdida"], "indemnizacion"].sum(),
                      "perdida_real_usd": d["perdida_usd"].sum(),
                      "de_cada_100_pagados": 100 * m.loc[m["perdida"], "indemnizacion"].sum() / m["indemnizacion"].sum(),
                      "indemnizacion_sequia_usd": m["indemnizacion_sequia"].sum(), "prima_total_usd": m["prima_total"].sum(),
                      "subsidio_usd": m["subsidio"].sum(), "prima_agricultor_usd": m["prima_agricultor"].sum()})
    sim = pd.DataFrame(filas)
    sim.to_csv(PROCESADOS / "eeuu_impacto_simulacion.csv", index=False)

    # 5. Sensibilidad en la prueba
    sens = []
    for suma in SUMAS:
        for recargo in RECARGOS:
            for subsidio in [0.0, subsidio_real, 1.0]:
                sens += simular(fija, suma, recargo, subsidio)
    pd.DataFrame(sens).to_csv(PROCESADOS / "eeuu_impacto_sensibilidad.csv", index=False)

    adel.to_csv(PROCESADOS / "eeuu_impacto_simulacion_detalle.csv", index=False)
    resumen = {"anio_dolares": ANIO_DOLARES, "subsidio_real": subsidio_real, "subsidio_2019_2025": subsidio_reciente,
               "periodo_subsidio": list(PERIODO_SUBSIDIO), "recargo": RECARGO,
               "perdida_1988_usd": float(por_anio.loc[1988, "perdida_usd"]), "perdida_2012_usd": float(por_anio.loc[2012, "perdida_usd"])}
    (PROCESADOS / "eeuu_impacto_resumen.json").write_text(json.dumps(resumen, indent=1), encoding="utf-8")
    pd.set_option("display.width", 250, "display.max_columns", 40)
    cols = ["periodo", "grupo", "disparador", "suma_asegurada", "pagos", "pagos_usd", "pagos_sin_perdida_usd", "perdida_real_usd",
            "perdida_sin_pago_usd", "pct_perdida_cubierta", "de_cada_100_pagados", "de_cada_100_al_azar", "de_cada_100_subsidio",
            "prima_pura_anual_usd", "tasa_prima_pura_pct"]
    print((sim[cols].assign(**{c: sim[c] / 1e6 for c in cols if c.endswith("_usd")})).round(2).to_string(index=False))
    print("Listo: eeuu_impacto_*.csv (dólares en millones en la tabla de arriba)")


if __name__ == "__main__":
    main()
