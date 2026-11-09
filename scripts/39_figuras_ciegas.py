"""
39_figuras_ciegas.py
Fase 6 de la prueba a ciegas: ocho figuras docs/figuras/pitch_ciegas_*.png, con títulos en español sencillo y sin siglas.
No hace análisis nuevos: solo lee lo que dejaron 35, 36, 37 y 38.

Requiere 35, 36, 37 y 38. Uso:  python scripts/39_figuras_ciegas.py
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
AZUL, NARANJA, GRIS, AZUL_CLARO, VERDE_OSC = "#2a78d6", "#eb6834", "#b8b7b1", "#8fb8ea", "#1baf7a"
SEMAFORO = {"verde": "#1baf7a", "amarillo": "#e8b00f", "rojo": "#d64b3a"}
ORIGINALES = ["17", "18", "19"]
NUEVOS = ["31", "27", "39", "29", "20", "46", "55"]
ESTADOS = {"17": "Illinois", "18": "Indiana", "19": "Iowa", "31": "Nebraska", "27": "Minnesota", "39": "Ohio", "29": "Missouri",
           "20": "Kansas", "46": "South Dakota", "55": "Wisconsin"}
CONDADOS = RAIZ / "datos" / "crudos" / "eeuu" / "condados" / "cb_2023_us_county_500k.zip"


def coma(x, d=2):
    return f"{x:.{d}f}".replace(".", ",")


def guardar(fig, nombre, nota=None):
    if nota:
        fig.text(0.01, 0.01, nota, fontsize=7.5, color=TINTA_2)
    fig.tight_layout(rect=(0, 0.05 if nota else 0, 1, 1))
    fig.savefig(FIGURAS / nombre, dpi=180, facecolor=SUPERFICIE)
    plt.close(fig)
    print(f"Guardada docs/figuras/{nombre}")


def estados_geo():
    g = gpd.read_file("zip://" + str(CONDADOS))
    return g[g["STATEFP"].isin(ORIGINALES + NUEVOS)]


# 1. Mapa
def mapa_estados():
    g = estados_geo()
    fig, ax = plt.subplots(figsize=(10, 5.8), facecolor=SUPERFICIE)
    g["tipo"] = np.where(g["STATEFP"].isin(ORIGINALES), "entrena", "prueba")
    g.plot(ax=ax, color=g["tipo"].map({"entrena": AZUL, "prueba": NARANJA}), edgecolor="white", linewidth=0.2)
    est = g.dissolve("STATEFP")
    est.boundary.plot(ax=ax, color=TINTA, linewidth=0.8)
    for fips, fila in est.iterrows():
        p = fila.geometry.representative_point()
        ax.text(p.x, p.y, ESTADOS[fips], ha="center", va="center", fontsize=8, color="white", weight="bold")
    ax.set_axis_off()
    ax.legend(handles=[Patch(color=AZUL, label="Estados con los que se entrenó el modelo (3)"),
                       Patch(color=NARANJA, label="Estados que el modelo nunca vio, para la prueba a ciegas (7)")],
              frameon=False, fontsize=9, loc="upper left")
    ax.set_title("Diez estados: tres para aprender y siete para probar a ciegas", loc="left", fontsize=12, color=TINTA)
    guardar(fig, "pitch_ciegas_mapa_estados.png", "Maíz para grano. Los siete estados de prueba no se usaron para entrenar, escoger ni calibrar el modelo.")


# 2. Modelo en los estados nuevos
def modelo_nuevos():
    r = pd.read_csv(PROCESADOS / "ciegas_resultados.csv")
    r = r[r["modo"] == "principal"]
    nombres = {"modelo": "Modelo", "regla": "Regla de lluvia", "tasa_historica": "Historia del\ncondado", "azar": "Azar"}
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.6), facecolor=SUPERFICIE)
    colores = {"modelo": AZUL, "regla": AZUL_CLARO, "tasa_historica": GRIS, "azar": "#dddcd6"}
    for ax, col, titulo, base in [(a1, "auc", "Capacidad de distinguir años con y sin pérdida", 0.5), (a2, "heidke", "Aciertos por encima del azar", 0.0)]:
        for j, (sub, rot, alfa) in enumerate([("todos", "Todos los años", 1.0), ("sin_2012", "Sin 2012", 0.55)]):
            d = r[r["subconjunto"] == sub].set_index("indice").reindex(list(nombres))
            x = np.arange(len(d)) + (j - 0.5) * 0.38
            err = np.vstack([d[col] - d[f"{col}_ic_inf"], d[f"{col}_ic_sup"] - d[col]])
            ax.bar(x, d[col], width=0.36, color=[colores[i] for i in d.index], alpha=alfa, zorder=3, yerr=err,
                   error_kw={"ecolor": TINTA_2, "capsize": 2, "lw": 0.9}, label=rot)
            for xi, v in zip(x, d[col]):
                ax.text(xi, v + 0.012 + (0.02 if col == "auc" else 0), coma(v), ha="center", fontsize=7.5, color=TINTA)
        ax.axhline(base, color=TINTA, linestyle="--", linewidth=1, zorder=4)
        ax.set_xticks(range(len(nombres)), list(nombres.values()), fontsize=8.5)
        comun.estilo(ax)
        ax.set_title(titulo, loc="left", fontsize=11, color=TINTA)
    a1.set_ylim(0.3, 1)
    a1.set_ylabel("0,5 = azar; 1 = perfecto", color=TINTA_2)
    a2.set_ylabel("0 = azar; 1 = perfecto", color=TINTA_2)
    a1.legend(handles=[Patch(color=TINTA_2, label="Todos los años"), Patch(color=TINTA_2, alpha=0.55, label="Sin 2012")], frameon=False, fontsize=8, loc="upper right")
    crit = json.loads((PROCESADOS / "ciegas_criterio.json").read_text(encoding="utf-8"))
    fig.suptitle("Estados que el modelo nunca vio: " + ("supera a la regla de lluvia" if crit["pasa_la_prueba"] else "no cumple el criterio fijado de antemano"),
                 x=0.01, ha="left", fontsize=13, color=TINTA)
    guardar(fig, "pitch_ciegas_modelo_nuevos.png", "Siete estados de prueba, 1991-2025, año por año. Todos pagan en tantos condados como la regla. Barras finas: rango de 95 % al cambiar los años.")


# 3. Por estado
def por_estado():
    r = pd.read_csv(PROCESADOS / "ciegas_resultados.csv")
    r = r[(r["modo"] == "principal") & r["subconjunto"].str.startswith("estado: ") & ~r["subconjunto"].str.endswith("sin 2012")]
    r = r.assign(estado=r["subconjunto"].str.replace("estado: ", "", regex=False))
    orden = [ESTADOS[g] for g in NUEVOS]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.8), facecolor=SUPERFICIE, sharey=True)
    for ax, col, titulo, base in [(a1, "auc", "Capacidad de distinguir años con y sin pérdida", 0.5), (a2, "heidke", "Aciertos por encima del azar", 0.0)]:
        y = np.arange(len(orden))[::-1]
        for k, (indice, color, nombre) in enumerate([("modelo", AZUL, "Modelo"), ("regla", GRIS, "Regla de lluvia")]):
            d = r[r["indice"] == indice].set_index("estado").reindex(orden)
            ax.barh(y + (0.18 if k == 0 else -0.18), d[col], height=0.34, color=color, zorder=3, label=nombre)
            for yi, v in zip(y + (0.18 if k == 0 else -0.18), d[col]):
                ax.text(max(v, base) + 0.01, yi, coma(v), va="center", fontsize=7.5, color=TINTA)
        ax.axvline(base, color=TINTA, linestyle="--", linewidth=1)
        ax.set_yticks(y, orden)
        comun.estilo(ax)
        ax.grid(axis="y", visible=False)
        ax.grid(axis="x", color=REJILLA, linewidth=0.7, zorder=0)
        ax.set_title(titulo, loc="left", fontsize=11, color=TINTA)
    a1.legend(frameon=False, fontsize=8.5, loc="lower right")
    fig.suptitle("El modelo frente a la regla de lluvia, estado por estado (siete estados que nunca vio)", x=0.01, ha="left", fontsize=12.5, color=TINTA)
    guardar(fig, "pitch_ciegas_por_estado.png", "1991-2025. En cada estado, el modelo paga en el mismo número de condados que la regla de lluvia en los siete estados juntos.")


# 4. Semáforo hacia adelante
def semaforo_adelante():
    r = pd.read_csv(PROCESADOS / "ciegas_semaforo_resultados.csv")
    d = pd.read_csv(PROCESADOS / "ciegas_semaforo_diferencias.csv")
    prueba = "prueba 1: hacia adelante, 10 estados"
    c = r[(r["prueba"] == prueba) & (r["variante"] == "regla base") & (r["indice"] == "modelo")].set_index("color").reindex(["verde", "amarillo", "rojo"])
    dd = d[(d["prueba"] == prueba) & (d["variante"] == "regla base") & (d["indice"] == "modelo")].set_index("metrica")
    crit = json.loads((PROCESADOS / "ciegas_semaforo_criterio.json").read_text(encoding="utf-8"))[f"{prueba} | regla base"]
    fig, ejes = plt.subplots(1, 3, figsize=(12.5, 4.4), facecolor=SUPERFICIE)
    for ax, col, titulo in zip(ejes, ["heidke", "pct_perdidas_captadas", "de_cada_100"],
                               ["Aciertos por encima del azar", "Pérdidas en las que habría pagado (%)", "De cada $100 pagados, a quien perdió"]):
        ax.bar(range(3), c[col], color=[SEMAFORO[k] for k in c.index], width=0.6, zorder=3)
        for i, v in enumerate(c[col]):
            ax.text(i, v, coma(v, 2 if col == "heidke" else 0), ha="center", va="bottom", fontsize=9, color=TINTA)
        ax.set_xticks(range(3), ["Verdes", "Amarillos", "Rojos"])
        comun.estilo(ax)
        ax.set_ylim(0, c[col].max() * 1.32)
        ax.set_title(titulo, loc="left", fontsize=10, color=TINTA)
        f = 2 if col == "heidke" else 1
        ax.text(0.02, 0.97, f"verde menos rojo: {dd.loc[col, 'diferencia']:+.{f}f}\n(95 %: {dd.loc[col, 'ic_inf']:+.{f}f} a {dd.loc[col, 'ic_sup']:+.{f}f})".replace(".", ","),
                transform=ax.transAxes, va="top", fontsize=8, color=TINTA_2)
    fig.suptitle("Semáforo año por año, sin ver el futuro: " + ("los verdes salen mejor que los rojos" if crit["cumple"] else "los verdes no salen claramente mejor que los rojos"),
                 x=0.01, ha="left", fontsize=12.5, color=TINTA)
    guardar(fig, "pitch_ciegas_semaforo_adelante.png", "Diez estados, 2006-2025. Cada año los colores se recalculan solo con años anteriores. Barras: modelo. Rango de 95 % al cambiar los años.")


# 5. Mapa del semáforo
def semaforo_mapa():
    col = pd.read_csv(PROCESADOS / "ciegas_semaforo_colores_adelante.csv", dtype={"unidad": str})
    col = col[col["anio"] == col["anio"].max()]
    g = estados_geo().merge(col[["unidad", "color_base"]], left_on="GEOID", right_on="unidad", how="left")
    fig, ax = plt.subplots(figsize=(10, 5.8), facecolor=SUPERFICIE)
    g.plot(ax=ax, color=g["color_base"].map(SEMAFORO).fillna("#ececea"), edgecolor="white", linewidth=0.2)
    g.dissolve("STATEFP").boundary.plot(ax=ax, color=TINTA_2, linewidth=0.8)
    ax.set_axis_off()
    n = col["color_base"].value_counts()
    ax.legend(handles=[Patch(color=SEMAFORO[k], label=f"{t} ({n.get(k, 0)} condados)") for k, t in
                       [("verde", "Verde: el seguro tendría poco error"), ("amarillo", "Amarillo: con cautela"), ("rojo", "Rojo: no conviene")]] +
              [Patch(color="#ececea", label="Sin datos suficientes")], frameon=False, fontsize=8.5, loc="lower left")
    ax.set_title(f"Semáforo de condados en diez estados (colores con datos hasta {int(col['anio'].max()) - 1})", loc="left", fontsize=12, color=TINTA)
    guardar(fig, "pitch_ciegas_semaforo_mapa.png", "Calidad del dato y cuánto responde la cosecha al clima del verano. Misma regla en todos los estados, sin dato de riego en el color.")


# 6. Palmer
def palmer():
    r = pd.read_csv(PROCESADOS / "ciegas_palmer_resultados.csv")
    dol = pd.read_csv(PROCESADOS / "ciegas_palmer_dolares.csv")
    difs = pd.read_csv(PROCESADOS / "ciegas_palmer_diferencias.csv").set_index("conjunto")
    conjuntos = [("nuevos", "Siete estados nuevos"), ("originales", "Iowa, Illinois e Indiana")]
    indices = [("Palmer", "Contrato con índice de sequía (Palmer)", NARANJA), ("Regla de lluvia", "Regla de lluvia", GRIS), ("Modelo", "Modelo", AZUL)]
    fig, ejes = plt.subplots(1, 4, figsize=(14, 4.6), facecolor=SUPERFICIE)
    medidas = [("auc", r, "Capacidad de distinguir", 2), ("heidke", r, "Aciertos sobre el azar", 2),
               ("pct_perdida_cubierta", dol, "Pérdida en dólares cubierta (%)", 0), ("de_cada_100", dol, "De cada $100, a quien perdió", 0)]
    for ax, (col, tabla, titulo, dec) in zip(ejes, medidas):
        for j, (ind, nombre, color) in enumerate(indices):
            v = [tabla[(tabla["conjunto"] == c) & (tabla["indice"] == ind)][col].iloc[0] for c, _ in conjuntos]
            x = np.arange(len(conjuntos)) + (j - 1) * 0.27
            ax.bar(x, v, width=0.26, color=color, zorder=3, label=nombre)
            for xi, vi in zip(x, v):
                ax.text(xi, vi, coma(vi, dec), ha="center", va="bottom", fontsize=7.5, color=TINTA)
        ax.set_xticks(range(len(conjuntos)), [n.replace(" e ", "\ne ") for _, n in conjuntos], fontsize=8)
        comun.estilo(ax)
        ax.set_title(titulo, loc="left", fontsize=10, color=TINTA)
    ejes[0].axhline(0.5, color=TINTA, linestyle="--", linewidth=1)
    fig.legend(*ejes[0].get_legend_handles_labels(), frameon=False, fontsize=8.5, loc="lower center", ncol=3, bbox_to_anchor=(0.5, 0.045))
    n = difs.loc["nuevos"]
    cerca = "queda cerca del modelo" if n["palmer_a_0_03_o_menos"] else "queda lejos del modelo"
    fig.suptitle(f"Contrato simple con el índice de sequía de Palmer: {cerca} (diferencia de {coma(n['auc_palmer_menos_modelo'])} en la primera medida, estados nuevos)",
                 x=0.01, ha="left", fontsize=11.5, color=TINTA)
    guardar(fig, "pitch_ciegas_palmer.png", "1991-2025, misma frecuencia de pago. Palmer: paga bajo el percentil 15 de los años anteriores del condado, hasta 100 % en el percentil 2. Modelo: prueba a ciegas.")


# 7. Dólares
def dolares():
    d = pd.read_csv(PROCESADOS / "ciegas_impacto_por_anio.csv").set_index("anio")
    fig, ax = plt.subplots(figsize=(12, 4.8), facecolor=SUPERFICIE)
    ax.bar(d.index, d["perdida_usd"] / 1e9, color=GRIS, width=0.8, zorder=3, label="Pérdida real de cosecha")
    ax.plot(d.index, d["indemnizacion"] / 1e9, color=AZUL, marker="o", ms=3.5, lw=1.5, zorder=4, label="Lo que pagó el seguro agrícola real (todas las causas)")
    ax.plot(d.index, d["modelo_usd"] / 1e9, color=NARANJA, marker="s", ms=3.5, lw=1.5, zorder=5, label="Lo que habría pagado el índice con el modelo")
    ax.plot(d.index, d["palmer_usd"] / 1e9, color=VERDE_OSC, marker="^", ms=3.5, lw=1.5, zorder=5, label="Lo que habría pagado el contrato con Palmer")
    for a in [1988, 2012]:
        if a in d.index:
            ax.text(a, d.loc[a, "perdida_usd"] / 1e9, f" {a}", fontsize=9, color=TINTA, va="bottom")
    comun.estilo(ax)
    ax.set_ylabel("Miles de millones de dólares de 2025", color=TINTA_2)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax.set_title("Diez estados: pérdida real, lo que pagó el seguro real y lo que habrían pagado el índice y el contrato con Palmer", loc="left", fontsize=11.5, color=TINTA)
    guardar(fig, "pitch_ciegas_dolares.png", "Maíz, diez estados. Pérdida con precio nacional de cada campaña (USDA). Seguro real: todos los planes y todas las causas, también la caída del precio. Suma asegurada de 100 %.")


# 8. De cada 100 y costo de administrarlo
def cada_100():
    s = pd.read_csv(PROCESADOS / "ciegas_impacto_simulacion.csv")
    c = pd.read_csv(PROCESADOS / "ciegas_impacto_costos.csv")
    s = s[(s["periodo"] == "1991-2025") & (s["grupo"] == "diez estados") & (s["suma_asegurada"].isna() | (s["suma_asegurada"] == 1.0))].set_index("disparador")
    nombres = [("Seguro real (RMA, todas las causas)", "Seguro real", AZUL), ("Modelo", "Índice con\nmodelo", NARANJA),
               ("Contrato Palmer", "Contrato\ncon Palmer", VERDE_OSC), ("Regla de lluvia (pago proporcional)", "Regla de\nlluvia", GRIS)]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.5, 4.8), facecolor=SUPERFICIE)
    v = [s.loc[k, "de_cada_100_pagados"] for k, _, _ in nombres]
    a1.bar(range(4), v, color=[col for _, _, col in nombres], width=0.6, zorder=3)
    for i, x in enumerate(v):
        a1.text(i, x + 1, f"${x:.0f}", ha="center", fontsize=11, color=TINTA)
    a1.set_xticks(range(4), [n for _, n, _ in nombres], fontsize=9)
    comun.estilo(a1)
    a1.set_title("De cada $100 que se pagan, cuántos llegan a quien perdió", loc="left", fontsize=10.5, color=TINTA)
    cc = c[(c["periodo"] == "1991-2025") & (c["grupo"] == "diez estados")]
    filas = [("Seguro real\n(costo de la ley:\n18,5 % de la prima)", cc[(cc["esquema"] == "Seguro real") & cc["supuesto"].str.contains("ley")]["costo_por_cada_100_que_llegan"].iloc[0], AZUL, False),
             ("Seguro real\n(costo implícito:\n12,8 % de la prima)", cc[(cc["esquema"] == "Seguro real") & cc["supuesto"].str.contains("implícito")]["costo_por_cada_100_que_llegan"].iloc[0], AZUL, False)]
    for nivel in [0.05, 0.10, 0.20]:
        x = cc[(cc["esquema"] == "Modelo") & np.isclose(cc["nivel"], nivel)]["costo_por_cada_100_que_llegan"].iloc[0]
        filas.append((f"Índice con\nmodelo\n(operar = {int(nivel * 100)} %,\nsupuesto)", x, NARANJA, True))
    for k, (nombre, x, color, supuesto) in enumerate(filas):
        a2.bar(k, x, color=color, width=0.6, zorder=3, hatch="//" if supuesto else None, edgecolor="white" if supuesto else None)
        a2.text(k, x + 0.3, f"${x:.0f}", ha="center", fontsize=10, color=TINTA)
    a2.set_xticks(range(len(filas)), [f[0] for f in filas], fontsize=7.5)
    comun.estilo(a2)
    a2.set_title("Cuánto cuesta administrarlo por cada $100 que llegan a quien perdió", loc="left", fontsize=10.5, color=TINTA)
    guardar(fig, "pitch_ciegas_cada_100.png", "Diez estados, 1991-2025. Rayado: costo de operar el índice, SUPUESTO (no medido). Seguro real: reembolso a las aseguradoras por administración y operación (GAO-17-501). "
            "El seguro real cubre más riesgos y paga por finca.")


def main():
    mapa_estados()
    modelo_nuevos()
    por_estado()
    semaforo_adelante()
    semaforo_mapa()
    palmer()
    dolares()
    cada_100()


if __name__ == "__main__":
    main()
