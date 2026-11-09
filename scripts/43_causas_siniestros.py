"""
43_causas_siniestros.py
Fase 4A del cierre (plan congelado en docs/plan_cierre.md): causas de los siniestros del maíz por estado y diagnóstico de Minnesota.

Fuente: Cause of Loss de la RMA (colsom_*.zip), maíz (0041), 1989-2025, diez estados, indemnización en dólares de 2025 (CPI-U).
Grupos de causa fijados en el plan: sequía (11), exceso de humedad (31 y 51), heladas o frío (41 a 45), granizo (21), precio (01) y otras.
Descriptivo: no se afirman causas que los datos no muestren.
Minnesota se compara con los demás estados y con los años de falla del modelo (años con al menos 10 % de condados con pérdida en que
el modelo captó menos de la mitad de las pérdidas).

Requiere 35. Salidas en datos/procesados/: cierre_causas_condado_anio.csv, cierre_causas_por_estado.csv, cierre_causas_detalle.csv,
  cierre_causas_minnesota_anios.csv, cierre_causas_minnesota_resumen.csv
Uso:  python scripts/43_causas_siniestros.py
"""
import importlib
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
e31 = importlib.import_module("31_impacto_eeuu")

PROCESADOS = RAIZ / "datos" / "procesados"
RMA = RAIZ / "datos" / "crudos" / "eeuu" / "rma"
ESTADOS = {"17": "Illinois", "18": "Indiana", "19": "Iowa", "31": "Nebraska", "27": "Minnesota", "39": "Ohio", "29": "Missouri",
           "20": "Kansas", "46": "South Dakota", "55": "Wisconsin"}
GRUPOS_CAUSA = {"11": "sequia", "31": "humedad", "51": "humedad", "41": "frio", "42": "frio", "43": "frio", "44": "frio", "45": "frio",
                "21": "granizo", "01": "precio"}
ORDEN = ["sequia", "humedad", "frio", "granizo", "precio", "otras"]
ETIQUETAS = {"sequia": "Sequía", "humedad": "Exceso de humedad", "frio": "Heladas o frío", "granizo": "Granizo", "precio": "Caída de precio",
             "otras": "Otras"}
PERDIDA_MINIMA, CAPTADO_MINIMO = 0.10, 0.50


def leer_causas(defl):
    """Indemnización de maíz por condado, año y causa, en dólares de 2025."""
    partes = []
    for archivo in sorted(RMA.glob("colsom_*.zip")):
        with zipfile.ZipFile(archivo) as z:
            d = pd.read_csv(z.open(z.namelist()[0]), sep="|", header=None, dtype=str, usecols=[0, 1, 3, 5, 11, 12, 28])
        d = d.apply(lambda s: s.str.strip())
        d = d[d[1].isin(ESTADOS) & (d[5] == "0041")]
        partes.append(d)
    d = pd.concat(partes, ignore_index=True)
    d.columns = ["anio", "cod_estado", "cod_condado", "cultivo", "causa", "causa_nombre", "indemnizacion"]
    d["unidad"] = d["cod_estado"].str.zfill(2) + d["cod_condado"].str.zfill(3)
    d["anio"] = d["anio"].astype(int)
    d["indemnizacion_usd"] = pd.to_numeric(d["indemnizacion"], errors="coerce").fillna(0) * d["anio"].map(defl)
    d["grupo_causa"] = d["causa"].map(GRUPOS_CAUSA).fillna("otras")
    return d


def partes_por(d, claves):
    """Dólares y parte de cada grupo de causa dentro de las claves dadas."""
    t = d.pivot_table(index=claves, columns="grupo_causa", values="indemnizacion_usd", aggfunc="sum", fill_value=0.0)
    t = t.reindex(columns=ORDEN, fill_value=0.0)
    t["total_usd"] = t[ORDEN].sum(axis=1)
    for g in ORDEN:
        t[f"parte_{g}"] = t[g] / t["total_usd"].replace(0, np.nan)
    return t


def main():
    defl = e31.deflactor()
    c = leer_causas(defl)
    print(f"Indemnizaciones de maíz, diez estados, {c['anio'].min()}-{c['anio'].max()}: {len(c):,} filas, ${c['indemnizacion_usd'].sum() / 1e9:.2f} mil millones (2025)")

    # Tabla ancha por condado y año (la usa el semáforo por causa)
    ca = partes_por(c, ["unidad", "anio"]).reset_index()
    ca[["unidad", "anio", "total_usd"] + ORDEN].to_csv(PROCESADOS / "cierre_causas_condado_anio.csv", index=False)

    # Por estado
    c["estado"] = c["cod_estado"].map(ESTADOS)
    pe = partes_por(c, ["estado"])
    pe = pe.join(c.groupby("estado")["unidad"].nunique().rename("condados"))
    pe.to_csv(PROCESADOS / "cierre_causas_por_estado.csv")
    det = c.groupby(["estado", "causa", "causa_nombre"])["indemnizacion_usd"].sum().reset_index()
    det["parte_estado"] = det["indemnizacion_usd"] / det.groupby("estado")["indemnizacion_usd"].transform("sum")
    det.sort_values(["estado", "indemnizacion_usd"], ascending=[True, False]).to_csv(PROCESADOS / "cierre_causas_detalle.csv", index=False)
    pd.set_option("display.width", 250, "display.max_columns", 30)
    print((pe[[f"parte_{g}" for g in ORDEN]] * 100).round(1).assign(total_mil_millones=(pe["total_usd"] / 1e9).round(2)).to_string())
    print("Detalle de Minnesota:\n" + det[det["estado"] == "Minnesota"].sort_values("indemnizacion_usd", ascending=False).head(10).round(3).to_string(index=False))

    # Años de falla del modelo en Minnesota (y, como contexto, en cada estado nuevo)
    p = pd.read_csv(PROCESADOS / "ciegas_predicciones_principal.csv", dtype={"unidad": str, "grupo": str})
    p = p[p["nuevo"]]
    filas = []
    for estado, g in p.groupby("estado"):
        for anio, h in g.groupby("anio"):
            y = h["perdida_previa"].astype(bool)
            filas.append({"estado": estado, "anio": anio, "condados": len(h), "pct_condados_con_perdida": 100 * y.mean(),
                          "perdidas": int(y.sum()), "perdidas_captadas": int((y & h["pago_modelo"].astype(bool)).sum())})
    a = pd.DataFrame(filas)
    a["pct_captado"] = 100 * a["perdidas_captadas"] / a["perdidas"].replace(0, np.nan)
    a["anio_de_falla"] = (a["pct_condados_con_perdida"] >= 100 * PERDIDA_MINIMA) & (a["pct_captado"] < 100 * CAPTADO_MINIMO)
    por_anio = c.pivot_table(index=["estado", "anio"], columns="grupo_causa", values="indemnizacion_usd", aggfunc="sum", fill_value=0.0)
    por_anio = por_anio.reindex(columns=ORDEN, fill_value=0.0)
    por_anio["total_usd"] = por_anio.sum(axis=1)
    a = a.merge(por_anio.reset_index(), on=["estado", "anio"], how="left")
    a.to_csv(PROCESADOS / "cierre_causas_minnesota_anios.csv", index=False)       # incluye los siete estados nuevos
    mn = a[a["estado"] == "Minnesota"]
    print("Años de falla de Minnesota:\n" + mn[mn["anio_de_falla"]][["anio", "pct_condados_con_perdida", "pct_captado", "total_usd"]].round(1).to_string(index=False))

    # Mezcla de causas: Minnesota en años de falla, Minnesota en los demás años, otros estados en los mismos años
    def mezcla(x):
        s = x[ORDEN].sum()
        return pd.Series({**{f"parte_{g}": s[g] / s.sum() if s.sum() else np.nan for g in ORDEN}, "total_usd": s.sum(), "anios": len(x)})
    falla_anios = mn.loc[mn["anio_de_falla"], "anio"].tolist()
    otros = a[(a["estado"] != "Minnesota") & a["anio"].isin(falla_anios)]
    filas = [("Minnesota, años de falla del modelo", mezcla(mn[mn["anio_de_falla"]])),
             ("Minnesota, los demás años", mezcla(mn[~mn["anio_de_falla"]])),
             ("Minnesota, todos los años", mezcla(mn)),
             ("Otros seis estados nuevos, esos mismos años", mezcla(otros)),
             ("Otros seis estados nuevos, todos los años", mezcla(a[a["estado"] != "Minnesota"]))]
    res = pd.DataFrame({k: v for k, v in filas}).T
    res.index.name = "grupo"
    res.to_csv(PROCESADOS / "cierre_causas_minnesota_resumen.csv")
    print((res[[f"parte_{g}" for g in ORDEN]] * 100).round(1).assign(anios=res["anios"], total_mil_millones=(res["total_usd"] / 1e9).round(3)).to_string())

    # Contexto: parte de sequía en años con muchas pérdidas frente al resto, por estado
    ctx = []
    for estado, g in a.groupby("estado"):
        muchas = g["pct_condados_con_perdida"] >= 100 * PERDIDA_MINIMA
        for nombre, sel in [("años con 10 % o más de condados con pérdida", muchas), ("demás años", ~muchas)]:
            x = g[sel]
            s = x[ORDEN].sum()
            ctx.append({"estado": estado, "tipo_de_año": nombre, "anios": len(x), "parte_sequia": s["sequia"] / s.sum() if s.sum() else np.nan,
                        "parte_humedad": s["humedad"] / s.sum() if s.sum() else np.nan, "total_usd": s.sum()})
    pd.DataFrame(ctx).to_csv(PROCESADOS / "cierre_causas_contexto.csv", index=False)
    print(pd.DataFrame(ctx).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
