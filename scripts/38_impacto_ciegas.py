"""
38_impacto_ciegas.py
Fase 4 de la prueba a ciegas (plan congelado en docs/plan_prueba_ciegas.md): impacto económico en dólares de 2025 (CPI-U) para los
siete estados nuevos y para los diez estados juntos, con los mismos cálculos de 31_impacto_eeuu.py.

  1. Pérdida real: (esperado - observado) x área cosechada x precio nacional de la campaña, solo en condado-años con pérdida.
  2. Lo que pagó la RMA (maíz, todos los planes): indemnización total y por sequía, prima, subsidio real.
  3. Seguro simulado, 1991-2025, suma asegurada de 100 % (y 75 % como sensibilidad): modelo (prueba principal de 35, pago = suma x
     severidad prevista cuando se activa el corte aplicable), regla de lluvia (mismo pago) y contrato Palmer (pago proporcional).
  4. De cada $100 que llegan a quien perdió y su costo de administración. Seguro real: reembolso de A&O sobre la prima.
     Índice: costo de operar SUPUESTO, con varios niveles. NO se afirma que el índice reemplace al seguro real.

Requiere 34, 35 y 37. Salidas en datos/procesados/: ciegas_impacto_*.csv y ciegas_impacto_resumen.json
Uso:  python scripts/38_impacto_ciegas.py
"""
import importlib
import json
import sys
import warnings
import zipfile
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
import comun  # noqa: E402
e31 = importlib.import_module("31_impacto_eeuu")

PROCESADOS = RAIZ / "datos" / "procesados"
RMA = RAIZ / "datos" / "crudos" / "eeuu" / "rma"
SIGLAS = ["IA", "IL", "IN", "NE", "MN", "OH", "MO", "KS", "SD", "WI"]
ORIGINALES = {"17", "18", "19"}
SUMAS = [0.75, 1.00]
RECARGO = 0.30
COSTO_INDICE = [0.05, 0.10, 0.20]               # SUPUESTO: costo de operar el índice como fracción de la prima pura
AO_EJEMPLO_GAO = 0.185                          # GAO-17-501: "fixed percentage (e.g., 18.5 percent) of the premium"
AO_GAO_ANUAL_USD = 1.4e9                        # GAO-17-501: unos $1.400 millones al año de subsidio A&O, 2011-2015
PERIODO_AO = (2011, 2015)
PERIODO_SUBSIDIO = (2014, 2018)
GRUPOS = {"siete estados nuevos": lambda d: ~d["unidad"].str[:2].isin(ORIGINALES),
          "tres estados originales": lambda d: d["unidad"].str[:2].isin(ORIGINALES),
          "diez estados": lambda d: np.ones(len(d), dtype=bool)}


def prima_nacional(anios):
    """Prima total de todos los cultivos y estados (Summary of Business de la RMA), en dólares de cada año."""
    total = {}
    for a in anios:
        with zipfile.ZipFile(RMA / f"sobcov_{a}.zip") as z:
            d = pd.read_csv(z.open(z.namelist()[0]), sep="|", header=None, dtype=str, usecols=[21])
        total[a] = pd.to_numeric(d[21], errors="coerce").fillna(0).sum()
    return pd.Series(total)


def simular(d, columna_pago, suma, nombre):
    """Métricas de un disparador; columna_pago es la fracción de la suma asegurada que paga (0 a 1) en cada condado-año."""
    pago = d["valor_esperado_usd"] * suma * d[columna_pago]
    perdida = d["perdida_usd"]
    y = d["perdida"].astype(bool)
    total, bien = pago.sum(), pago[y].sum()
    anios = d["anio"].nunique()
    potencial = d["valor_esperado_usd"] * suma * d["severidad_prevista"]
    return {"disparador": nombre, "suma_asegurada": suma, "condado_anios": len(d), "anios": anios, "pagos": int((pago > 0).sum()),
            "pagos_usd": total, "pagos_a_perdida_usd": bien, "pagos_sin_perdida_usd": total - bien, "perdida_real_usd": perdida.sum(),
            "perdida_sin_pago_usd": perdida[pago <= 0].sum(),
            "pct_perdida_cubierta": 100 * np.minimum(pago, perdida).sum() / perdida.sum() if perdida.sum() else np.nan,
            "de_cada_100_pagados": 100 * bien / total if total else np.nan,
            "de_cada_100_al_azar": 100 * potencial[y].sum() / potencial.sum(),
            "prima_pura_anual_usd": total / anios,
            "tasa_prima_pura_pct": 100 * total / anios / (d["valor_esperado_usd"].sum() * suma / anios)}


def main():
    defl, precio, fase = e31.deflactor(), e31.precios(), e31.oni_verano()
    b = pd.read_csv(PROCESADOS / "eeuu_ciegas_base.csv", dtype={"unidad": str, "grupo": str})

    # 1. Pérdida real, diez estados
    r, por_anio, por_estado, por_fase = e31.perdida_real(b, precio, defl, fase)
    r["nuevo"] = ~r["unidad"].str[:2].isin(ORIGINALES)
    por_anio_grupo = r.groupby(["anio", "nuevo"])["perdida_usd"].sum().unstack(fill_value=0).rename(columns={False: "originales_usd", True: "nuevos_usd"})
    por_anio = por_anio.join(por_anio_grupo)
    por_anio.to_csv(PROCESADOS / "ciegas_impacto_perdida_por_anio.csv")
    por_estado.to_csv(PROCESADOS / "ciegas_impacto_perdida_por_estado.csv")
    por_fase.to_csv(PROCESADOS / "ciegas_impacto_perdida_por_fase.csv")
    print("Pérdida real por estado, 1988-2025 (dólares de 2025):\n" + por_estado.round(0).to_string())

    # 2. RMA de los diez estados
    comun.ESTADOS_RMA = SIGLAS
    s, nominal = e31.rma(defl)
    s["estado"] = s["unidad"].str[:2]
    s.to_csv(PROCESADOS / "ciegas_impacto_rma_condado_anio.csv", index=False)
    rma_anio = s.groupby("anio")[["responsabilidad", "prima_total", "subsidio", "prima_agricultor", "indemnizacion", "indemnizacion_sequia"]].sum()
    rma_anio.to_csv(PROCESADOS / "ciegas_impacto_rma_por_anio.csv")
    n = nominal[nominal["anio"].between(*PERIODO_SUBSIDIO)]
    nuevo_n = ~n["unidad"].str[:2].isin(ORIGINALES)
    subsidio = {"diez estados": n["subsidio"].sum() / n["prima_total"].sum(),
                "siete estados nuevos": n.loc[nuevo_n, "subsidio"].sum() / n.loc[nuevo_n, "prima_total"].sum(),
                "tres estados originales": n.loc[~nuevo_n, "subsidio"].sum() / n.loc[~nuevo_n, "prima_total"].sum()}
    print("Subsidio real de la RMA 2014-2018: " + ", ".join(f"{k} {v:.1%}" for k, v in subsidio.items()))

    # 3. Seguro simulado con el modelo de la prueba principal, la regla y el contrato Palmer
    pred = pd.read_csv(PROCESADOS / "ciegas_predicciones_principal.csv", dtype={"unidad": str, "grupo": str})
    pal = pd.read_csv(PROCESADOS / "ciegas_palmer_predicciones.csv", dtype={"unidad": str}, usecols=["unidad", "anio", "fraccion_palmer", "fraccion_lluvia", "conjunto"])
    pal = pal[pal["conjunto"] == "diez estados"].drop(columns="conjunto")
    d = pred.merge(pal, on=["unidad", "anio"], how="inner")                       # mismas filas para los tres índices
    d = e31.preparar(d.merge(b[["unidad", "anio", "rendimiento_bu_acre", "area_cosechada_acres"]], on=["unidad", "anio"]),
                     "esperado_previo_t_ha", "perdida_previa", precio, defl)
    d["f_modelo"] = d["severidad_prevista"] * d["pago_umbral"].astype(bool)
    d["f_regla"] = d["severidad_prevista"] * d["pago_regla"].astype(bool)
    d["f_palmer"] = d["fraccion_palmer"]
    d["f_regla_proporcional"] = d["fraccion_lluvia"]
    filas = []
    for periodo, desde in [("1991-2025", 1991), ("prueba 2019-2025", 2019)]:
        for grupo, sel in GRUPOS.items():
            g = d[sel(d) & (d["anio"] >= desde)]
            for suma in SUMAS:
                for col, nombre in [("f_modelo", "Modelo"), ("f_regla", "Regla de lluvia (pago por severidad)"),
                                    ("f_regla_proporcional", "Regla de lluvia (pago proporcional)"), ("f_palmer", "Contrato Palmer")]:
                    filas.append({"periodo": periodo, "grupo": grupo, **simular(g, col, suma, nombre)})
            # Lo que pagó la RMA en esos mismos condado-años
            m = g.merge(s, on=["unidad", "anio"], how="left")
            ind = m["indemnizacion"].fillna(0)
            filas.append({"periodo": periodo, "grupo": grupo, "disparador": "Seguro real (RMA, todas las causas)", "suma_asegurada": np.nan,
                          "condado_anios": len(g), "anios": g["anio"].nunique(), "pagos_usd": ind.sum(),
                          "pagos_a_perdida_usd": ind[m["perdida"]].sum(), "pagos_sin_perdida_usd": ind[~m["perdida"]].sum(),
                          "perdida_real_usd": g["perdida_usd"].sum(), "de_cada_100_pagados": 100 * ind[m["perdida"]].sum() / ind.sum(),
                          "indemnizacion_sequia_usd": m["indemnizacion_sequia"].fillna(0).sum(),
                          "prima_total_usd": m["prima_total"].fillna(0).sum(), "subsidio_usd": m["subsidio"].fillna(0).sum(),
                          "prima_agricultor_usd": m["prima_agricultor"].fillna(0).sum()})
    sim = pd.DataFrame(filas)

    # 4. Costo de operar. Real: reembolso A&O. Índice: SUPUESTO.
    prima = prima_nacional(range(PERIODO_AO[0], PERIODO_AO[1] + 1))
    ao_implicito = AO_GAO_ANUAL_USD * len(prima) / prima.sum()
    print(f"Prima total nacional (todos los cultivos) {PERIODO_AO[0]}-{PERIODO_AO[1]}: ${prima.sum() / 1e9:.1f} mil millones; "
          f"A&O de GAO ($1.400 millones al año) implica {ao_implicito:.1%} de la prima")
    niveles_ao = {"A&O implícito (GAO / prima nacional)": ao_implicito, "A&O ejemplo de la ley (GAO, 18,5 % de la prima)": AO_EJEMPLO_GAO}
    costos = []
    for (periodo, grupo), g in sim.groupby(["periodo", "grupo"]):
        real = g[g["disparador"].str.startswith("Seguro real")].iloc[0]
        for nombre_ao, ao in niveles_ao.items():
            costo = ao * real["prima_total_usd"]
            costos.append({"periodo": periodo, "grupo": grupo, "esquema": "Seguro real", "supuesto": nombre_ao, "nivel": ao,
                           "costo_operar_usd": costo, "llega_a_quien_perdio_usd": real["pagos_a_perdida_usd"],
                           "de_cada_100_llegan": real["de_cada_100_pagados"],
                           "costo_por_cada_100_que_llegan": 100 * costo / real["pagos_a_perdida_usd"],
                           "costo_por_cada_100_pagados": 100 * costo / real["pagos_usd"], "es_supuesto": False})
        for _, f in g[(g["suma_asegurada"] == 1.0) & g["disparador"].isin(["Modelo", "Contrato Palmer", "Regla de lluvia (pago proporcional)"])].iterrows():
            for nivel in COSTO_INDICE:
                costo = nivel * f["pagos_usd"]
                costos.append({"periodo": periodo, "grupo": grupo, "esquema": f["disparador"], "supuesto": "costo de operar el índice (SUPUESTO)",
                               "nivel": nivel, "costo_operar_usd": costo, "llega_a_quien_perdio_usd": f["pagos_a_perdida_usd"],
                               "de_cada_100_llegan": f["de_cada_100_pagados"],
                               "costo_por_cada_100_que_llegan": 100 * costo / f["pagos_a_perdida_usd"],
                               "costo_por_cada_100_pagados": 100 * costo / f["pagos_usd"], "es_supuesto": True})
    costos = pd.DataFrame(costos)

    # Por año (para la figura de dólares): diez estados
    gd = d[d["anio"] >= 1991]
    por_anio_sim = pd.DataFrame({
        "modelo_usd": (gd["valor_esperado_usd"] * gd["f_modelo"]).groupby(gd["anio"]).sum(),
        "palmer_usd": (gd["valor_esperado_usd"] * gd["f_palmer"]).groupby(gd["anio"]).sum(),
        "regla_usd": (gd["valor_esperado_usd"] * gd["f_regla_proporcional"]).groupby(gd["anio"]).sum()})
    por_anio_sim = por_anio_sim.join(rma_anio[["indemnizacion", "indemnizacion_sequia"]]).join(por_anio[["perdida_usd", "originales_usd", "nuevos_usd"]])
    por_anio_sim.to_csv(PROCESADOS / "ciegas_impacto_por_anio.csv")
    sim.to_csv(PROCESADOS / "ciegas_impacto_simulacion.csv", index=False)
    costos.to_csv(PROCESADOS / "ciegas_impacto_costos.csv", index=False)
    d.to_csv(PROCESADOS / "ciegas_impacto_detalle.csv", index=False)
    resumen = {"anio_dolares": 2025, "recargo": RECARGO, "subsidio_real_2014_2018": subsidio, "ao_implicito_gao": ao_implicito,
               "ao_ejemplo_gao": AO_EJEMPLO_GAO, "ao_gao_anual_usd": AO_GAO_ANUAL_USD, "prima_nacional_2011_2015_usd": float(prima.sum()),
               "costo_indice_supuestos": COSTO_INDICE,
               "perdida_total_1988_2025_usd": float(por_anio["perdida_usd"].sum()), "perdida_2012_usd": float(por_anio.loc[2012, "perdida_usd"])}
    (PROCESADOS / "ciegas_impacto_resumen.json").write_text(json.dumps(resumen, indent=1), encoding="utf-8")

    pd.set_option("display.width", 250, "display.max_columns", 40)
    cols = ["periodo", "grupo", "disparador", "suma_asegurada", "pagos", "pagos_usd", "pagos_sin_perdida_usd", "perdida_real_usd",
            "pct_perdida_cubierta", "de_cada_100_pagados", "de_cada_100_al_azar", "tasa_prima_pura_pct"]
    t = sim[cols].copy()
    for c in cols:
        if c.endswith("_usd"):
            t[c] = t[c] / 1e6
    print(t[t["suma_asegurada"].isna() | (t["suma_asegurada"] == 1.0)].round(2).to_string(index=False))
    print(costos[costos["periodo"] == "1991-2025"].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
