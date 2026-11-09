"""
42_palmer_topes.py
Fase 3 del cierre (plan congelado en docs/plan_cierre.md): contrato Palmer con topes.

Mismo disparador de 37 (Palmer de julio y agosto bajo el percentil 15 del condado, pago en línea recta hasta el percentil 2), con dos
cambios: suma asegurada de 50 % y 75 % del valor esperado, y un tope de pago total por año en los diez estados igual a 2 veces la
prima pura anual (el pago total promedio por año del mismo contrato sin tope, 1991-2025). Si un año se pasa del tope, todos los pagos
de ese año se reducen en la misma proporción. Se compara con el contrato sin topes, con la regla de lluvia (misma fórmula) y con el modelo.

Interpretación fijada: el contrato es "vendible" si en ningún año paga más de 1,5 veces la pérdida real de ese año y de cada $100
que paga llegan a quien perdió al menos lo mismo que con la regla de lluvia (con tope y misma suma).

Requiere 38. Salidas en datos/procesados/: cierre_palmer_topes_resumen.csv, cierre_palmer_topes_por_anio.csv, cierre_palmer_topes_criterio.json
Uso:  python scripts/42_palmer_topes.py
"""
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
PROCESADOS = RAIZ / "datos" / "procesados"
SUMAS = [0.50, 0.75, 1.00]               # 1,00 es solo la referencia sin topes de 37/38
SUMAS_CONTRATO = [0.50, 0.75]
MULTIPLO_TOPE = 2.0                      # tope = 2 veces la prima pura anual
LIMITE_VENDIBLE = 1.5                    # pago anual / pérdida real anual
DISPARADORES = {"Contrato Palmer": "f_palmer", "Regla de lluvia (pago proporcional)": "f_regla_proporcional", "Modelo": "f_modelo"}


def aplicar_tope(pago, anio, anios_total):
    """Reduce todos los pagos de un año en la misma proporción si el total del año pasa de 2 veces la prima pura anual."""
    total_anual = pago.groupby(anio).sum()
    prima_pura = total_anual.sum() / anios_total
    tope = MULTIPLO_TOPE * prima_pura
    factor = (tope / total_anual).clip(upper=1.0)
    return pago * anio.map(factor), tope, factor


def resumir(d, pago, anio_total, nombre, suma, con_tope, tope):
    perdida = d["perdida_usd"]
    y = d["perdida"].astype(bool)
    por_anio = pd.DataFrame({"pago": pago.groupby(d["anio"]).sum(), "perdida": perdida.groupby(d["anio"]).sum()})
    razon = por_anio["pago"] / por_anio["perdida"].replace(0, np.nan)
    total = pago.sum()
    excede = razon[razon > LIMITE_VENDIBLE]
    sin_perdida_con_pago = por_anio[(por_anio["perdida"] <= 0) & (por_anio["pago"] > 0)].index.tolist()
    return {"disparador": nombre, "suma_asegurada": suma, "con_tope": con_tope, "tope_anual_usd": tope if con_tope else np.nan,
            "pagos_usd": total, "pago_2012_usd": por_anio.loc[2012, "pago"], "perdida_2012_usd": por_anio.loc[2012, "perdida"],
            "pago_2012_sobre_perdida": razon.loc[2012], "razon_maxima_anual": razon.max(), "anio_razon_maxima": int(razon.idxmax()),
            "anios_con_pago_mayor_1_5": ", ".join(str(int(a)) for a in excede.index), "n_anios_mayor_1_5": len(excede),
            "anios_sin_perdida_con_pago": ", ".join(str(a) for a in sin_perdida_con_pago),
            "perdida_real_usd": perdida.sum(),
            "pct_perdida_cubierta": 100 * np.minimum(pago, perdida).sum() / perdida.sum(),
            "de_cada_100": 100 * pago[y].sum() / total if total else np.nan,
            "prima_pura_anual_usd": total / anio_total,
            "prima_pura_pct_suma": 100 * (total / anio_total) / (d["valor_esperado_usd"].sum() * suma / anio_total)}


def main():
    d = pd.read_csv(PROCESADOS / "ciegas_impacto_detalle.csv", dtype={"unidad": str, "grupo": str})
    d = d[d["anio"] >= 1991].reset_index(drop=True)
    anios_total = d["anio"].nunique()
    print(f"Filas: {len(d):,}; años: {anios_total}; pérdida real total ${d['perdida_usd'].sum() / 1e9:.2f} mil millones")
    filas, por_anio = [], []
    for suma in SUMAS:
        for nombre, col in DISPARADORES.items():
            pago = d["valor_esperado_usd"] * suma * d[col]
            filas.append(resumir(d, pago, anios_total, nombre, suma, False, np.nan))
            capado, tope, factor = aplicar_tope(pago, d["anio"], anios_total)
            filas.append(resumir(d, capado, anios_total, nombre, suma, True, tope))
            pa = pd.DataFrame({"anio": pago.groupby(d["anio"]).sum().index, "pago_sin_tope_usd": pago.groupby(d["anio"]).sum().to_numpy(),
                               "pago_con_tope_usd": capado.groupby(d["anio"]).sum().to_numpy()})
            pa["perdida_real_usd"] = d["perdida_usd"].groupby(d["anio"]).sum().to_numpy()
            pa["factor_tope"] = factor.reindex(pa["anio"]).to_numpy()
            por_anio.append(pa.assign(disparador=nombre, suma_asegurada=suma, tope_anual_usd=tope))
    res, anual = pd.DataFrame(filas), pd.concat(por_anio, ignore_index=True)
    res.to_csv(PROCESADOS / "cierre_palmer_topes_resumen.csv", index=False)
    anual.to_csv(PROCESADOS / "cierre_palmer_topes_por_anio.csv", index=False)

    # Criterio "vendible", en cada suma asegurada de contrato (50 % y 75 %)
    crit = {}
    for suma in SUMAS_CONTRATO:
        g = res[(res["suma_asegurada"] == suma) & res["con_tope"]].set_index("disparador")
        sin = res[(res["suma_asegurada"] == suma) & ~res["con_tope"]].set_index("disparador")
        p, r = g.loc["Contrato Palmer"], g.loc["Regla de lluvia (pago proporcional)"]
        c1 = bool(p["razon_maxima_anual"] <= LIMITE_VENDIBLE and not p["anios_sin_perdida_con_pago"])
        c2 = bool(p["de_cada_100"] >= r["de_cada_100"])
        crit[f"suma {int(suma * 100)} %"] = {
            "razon_maxima_anual_con_tope": float(p["razon_maxima_anual"]), "anio_razon_maxima": int(p["anio_razon_maxima"]),
            "anios_con_pago_mayor_1_5": p["anios_con_pago_mayor_1_5"], "anios_sin_perdida_con_pago": p["anios_sin_perdida_con_pago"],
            "condicion_1_nunca_mas_de_1_5_veces": c1,
            "de_cada_100_palmer_con_tope": float(p["de_cada_100"]), "de_cada_100_lluvia_con_tope": float(r["de_cada_100"]),
            "de_cada_100_lluvia_sin_tope": float(sin.loc["Regla de lluvia (pago proporcional)", "de_cada_100"]),
            "condicion_2_igual_o_mejor_que_lluvia": c2, "vendible": bool(c1 and c2)}
    crit["vendible_en_ambas_sumas"] = bool(all(crit[k]["vendible"] for k in crit if k.startswith("suma")))
    (PROCESADOS / "cierre_palmer_topes_criterio.json").write_text(json.dumps(crit, indent=1, ensure_ascii=False), encoding="utf-8")

    pd.set_option("display.width", 280, "display.max_columns", 40)
    t = res.copy()
    for c in ["tope_anual_usd", "pagos_usd", "pago_2012_usd", "perdida_2012_usd", "perdida_real_usd", "prima_pura_anual_usd"]:
        t[c] = t[c] / 1e6
    print(t.round(2).to_string(index=False))
    print(json.dumps(crit, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
