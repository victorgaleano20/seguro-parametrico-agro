"""
45_figuras_cierre.py
Figuras del cierre: seis figuras docs/figuras/pitch_cierre_*.png, con títulos en español sencillo y sin siglas.
No hace análisis nuevos: solo lee lo que dejaron 40 a 44.

Requiere 40, 41, 42, 43 y 44. Uso:  python scripts/45_figuras_cierre.py
"""
import importlib
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
f39 = importlib.import_module("39_figuras_ciegas")

PROCESADOS = RAIZ / "datos" / "procesados"
SUPERFICIE, TINTA, TINTA_2, REJILLA = f39.SUPERFICIE, f39.TINTA, f39.TINTA_2, f39.REJILLA
AZUL, NARANJA, GRIS, SEMAFORO = f39.AZUL, f39.NARANJA, f39.GRIS, f39.SEMAFORO
coma, guardar = f39.coma, f39.guardar
ESTADOS = f39.ESTADOS


def estilo(ax):
    ax.set_facecolor(SUPERFICIE)
    ax.grid(axis="y", color=REJILLA, linewidth=0.6)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)


# 1. Modelo con y sin ubicación
def fig_ubicacion():
    c = pd.read_csv(PROCESADOS / "cierre_ubicacion_comparacion.csv")
    modelos = ["Modelo original (con ubicación)", "Modelo sin ubicación", "Regla de lluvia"]
    colores = [AZUL, NARANJA, GRIS]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5.2), facecolor=SUPERFICIE, gridspec_kw={"width_ratios": [1, 1.7]})
    subs = [("todos", "Todos los años"), ("sin_2012", "Sin 2012"), ("1995_2025", "1995 a 2025")]
    for ax in (a1, a2):
        estilo(ax)
    for j, (m, col) in enumerate(zip(modelos, colores)):
        v = [c[(c["modelo"] == m) & (c["subconjunto"] == s)].iloc[0] for s, _ in subs]
        x = np.arange(len(subs)) + (j - 1) * 0.27
        a1.bar(x, [r["auc"] for r in v], 0.25, color=col, label=m,
               yerr=[[r["auc"] - r["auc_ic_inf"] for r in v], [r["auc_ic_sup"] - r["auc"] for r in v]], error_kw={"ecolor": TINTA_2, "lw": 0.8})
        for xi, r in zip(x, v):
            a1.text(xi, r["auc_ic_inf"] - 0.035, coma(r["auc"]), ha="center", fontsize=8, color="white" if r["auc_ic_inf"] > 0.45 else TINTA)
    a1.set_xticks(range(len(subs)), [n for _, n in subs])
    a1.axhline(0.5, color=TINTA_2, lw=0.8, ls="--")
    a1.set_ylim(0.3, 0.95)
    a1.set_ylabel("Acierto al ordenar años de pérdida (0,5 = azar)")
    a1.set_title("Los siete estados nuevos juntos", loc="left", fontsize=10, color=TINTA)
    a1.legend(frameon=False, fontsize=8, loc="upper left")
    estados = [e for e in ["Ohio", "Kansas", "Missouri", "South Dakota", "Nebraska", "Wisconsin", "Minnesota"]]
    for j, (m, col) in enumerate(zip(modelos, colores)):
        v = [c[(c["modelo"] == m) & (c["subconjunto"] == f"estado: {e}")].iloc[0]["auc"] for e in estados]
        a2.bar(np.arange(len(estados)) + (j - 1) * 0.27, v, 0.25, color=col)
    a2.set_xticks(range(len(estados)), estados, fontsize=9)
    a2.axhline(0.5, color=TINTA_2, lw=0.8, ls="--")
    a2.set_ylim(0.3, 0.95)
    a2.set_title("Por estado", loc="left", fontsize=10, color=TINTA)
    fig.suptitle("¿El modelo aprende clima o geografía? Mismo modelo con y sin la ubicación", x=0.01, ha="left", fontsize=12.5, color=TINTA)
    guardar(fig, "pitch_cierre_modelo_ubicacion.png", "Sin ubicación = sin latitud, longitud ni estado. Las barras finas son el margen de error al 95 % (remuestreando años completos).")


# 2. Calibración según los años locales
def fig_calibracion():
    cu = pd.read_csv(PROCESADOS / "cierre_calibracion_curva.csv")
    br = pd.read_csv(PROCESADOS / "cierre_calibracion_brier.csv")
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.5, 5.2), facecolor=SUPERFICIE)
    estilo(a1), estilo(a2)
    paleta = {0: "#b8b7b1", 3: "#8fb8ea", 5: "#5b9ae0", 10: "#2a78d6", 15: "#0b3d7a"}
    for k, g in cu.groupby("K"):
        a1.plot(g["prob_media"] * 100, g["perdida_observada"] * 100, marker="o", ms=4, lw=1.4, color=paleta[k], label="Sin años locales" if k == 0 else f"{k} años locales")
    mx = 45
    a1.plot([0, mx], [0, mx], color=TINTA_2, ls="--", lw=0.9)
    a1.set_xlim(0, mx), a1.set_ylim(0, mx)
    a1.set_xlabel("Probabilidad de pérdida que da el modelo (%)")
    a1.set_ylabel("Pérdidas que realmente ocurrieron (%)")
    a1.set_title("Curva de calibración, siete estados, 2006 a 2025", loc="left", fontsize=10, color=TINTA)
    a1.legend(frameon=False, fontsize=8, loc="upper left")
    a1.text(mx * 0.97, mx * 0.88, "línea ideal", rotation=38, fontsize=8, color=TINTA_2, ha="right")
    por = br[br["estado"] != "siete estados juntos"].groupby("K")["mejor_que_tasa_media"].sum().astype(int)
    a2.bar([str(k) for k in por.index], por.values, color=[paleta[k] for k in por.index])
    for i, v in enumerate(por.values):
        a2.text(i, v + 0.1, str(v), ha="center", fontsize=10, color=TINTA)
    a2.axhline(5, color=NARANJA, lw=1.2, ls="--")
    a2.text(-0.4, 5.15, "meta: 5 de 7", color=NARANJA, fontsize=9)
    a2.set_ylim(0, 7.5)
    a2.set_xlabel("Años locales usados para recalibrar")
    a2.set_ylabel("Estados donde la probabilidad supera a la tasa media")
    a2.set_title("Estados (de 7) con mejor Brier que la tasa media", loc="left", fontsize=10, color=TINTA)
    fig.suptitle("¿Cuántos años locales hacen falta para confiar en las probabilidades de un estado nuevo?", x=0.01, ha="left", fontsize=12.5, color=TINTA)
    guardar(fig, "pitch_cierre_calibracion_anios_locales.png", "Se recalibra con los primeros años de cada estado y se evalúa siempre en 2006-2025. La tasa media es el promedio de pérdidas de ese estado en esos años.")


# 3. Palmer con y sin topes
def fig_palmer():
    a = pd.read_csv(PROCESADOS / "cierre_palmer_topes_por_anio.csv")
    fig, axs = plt.subplots(1, 2, figsize=(13, 5.3), facecolor=SUPERFICIE, sharey=True)
    for ax, suma in zip(axs, [0.5, 0.75]):
        estilo(ax)
        g = a[(a["suma_asegurada"] == suma) & (a["disparador"] == "Contrato Palmer")].sort_values("anio")
        m = a[(a["suma_asegurada"] == suma) & (a["disparador"] == "Modelo")].sort_values("anio")
        ax.bar(g["anio"], g["perdida_real_usd"] / 1e9, color=GRIS, width=0.8, label="Pérdida real")
        ax.plot(g["anio"], g["pago_sin_tope_usd"] / 1e9, color=NARANJA, lw=1.5, marker="o", ms=3, label="Palmer sin tope")
        ax.plot(g["anio"], g["pago_con_tope_usd"] / 1e9, color=AZUL, lw=1.8, marker="o", ms=3, label="Palmer con tope")
        ax.plot(m["anio"], m["pago_con_tope_usd"] / 1e9, color="#1baf7a", lw=1.2, ls="--", label="Modelo (con el mismo tope)")
        ax.axhline(g["tope_anual_usd"].iloc[0] / 1e9, color=AZUL, lw=0.8, ls=":")
        ax.text(1991, g["tope_anual_usd"].iloc[0] / 1e9 + 0.8, "tope anual", color=AZUL, fontsize=8)
        ax.set_title(f"Suma asegurada de {int(suma * 100)} % del valor esperado", loc="left", fontsize=10, color=TINTA)
        ax.set_xlabel("Año")
    axs[0].set_ylabel("Miles de millones de dólares de 2025, diez estados")
    axs[0].legend(frameon=False, fontsize=8.5, loc="upper left")
    fig.suptitle("Contrato con el índice de sequía de Palmer, con y sin tope, año por año", x=0.01, ha="left", fontsize=12.5, color=TINTA)
    guardar(fig, "pitch_cierre_palmer_topes.png", "El tope es 2 veces el pago promedio por año del mismo contrato sin tope. Cuando un año lo pasa, todos los pagos de ese año bajan en la misma proporción.")


# 4. Causas de los siniestros por estado
def fig_causas():
    pe = pd.read_csv(PROCESADOS / "cierre_causas_por_estado.csv").set_index("estado")
    grupos = ["sequia", "humedad", "frio", "granizo", "precio", "otras"]
    nombres = {"sequia": "Sequía", "humedad": "Exceso de humedad", "frio": "Heladas o frío", "granizo": "Granizo", "precio": "Caída de precio", "otras": "Otras"}
    colores = {"sequia": NARANJA, "humedad": AZUL, "frio": "#8fb8ea", "granizo": "#7d6bd6", "precio": "#e8b00f", "otras": GRIS}
    pe = pe.sort_values("parte_sequia")
    fig, ax = plt.subplots(figsize=(11, 5.8), facecolor=SUPERFICIE)
    ax.set_facecolor(SUPERFICIE)
    izq = np.zeros(len(pe))
    for g in grupos:
        v = pe[f"parte_{g}"].to_numpy() * 100
        ax.barh(pe.index, v, left=izq, color=colores[g], label=nombres[g], height=0.7)
        for i, (x0, w) in enumerate(zip(izq, v)):
            if w >= 7:
                ax.text(x0 + w / 2, i, f"{w:.0f}".replace(".", ","), ha="center", va="center", fontsize=8, color="white")
        izq += v
    for lab in ax.get_yticklabels():
        if lab.get_text() == "Minnesota":
            lab.set_fontweight("bold"), lab.set_color(NARANJA)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Parte de lo pagado en indemnizaciones de maíz, 1989 a 2025 (%)")
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    ax.legend(frameon=False, ncol=6, fontsize=8.5, loc="upper center", bbox_to_anchor=(0.5, 1.09))
    fig.suptitle("¿Por qué se pagan los siniestros del maíz en cada estado?", x=0.01, ha="left", fontsize=12.5, color=TINTA)
    guardar(fig, "pitch_cierre_causas_estado.png", "Seguro real de maíz, dólares de 2025. Minnesota es el estado donde la sequía pesa menos y el exceso de humedad más.")


# 5. Semáforo por causa en años de prueba: verdes frente a rojos
def fig_semaforo_causa():
    pc = pd.read_csv(PROCESADOS / "cierre_semaforo_causa_resultados.csv")
    lado = pd.read_csv(PROCESADOS / "cierre_semaforo_lado_a_lado.csv")
    s36 = pd.read_csv(PROCESADOS / "ciegas_semaforo_resultados.csv")
    s36 = s36[(s36["prueba"] == "prueba 1: hacia adelante, 10 estados") & (s36["variante"] == "regla base") & (s36["indice"] == "modelo")]
    causa = pc[(pc["prueba"] == "causa, 1999-2025 (principal)") & (pc["indice"] == "modelo")]
    metricas = [("heidke", "Acierto descontando el azar", "{:.2f}"), ("pct_perdidas_captadas", "Pérdidas captadas (%)", "{:.0f}"),
                ("de_cada_100", "De cada $100, a quien perdió", "${:.0f}")]
    etiquetas = {"Semáforo de 36 (calidad y sensibilidad), 2006-2025": "Semáforo de calidad\ny sensibilidad\n(2006-2025)",
                 "Semáforo por causa, 1999-2025": "Semáforo por causa\n(1999-2025)"}
    fig, axs = plt.subplots(1, 3, figsize=(13, 6.2), facecolor=SUPERFICIE)
    for ax, (k, titulo, fmt) in zip(axs, metricas):
        estilo(ax)
        for i, (fuente, nombre) in enumerate([(s36, "Semáforo de 36 (calidad y sensibilidad), 2006-2025"), (causa, "Semáforo por causa, 1999-2025")]):
            v, r = fuente[fuente["color"] == "verde"][k].iloc[0], fuente[fuente["color"] == "rojo"][k].iloc[0]
            ax.bar(i - 0.17, v, 0.32, color=SEMAFORO["verde"], label="Verdes" if i == 0 else None)
            ax.bar(i + 0.17, r, 0.32, color=SEMAFORO["rojo"], label="Rojos" if i == 0 else None)
            ax.text(i - 0.17, v, fmt.format(v).replace(".", ","), ha="center", va="bottom", fontsize=8.5)
            ax.text(i + 0.17, r, fmt.format(r).replace(".", ","), ha="center", va="bottom", fontsize=8.5)
            d = lado[(lado["semaforo"] == nombre) & (lado["metrica"] == k)].iloc[0]
            ax.text(i, -0.30, (f"Diferencia {fmt.format(d['diferencia']).replace('.', ',')}\n({fmt.format(d['ic_inf']).replace('.', ',')} a {fmt.format(d['ic_sup']).replace('.', ',')})\n" +
                    ("excluye el cero" if d["excluye_cero"] else "incluye el cero")).replace("$", r"\$"), ha="center", va="top", fontsize=8, color=TINTA_2, transform=ax.get_xaxis_transform())
        ax.set_xticks([0, 1], [etiquetas["Semáforo de 36 (calidad y sensibilidad), 2006-2025"], etiquetas["Semáforo por causa, 1999-2025"]], fontsize=8.5)
        ax.tick_params(axis="x", pad=4)
        ax.set_title(titulo, loc="left", fontsize=10, color=TINTA)
        ax.set_ylim(0, ax.get_ylim()[1] * 1.12)
    axs[0].legend(frameon=False, fontsize=9, loc="upper left")
    fig.suptitle("Semáforo por causa en años de prueba: los verdes frente a los rojos", x=0.01, ha="left", fontsize=12.5, color=TINTA)
    guardar(fig, "pitch_cierre_semaforo_causa_prueba.png", "Cada año los colores usan solo años anteriores. El margen de error es al 95 % (remuestreando años completos); para que el semáforo se sostenga no debe incluir el cero.")


# 6. Mapa del semáforo por causa
def fig_mapa_causa():
    c = pd.read_csv(PROCESADOS / "cierre_semaforo_causa_colores.csv", dtype={"unidad": str})
    c = c[c["anio"] == c["anio"].max()]
    g = f39.estados_geo()
    g["unidad"] = g["GEOID"]
    g = g.merge(c[["unidad", "color_causa"]], on="unidad", how="left")
    fig, ax = plt.subplots(figsize=(10.5, 6.2), facecolor=SUPERFICIE)
    g["col"] = g["color_causa"].map(SEMAFORO).fillna("#e6e5e0")
    g.plot(ax=ax, color=g["col"], edgecolor="white", linewidth=0.2)
    g.dissolve("STATEFP").boundary.plot(ax=ax, color=TINTA, linewidth=0.8)
    ax.set_axis_off()
    n = c["color_causa"].value_counts()
    ax.legend(handles=[Patch(color=SEMAFORO["verde"], label=f"Verde: más parte de sus siniestros por sequía ({n.get('verde', 0)} condados)"),
                       Patch(color=SEMAFORO["amarillo"], label=f"Amarillo: en medio ({n.get('amarillo', 0)})"),
                       Patch(color=SEMAFORO["rojo"], label=f"Rojo: menos sequía o pocos años de datos ({n.get('rojo', 0)})"),
                       Patch(color="#e6e5e0", label="Sin dato de maíz")], frameon=False, fontsize=8.5, loc="lower left")
    ax.set_title(f"Semáforo por causa de los siniestros, colores de {int(c['anio'].max())}", loc="left", fontsize=12, color=TINTA)
    guardar(fig, "pitch_cierre_semaforo_causa_mapa.png", "El semáforo todavía no está probado: los verdes salen mejor, pero el margen de error incluye el cero.")


def main():
    f39.FIGURAS.mkdir(parents=True, exist_ok=True)
    for f in (fig_ubicacion, fig_calibracion, fig_palmer, fig_causas, fig_semaforo_causa, fig_mapa_causa):
        f()


if __name__ == "__main__":
    main()
