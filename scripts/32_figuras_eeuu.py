"""
32_figuras_eeuu.py
Fase 5 del seguro de sequía para el maíz de EE. UU.: figuras del pitch (docs/figuras/pitch_eeuu_*.png),
con títulos en español sencillo y sin siglas. No hace análisis nuevos: solo lee lo que dejaron 08, 29, 30 y 31.
También hace pitch_serie_tiempo_eeuu.png (lluvia mes a mes 1981-2025 y cosecha de cada año), que antes hacía el script 17.

Requiere 08, 29, 30 y 31. Uso:  python scripts/32_figuras_eeuu.py
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
import comun  # noqa: E402

PROCESADOS = RAIZ / "datos" / "procesados"
FIGURAS = RAIZ / "docs" / "figuras"
SUPERFICIE, TINTA, TINTA_2, REJILLA = comun.SUPERFICIE, comun.TINTA, comun.TINTA_2, comun.REJILLA
AZUL, NARANJA, GRIS, AZUL_CLARO = "#2a78d6", "#eb6834", "#b8b7b1", "#8fb8ea"
SEMAFORO = {"verde": "#1baf7a", "amarillo": "#e8b00f", "rojo": "#d64b3a"}
NOMBRE_MODELO = {"regla": "Regla de lluvia\n(junio a agosto)", "solo_ubicacion": "Solo sabe dónde\nestá el condado",
                 "regresion_logistica": "Regresión\nlogística", "bosque_aleatorio": "Bosque\naleatorio", "lightgbm": "Árboles en\nsecuencia (LightGBM)"}
MES = {"may": "mayo", "jun": "junio", "jul": "julio", "ago": "agosto", "sep": "septiembre"}


def guardar(fig, nombre, nota=None):
    if nota:
        fig.text(0.01, 0.01, nota, fontsize=7.5, color=TINTA_2)
    fig.tight_layout(rect=(0, 0.05 if nota else 0, 1, 1))
    fig.savefig(FIGURAS / nombre, dpi=180, facecolor=SUPERFICIE)
    plt.close(fig)
    print(f"Guardada docs/figuras/{nombre}")


def nombre_variable(v):
    if v.startswith("lluvia_"):
        return f"Lluvia de {MES[v[7:]]}"
    if v.startswith("tmax_"):
        return f"Temperatura máxima de {MES[v[5:]]}"
    if v.startswith("palmer_"):
        return f"Índice de sequía, {MES[v[7:]]}"
    return {"racha_meses_secos": "Meses secos seguidos", "deficit_jul_ago": "Falta de lluvia en julio y agosto",
            "fraccion_riego": "Parte del maíz con riego", "latitud": "Latitud", "longitud": "Longitud"}.get(v, "Estado")


def modelos():
    r = pd.read_csv(PROCESADOS / "eeuu_sequia_resultados.csv")
    d = r[r["esquema"] == "hacia_adelante"].set_index("modelo").reindex(list(NOMBRE_MODELO))
    mejor = json.loads((PROCESADOS / "eeuu_sequia_mejor.json").read_text(encoding="utf-8"))["modelo"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.6), facecolor=SUPERFICIE)
    colores = [GRIS if m in ("regla", "solo_ubicacion") else (AZUL if m == mejor else AZUL_CLARO) for m in d.index]
    x = np.arange(len(d))
    for ax, col, titulo, base in [(a1, "auc", "Capacidad de distinguir años con y sin pérdida", 0.5),
                                  (a2, "heidke", "Aciertos por encima del azar", 0.0)]:
        err = np.vstack([d[col] - d[f"{col}_ic_inf"], d[f"{col}_ic_sup"] - d[col]])
        ax.bar(x, d[col], color=colores, width=0.62, zorder=3, yerr=err, error_kw={"ecolor": TINTA_2, "capsize": 3, "lw": 1})
        ax.axhline(base, color=TINTA, linestyle="--", linewidth=1, zorder=4)
        ax.text(len(d) - 0.5, base, " azar", va="bottom", ha="right", fontsize=8.5, color=TINTA)
        for i, v in enumerate(d[col]):
            ax.text(i, v / 2 if col == "heidke" else base + (v - base) / 2, f"{v:.2f}".replace(".", ","), ha="center", color="white", fontsize=9, zorder=5)
        comun.estilo(ax)
        ax.set_xticks(x, [NOMBRE_MODELO[m] for m in d.index], fontsize=8)
        ax.set_title(titulo, loc="left", fontsize=11, color=TINTA)
    a1.set_ylim(0.4, 1)
    a1.set_ylabel("0,5 = azar; 1 = perfecto", color=TINTA_2)
    a2.set_ylabel("0 = azar; 1 = perfecto", color=TINTA_2)
    fig.suptitle("Los modelos que aprenden distinguen mejor que la regla de lluvia", x=0.01, ha="left", fontsize=13, color=TINTA)
    guardar(fig, "pitch_eeuu_modelos.png", "Maíz de Iowa, Illinois e Indiana, 1991-2025. Cada año se predice con modelos entrenados solo con años anteriores. "
            "Barras finas: rango de 95 % al cambiar los años. Todos pagan en tantos condados como la regla.")


def aporte():
    a = pd.read_csv(PROCESADOS / "eeuu_sequia_aporte.csv")
    a = a[a["modelo"] == "lightgbm"].set_index("conjunto")
    filas = [("solo_ubicacion", "Solo dónde está el condado"), ("ubicacion_y_riego", "+ riego"), ("ubicacion_y_lluvia", "+ lluvia"),
             ("ubicacion_y_temperatura", "+ temperatura"), ("ubicacion_y_sequia", "+ índice de sequía"), ("todas", "Todo junto")]
    filas = [(f, n) for f, n in filas if f in a.index]       # sin dato de riego no hay fila de riego
    d = a.loc[[f for f, _ in filas]]
    fig, ax = plt.subplots(figsize=(9, 4.4), facecolor=SUPERFICIE)
    y = np.arange(len(d))[::-1]
    colores = [GRIS] + [AZUL_CLARO] * (len(d) - 2) + [AZUL]
    ax.barh(y, d["auc"] - 0.5, left=0.5, color=colores, height=0.6, zorder=3,
            xerr=np.vstack([d["auc"] - d["auc_ic_inf"], d["auc_ic_sup"] - d["auc"]]), error_kw={"ecolor": TINTA_2, "capsize": 3, "lw": 1})
    base = d.loc["solo_ubicacion", "auc"]
    for yi, (f, v) in zip(y, d["auc"].items()):
        texto = f"{v:.2f}".replace(".", ",") + ("" if f == "solo_ubicacion" else f"  ({v - base:+.2f})".replace(".", ","))
        ax.text(max(v, d.loc[f, "auc_ic_sup"]) + 0.01, yi, texto, va="center", fontsize=9, color=TINTA)
    ax.set_yticks(y, [n for _, n in filas])
    ax.axvline(0.5, color=TINTA, linestyle="--", linewidth=1)
    comun.estilo(ax)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=REJILLA, linewidth=0.7, zorder=0)
    ax.set_xlim(0.45, 1)
    ax.set_xlabel("Capacidad de distinguir años con y sin pérdida (0,5 = azar; 1 = perfecto)", color=TINTA_2)
    ax.set_title("Cuánto agrega el clima a saber dónde queda el condado", loc="left", fontsize=12, color=TINTA)
    guardar(fig, "pitch_eeuu_aporte.png", "Entre paréntesis: lo que se gana frente a solo la ubicación. Validación año por año, 1991-2025, "
            "con el mismo modelo (LightGBM).")


def variables():
    s = pd.read_csv(PROCESADOS / "eeuu_sequia_shap.csv")
    s = s[~s["variable"].str.startswith("grupo_")].head(12).iloc[::-1]
    color = {"lluvia": AZUL, "temperatura": NARANJA, "sequia": "#8a5cc2", "riego": "#1baf7a", "ubicacion": GRIS}
    fig, ax = plt.subplots(figsize=(9, 5), facecolor=SUPERFICIE)
    ax.barh([nombre_variable(v) for v in s["variable"]], s["shap_medio_absoluto"], color=[color[g] for g in s["grupo"]], height=0.62, zorder=3)
    comun.estilo(ax)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=REJILLA, linewidth=0.7, zorder=0)
    ax.set_xlabel("Peso promedio en la predicción", color=TINTA_2)
    ax.legend(handles=[Patch(color=color[g], label=n) for g, n in [("lluvia", "Lluvia"), ("temperatura", "Temperatura"),
                       ("sequia", "Índice de sequía"), ("riego", "Riego"), ("ubicacion", "Ubicación")] if g in set(s["grupo"])],
              frameon=False, fontsize=8.5, loc="lower right")
    ax.set_title("Qué meses y qué variables pesan más", loc="left", fontsize=12, color=TINTA)
    guardar(fig, "pitch_eeuu_variables.png", "Peso medido con valores SHAP del mejor modelo, en 2012-2025. Índice de sequía: Palmer (NOAA).")


def probabilidad_lluvia():
    d = pd.read_csv(PROCESADOS / "eeuu_sequia_predicciones_adelante.csv", dtype={"unidad": str})
    b = pd.read_csv(PROCESADOS / "eeuu_sequia_base.csv", dtype={"unidad": str})[["unidad", "anio", "lluvia_jun", "lluvia_jul", "lluvia_ago"]]
    d = d.merge(b, on=["unidad", "anio"])
    d["lluvia_verano"] = d[["lluvia_jun", "lluvia_jul", "lluvia_ago"]].mean(axis=1)
    d["grupo_lluvia"] = pd.qcut(d["lluvia_verano"], 10, labels=False)
    g = d.groupby("grupo_lluvia").agg(lluvia=("lluvia_verano", "median"), observada=("perdida_previa", "mean"), modelo=("prob_calibrada", "mean"))
    fig, ax = plt.subplots(figsize=(9, 4.4), facecolor=SUPERFICIE)
    x = np.arange(len(g))
    ax.bar(x, 100 * g["observada"], color=[NARANJA if i < 2 or i == len(g) - 1 else AZUL_CLARO for i in x], width=0.65, zorder=3, label="Pérdida que de verdad hubo")
    ax.plot(x, 100 * g["modelo"], color=TINTA, marker="o", linewidth=1.5, zorder=4, label="Probabilidad que dio el modelo")
    for i, v in enumerate(g["observada"]):
        ax.text(i + 0.22, 100 * v + 0.8, f"{100 * v:.0f} %", ha="left", fontsize=8.5, color=TINTA)
    ax.set_xticks(x, [f"{v:.0f} %" for v in g["lluvia"]], fontsize=8.5)
    ax.set_xlabel("Lluvia de junio a agosto frente a lo normal (de lo más seco a lo más lluvioso; cada barra es un 10 % de los casos)", color=TINTA_2, fontsize=8.5)
    ax.set_ylabel("Condado-años con pérdida (%)", color=TINTA_2)
    comun.estilo(ax)
    ax.legend(frameon=False, fontsize=8.5)
    ax.set_title("Un verano muy seco dispara la pérdida; uno muy lluvioso también, y eso el modelo casi no lo ve", loc="left", fontsize=12, color=TINTA)
    guardar(fig, "pitch_eeuu_probabilidad_lluvia.png", "Iowa, Illinois e Indiana, 1991-2025. Pérdida: rendimiento de 80 % o menos de lo esperado por la tendencia de años anteriores.")


def mapa():
    t = pd.read_csv(PROCESADOS / "semaforo_condados.csv", dtype={"unidad": str})
    cond = gpd.read_file("zip://" + str(RAIZ / "datos" / "crudos" / "eeuu" / "condados" / "cb_2023_us_county_500k.zip"))
    cond = cond[cond["STATEFP"].isin(["17", "18", "19"])].merge(t[["unidad", "color"]], left_on="GEOID", right_on="unidad", how="left")
    fig, ax = plt.subplots(figsize=(10, 5.6), facecolor=SUPERFICIE)
    cond.plot(ax=ax, color=cond["color"].map(SEMAFORO).fillna("#ececea"), edgecolor="white", linewidth=0.3)
    cond.dissolve("STATEFP").boundary.plot(ax=ax, color=TINTA_2, linewidth=0.8)
    ax.set_axis_off()
    n = t["color"].value_counts()
    ax.legend(handles=[Patch(color=SEMAFORO[c], label=f"{e} ({n.get(c, 0)} condados)") for c, e in
                       [("verde", "Verde: el seguro tendría poco error"), ("amarillo", "Amarillo: con cautela"), ("rojo", "Rojo: no conviene")]] +
              [Patch(color="#ececea", label="Sin datos suficientes")], frameon=False, fontsize=8.5, loc="lower left")
    ax.set_title("Semáforo de condados: dónde funcionaría el seguro de sequía", loc="left", fontsize=12, color=TINTA)
    guardar(fig, "pitch_eeuu_semaforo_mapa.png", "Construido solo con 1981-2018: calidad del dato y cuánto responde la cosecha al clima del verano. Sin dato de riego (no se pudo descargar).")


def prueba_semaforo():
    p = pd.read_csv(PROCESADOS / "eeuu_semaforo_prueba.csv")
    c = p[(p["tabla"] == "por_color") & (p["esquema"] == "particion_fija")]
    dif = p[(p["tabla"] == "verde_menos_rojo") & (p["esquema"] == "particion_fija") & (p["indice"] == "modelo")].set_index("metrica")
    fig, ejes = plt.subplots(1, 3, figsize=(12, 4.2), facecolor=SUPERFICIE)
    for ax, col, titulo in zip(ejes, ["auc", "heidke", "pct_perdidas_captadas"],
                               ["Capacidad de distinguir", "Aciertos por encima del azar", "Pérdidas en las que habría pagado (%)"]):
        for j, indice in enumerate(["modelo", "regla"]):
            d = c[c["indice"] == indice].set_index("color").reindex(["verde", "amarillo", "rojo"])
            x = np.arange(3) + (j - 0.5) * 0.36
            ax.bar(x, d[col], width=0.34, color=[SEMAFORO[k] for k in d.index], alpha=1 if indice == "modelo" else 0.45, zorder=3,
                   label="Modelo" if indice == "modelo" else "Regla de lluvia")
        ax.set_xticks(range(3), ["Verdes", "Amarillos", "Rojos"])
        comun.estilo(ax)
        sin_perdidas = c[(c["indice"] == "modelo") & (c["color"] == "verde")]["perdidas"].sum() == 0
        texto = ("Los verdes no tuvieron\npérdidas: no se puede\ncomparar" if sin_perdidas else
                 f"verde − rojo: {dif.loc[col, 'diferencia']:+.2f}\n(95 %: {dif.loc[col, 'ic_inf']:+.2f} a {dif.loc[col, 'ic_sup']:+.2f})".replace(".", ","))
        ax.set_title(titulo, loc="left", fontsize=10, color=TINTA)
        ax.text(0.02, 0.6, texto, transform=ax.transAxes, ha="left", va="center", fontsize=8, color=TINTA_2)
    ejes[0].legend(handles=[Patch(color=TINTA_2, label="Modelo (color fuerte)"), Patch(color=TINTA_2, alpha=0.45, label="Regla (color claro)")],
                   frameon=False, fontsize=8, loc="lower left")
    resultado = (PROCESADOS / "eeuu_semaforo_resultado.txt").read_text(encoding="utf-8").strip().endswith("True")
    fig.suptitle("El semáforo en años que no vio (2019-2025): " + ("los verdes salen mejor que los rojos" if resultado else "los verdes no salen claramente mejor que los rojos"),
                 x=0.01, ha="left", fontsize=12, color=TINTA)
    guardar(fig, "pitch_eeuu_semaforo_prueba.png", "Rango de 95 % al cambiar los años de prueba. El semáforo se armó solo con años hasta 2018.")


def dolares():
    per = pd.read_csv(PROCESADOS / "eeuu_impacto_perdida_por_anio.csv").set_index("anio")
    rma = pd.read_csv(PROCESADOS / "eeuu_impacto_rma_por_anio.csv").set_index("anio")
    det = pd.read_csv(PROCESADOS / "eeuu_impacto_simulacion_detalle.csv", dtype={"unidad": str})
    det["pago_modelo"] = det["valor_esperado_usd"] * det["severidad_prevista"] * det["pago_umbral"].astype(bool)
    sim = det.groupby("anio")["pago_modelo"].sum()
    anios = per.index
    fig, ax = plt.subplots(figsize=(12, 4.6), facecolor=SUPERFICIE)
    ax.bar(anios, per.loc[anios, "perdida_usd"] / 1e9, color=GRIS, width=0.8, zorder=3, label="Pérdida real de cosecha")
    ax.plot(rma.index[rma.index >= 1989], rma.loc[rma.index >= 1989, "indemnizacion"] / 1e9, color=AZUL, marker="o", ms=3.5, lw=1.5, zorder=4,
            label="Lo que pagó el seguro agrícola real (todas las causas)")
    ax.plot(sim.index, sim / 1e9, color=NARANJA, marker="s", ms=3.5, lw=1.5, zorder=5, label="Lo que habría pagado el índice (modelo, suma del 100 %)")
    for a in [1988, 2012]:
        if a in per.index:
            ax.text(a, per.loc[a, "perdida_usd"] / 1e9, f" {a}", fontsize=9, color=TINTA, va="bottom")
    comun.estilo(ax)
    ax.set_ylabel("Miles de millones de dólares de 2025", color=TINTA_2)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax.set_title("Dólares: pérdida real, lo que pagó el seguro real y lo que habría pagado el índice", loc="left", fontsize=12, color=TINTA)
    guardar(fig, "pitch_eeuu_dolares.png", "Iowa, Illinois e Indiana. Pérdida real con precio nacional de cada campaña (USDA). Seguro real: RMA, maíz, todos los planes. "
            "El seguro real cubre también caídas de precio y otras causas.")


def subsidio():
    s = pd.read_csv(PROCESADOS / "eeuu_impacto_simulacion.csv")
    s = s[(s["grupo"] == "todos") & ((s["suma_asegurada"] == 1.0) | s["disparador"].str.startswith("RMA"))]
    fig, ejes = plt.subplots(1, 2, figsize=(11, 4.2), facecolor=SUPERFICIE, sharey=True)
    for ax, periodo in zip(ejes, ["prueba 2019-2025", "hacia adelante 1991-2025"]):
        d = s[s["periodo"] == periodo].set_index("disparador")
        valores = [("Pagando al azar", d.loc["Regla", "de_cada_100_al_azar"], GRIS), ("Regla de lluvia", d.loc["Regla", "de_cada_100_pagados"], AZUL_CLARO),
                   ("Modelo", d.loc["Modelo", "de_cada_100_pagados"], AZUL)]
        ax.bar([v[0] for v in valores], [v[1] for v in valores], color=[v[2] for v in valores], width=0.6, zorder=3)
        for i, (_, v, _) in enumerate(valores):
            ax.text(i, v + 1, f"${v:.0f}", ha="center", fontsize=11, color=TINTA)
        comun.estilo(ax)
        ax.set_title(periodo.capitalize().replace("Hacia adelante", "Año por año,"), loc="left", fontsize=10, color=TINTA)
    ejes[0].set_ylabel("De cada $100 pagados, cuántos llegan\na condados que de verdad perdieron", color=TINTA_2)
    fig.suptitle("De cada $100 que paga el seguro, cuántos llegan a quien perdió la cosecha", x=0.01, ha="left", fontsize=12, color=TINTA)
    guardar(fig, "pitch_eeuu_subsidio.png", "Con un recargo de 30 % (supuesto), de cada $100 de subsidio llega esa cifra dividida entre 1,3. "
            "El pago es proporcional a la pérdida que estima el modelo.")


def fecha(anio, mes, dia=1):
    return pd.Timestamp(year=int(anio), month=int(mes), day=dia)


def serie_tiempo():
    """Lluvia mes a mes 1981-2025 (junio-agosto sombreado) y cosecha de cada año, promedio de los tres estados."""
    sequias, sombra = [1988, 2012], "#f6d3c2"
    m = pd.read_csv(PROCESADOS / "chirps_mensual_condados_eeuu.csv")
    m = m[m["anio"] <= 2025].groupby(["anio", "mes"])["lluvia_mm"].mean().reset_index()
    m["fecha"] = [fecha(a, b, 15) for a, b in zip(m["anio"], m["mes"])]
    base = pd.read_csv(PROCESADOS / "eeuu_base_ciclos.csv")
    cosecha = (100 * base[base["en_analisis"]].groupby("anio")["rend_relativo"].mean()).reset_index()

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 5.6), sharex=True, facecolor=SUPERFICIE,
                                   gridspec_kw={"height_ratios": [1.2, 1]})
    for anio in range(1981, 2026):
        for ax in (ax1, ax2):
            ax.axvspan(fecha(anio, 6), fecha(anio, 9), color=sombra, linewidth=0, zorder=0)
    ax1.plot(m["fecha"], m["lluvia_mm"], color=AZUL, linewidth=1, zorder=3)
    ax1.set_ylabel("Lluvia del mes (mm)", color=TINTA_2, fontsize=9)
    comun.estilo(ax1)
    # Cosecha como barra desde el 100 % (lo esperado), en julio de cada año
    for anio, v in zip(cosecha["anio"], cosecha["rend_relativo"]):
        ax2.bar(fecha(anio, 7), v - 100, bottom=100, width=150, color=NARANJA if anio in sequias else AZUL, zorder=3)
    ax2.axhline(100, color=TINTA_2, linewidth=0.8, zorder=4)
    ax2.set_ylabel("Cosecha\n(% de lo esperado)", color=TINTA_2, fontsize=9)
    comun.estilo(ax2)
    for anio in sequias:
        v = cosecha.loc[cosecha["anio"] == anio, "rend_relativo"].iloc[0]
        ax2.text(fecha(anio, 7), v - 4, f"{anio}: gran sequía", ha="center", va="top", fontsize=8.5, color=NARANJA)
    ax2.set_ylim(50, 130)
    ax1.set_title("Estados Unidos (Iowa, Illinois, Indiana): la lluvia mes a mes y la cosecha de cada año, 1981-2025",
                  loc="left", fontsize=11.5, color=TINTA, pad=8)
    fig.text(0.01, 0.01, "Franjas: junio a agosto de cada año, los meses que mira el seguro. Lluvia y cosecha: "
             "promedio de 293 condados. Cosecha: rendimiento frente al esperado por la tendencia de cada condado.",
             fontsize=8, color=TINTA_2)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(FIGURAS / "pitch_serie_tiempo_eeuu.png", dpi=170, facecolor=SUPERFICIE)
    plt.close(fig)


def main():
    serie_tiempo()
    modelos()
    aporte()
    variables()
    probabilidad_lluvia()
    mapa()
    prueba_semaforo()
    dolares()
    subsidio()


if __name__ == "__main__":
    main()
