"""
app_comun.py
Datos, colores y cálculos que comparten las páginas de la app (app.py y paginas/).
La app no entrena nada: lee tablas de datos/procesados (scripts 50, 53 y 54).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
from sklearn.metrics import roc_auc_score

RAIZ = Path(__file__).resolve().parent
PROCESADOS = RAIZ / "datos" / "procesados"

# Colores por puntaje: siempre el mismo color para el mismo disparador (paleta validada de la guía de visualización)
COLORES = {"prob": "#2a78d6", "ref_calor": "#eb6834", "ref_regla": "#1baf7a", "azar": "#8a8984"}
NOMBRES = {"prob": "Modelo final", "ref_calor": "Índice de calor", "ref_regla": "Regla de lluvia", "azar": "Azar"}
NOMBRES_LARGOS = {"prob": "Modelo final (logística con splines)", "ref_calor": "Índice de calor de julio y agosto",
                  "ref_regla": "Regla de lluvia de junio a agosto", "azar": "Pagar al azar"}
PUNTAJES = ["prob", "ref_calor", "ref_regla"]
GRIS_SUAVE, TINTA_2 = "#c3c2b7", "#52514e"

GRUPOS = {"siete": "Siete estados nuevos", "tres": "Tres estados originales", "diez": "Diez estados"}
PERIODOS = {"todo": "1991-2025", "sin_2012": "Sin 2012", "seleccion": "1991-2010", "confirmacion": "2011-2025"}
MIN_PERDIDAS_ANIO = 10

AVISO_GRUPO = {
    "siete": "Los años 1991-2010 de estos siete estados se usaron para escoger entre 10 modelos. "
             "La cifra más limpia es la de **2011-2025**, que no se usó para escoger.",
    "tres": "Iowa, Illinois e Indiana se usaron para desarrollar todo el proyecto: aquí cada año se predice solo con años "
            "anteriores, pero no es una prueba a ciegas.",
    "diez": "Mezcla los tres estados de desarrollo con los siete de la prueba a ciegas.",
}


# ---------------------------------------------------------------- datos
@st.cache_data
def predicciones():
    """Modelo final año por año (script 53): entrenado solo con Iowa, Illinois e Indiana y años anteriores."""
    d = pd.read_csv(PROCESADOS / "modelo_final_predicciones.csv", dtype={"unidad": str, "grupo": str})
    d["y"] = d["y"].astype(bool)
    d["pago_regla"] = d["pago_regla"].astype(bool)
    nombres = pd.read_csv(PROCESADOS / "eeuu_ciegas_app.csv", dtype={"unidad": str}).groupby("unidad").agg(
        condado=("nombre", "first"), sigla=("nombre_grupo", "first"), latitud=("latitud", "first"), longitud=("longitud", "first"))
    return d.merge(nombres, left_on="unidad", right_index=True, how="left")


@st.cache_data
def tabla(nombre):
    return pd.read_csv(PROCESADOS / nombre)


@st.cache_data
def leer_json(nombre):
    return json.loads((PROCESADOS / nombre).read_text(encoding="utf-8"))


def filtrar(d, grupo, periodo="todo"):
    """Mismo filtro que 54_tablas_app.py."""
    g = d if grupo == "diez" else d[d["nuevo"] == (grupo == "siete")]
    if periodo == "sin_2012":
        return g[g["anio"] != 2012]
    if periodo == "seleccion":
        return g[g["anio"] <= 2010]
    if periodo == "confirmacion":
        return g[g["anio"] > 2010]
    return g


# ---------------------------------------------------------------- métricas
def auc(y, s):
    return roc_auc_score(y, s) if 0 < np.sum(y) < len(y) else np.nan


def auc_por_anio(g, puntajes=PUNTAJES):
    filas = []
    for anio, a in g.groupby("anio"):
        fila = {"anio": anio, "filas": len(a), "perdidas": int(a["y"].sum())}
        for k in puntajes:
            fila[k] = auc(a["y"], a[k])
        filas.append(fila)
    return pd.DataFrame(filas)


def auc_dentro(g, k):
    pa = auc_por_anio(g, [k])
    ok = (pa["perdidas"] >= MIN_PERDIDAS_ANIO) & pa[k].notna()
    return np.average(pa.loc[ok, k], weights=pa.loc[ok, "perdidas"]) if ok.any() else np.nan


def heidke(perdida, pago):
    a = int((perdida & pago).sum())
    b = int((~perdida & pago).sum())
    c = int((perdida & ~pago).sum())
    d = len(perdida) - a - b - c
    den = (a + c) * (c + d) + (a + b) * (b + d)
    return 2 * (a * d - b * c) / den if den else np.nan


def pagar_los_mas_altos(puntaje, frecuencia):
    """Paga en los condado-años de puntaje más alto, tantos como frecuencia x filas (como comun.pagar_igual_que_regla)."""
    orden = np.argsort(-np.asarray(puntaje), kind="stable")
    pago = np.zeros(len(orden), dtype=bool)
    pago[orden[:int(round(frecuencia * len(orden)))]] = True
    return pago


def pagos(g, frecuencia):
    """Qué condado-años paga cada disparador, todos con la misma frecuencia. La regla usa su umbral pactado si la frecuencia es la suya."""
    regla_pactada = np.isclose(frecuencia, g["pago_regla"].mean())
    return {"prob": pagar_los_mas_altos(g["prob"], frecuencia),
            "ref_calor": pagar_los_mas_altos(g["ref_calor"], frecuencia),
            "ref_regla": g["pago_regla"].to_numpy() if regla_pactada else pagar_los_mas_altos(g["ref_regla"], frecuencia)}


def contrato(g, frecuencia):
    """Resultados en dólares y en aciertos de cada disparador (como 53: monto = valor esperado x tamaño medio previo)."""
    y = g["y"].to_numpy()
    potencial = (g["valor_esperado_usd"] * g["severidad_media_previa"]).to_numpy()
    perdida = g["perdida_usd"].to_numpy()
    n_anios = g["anio"].nunique()
    filas, por_anio = [], []
    for k, paga in pagos(g, frecuencia).items():
        pago = potencial * paga
        a, b = int((y & paga).sum()), int((~y & paga).sum())
        c = int((y & ~paga).sum())
        anual = pd.Series(pago).groupby(g["anio"].to_numpy()).sum()
        filas.append({"clave": k, "disparador": NOMBRES[k], "pagos": int(paga.sum()), "pagos_usd": pago.sum(),
                      "de_cada_100": 100 * pago[y].sum() / pago.sum() if pago.sum() else np.nan,
                      "perdida_cubierta": 100 * np.minimum(pago, perdida).sum() / perdida.sum(),
                      "perdidas_sin_pago": 100 * c / (a + c) if a + c else np.nan,
                      "pagos_sin_perdida": 100 * b / (a + b) if a + b else np.nan,
                      "heidke": heidke(y, paga), "prima_pura": pago.sum() / n_anios,
                      "peor_anio": anual.max(), "peor_anio_veces": anual.max() / (pago.sum() / n_anios) if pago.sum() else np.nan,
                      "a": a, "b": b, "c": c, "d": len(y) - a - b - c})
        por_anio.append(pd.DataFrame({"anio": g["anio"].to_numpy(), "clave": k, "con_perdida": pago * y, "sin_perdida": pago * ~y}))
    filas.append({"clave": "azar", "disparador": NOMBRES["azar"], "de_cada_100": 100 * potencial[y].sum() / potencial.sum(),
                  "heidke": 0.0})
    anual = pd.concat(por_anio).groupby(["clave", "anio"])[["con_perdida", "sin_perdida"]].sum().reset_index()
    real = g.groupby("anio")["perdida_usd"].sum().rename("perdida_real").reset_index()
    return pd.DataFrame(filas), anual.merge(real, on="anio")


def veredicto(dif):
    """Lee la distribución de la diferencia (modelo menos referencia): supera solo si el rango de 95 % no incluye el cero."""
    inf, sup = np.nanpercentile(dif, [2.5, 97.5])
    no_gana = float(np.nanmean(dif <= 0))
    estado = "supera" if inf > 0 else ("queda por debajo" if sup < 0 else "no se distingue")
    return estado, inf, sup, no_gana


# ---------------------------------------------------------------- formato
def num(x, dec=3):
    return "–" if pd.isna(x) else f"{x:,.{dec}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def entero(n):
    return f"{int(n):,}".replace(",", ".")


def signo(x, dec=3):
    return ("+" if x > 0 else "−" if x < 0 else "") + num(abs(x), dec)


def millones(x):
    return f"US${num(x / 1e6, 0)} millones"


def estilo(fig, alto=380, leyenda=True):
    fig.update_layout(height=alto, margin=dict(l=10, r=10, t=30, b=10), showlegend=leyenda,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title=None),
                      hoverlabel=dict(namelength=-1), separators=",.")
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.18)", zeroline=False)
    return fig


def selector(etiqueta, opciones, defecto, clave):
    """Control segmentado que nunca devuelve None."""
    v = st.segmented_control(etiqueta, list(opciones), format_func=opciones.get, default=defecto, key=clave)
    return v or defecto
