"""
app.py - Simulador del seguro paramétrico de sequía para el maíz de EE. UU. (diez estados, 1991-2025).

Solo LEE tablas ya calculadas en datos/procesados (no entrena nada ni usa MLflow): eeuu_ciegas_app.csv, ciegas_impacto_*.csv,
ciegas_semaforo_*.csv y cierre_* (scripts 34 a 44), y modelo_final_predicciones.csv (script 53: probabilidad del modelo final). Las tablas opcionales (cierre_*) pueden faltar sin que la app falle. Todas las rutas son relativas a este archivo.
Uso, desde la carpeta del proyecto:
    streamlit run app.py
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import streamlit as st

PROCESADOS = Path(__file__).resolve().parent / "datos" / "procesados"
AZUL, NARANJA, TINTA, TINTA_2, REJILLA = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#e4e3df"

st.set_page_config(page_title="Simulador de seguro paramétrico", layout="wide")


@st.cache_data
def cargar(nombre, codigo):
    return pd.read_csv(PROCESADOS / nombre, dtype={codigo: str})


def hay(nombre):
    return (PROCESADOS / nombre).exists()


def leer_opcional(nombre, columnas):
    """Lee una tabla opcional; si no existe devuelve None (o las columnas pedidas si existe)."""
    if not hay(nombre):
        return None
    d = pd.read_csv(PROCESADOS / nombre, dtype={"unidad": str})
    return d if columnas is None else d[columnas]


def leer_json(nombre):
    ruta = PROCESADOS / nombre
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else None


def dolares(x):
    return f"US${x:,.0f}"


@st.cache_data
def cargar_eeuu():
    # Diez estados: tres de entrenamiento y siete de la prueba a ciegas (scripts 34 a 38)
    d = pd.read_csv(PROCESADOS / "ciegas_impacto_detalle.csv", dtype={"unidad": str})
    b = pd.read_csv(PROCESADOS / "eeuu_ciegas_app.csv", dtype={"unidad": str})[["unidad", "anio", "nombre", "nombre_grupo", "lluvia_jun_ago_mm"]]
    d = d.merge(b, on=["unidad", "anio"], how="left")
    # Tablas opcionales: si faltan, la pestaña sigue funcionando sin esa parte
    d = d.merge(leer_opcional("ciegas_impacto_rma_condado_anio.csv", ["unidad", "anio", "indemnizacion", "indemnizacion_sequia"]),
                on=["unidad", "anio"], how="left") if hay("ciegas_impacto_rma_condado_anio.csv") else d.assign(indemnizacion=0.0, indemnizacion_sequia=0.0)
    topes = leer_opcional("cierre_palmer_topes_por_anio.csv", None)
    if topes is not None:
        f = topes[(topes["disparador"] == "Contrato Palmer") & (topes["suma_asegurada"] == 0.75)][["anio", "factor_tope"]]   # el factor no depende de la suma
        d = d.merge(f, on="anio", how="left")
    else:
        d["factor_tope"] = float("nan")
    for c in ["perdida", "pago_regla", "pago_umbral"]:
        d[c] = d[c].astype(bool)
    d["lluvia_pct_normal"] = -100 * d["puntaje_regla"]
    # Modelo final (script 53): logística con splines sobre clima frente a lo normal, entrenada solo con años anteriores
    # y con Iowa, Illinois e Indiana; reemplaza a la probabilidad y al tamaño de pérdida del LightGBM anterior
    f = pd.read_csv(PROCESADOS / "modelo_final_predicciones.csv", dtype={"unidad": str})[["unidad", "anio", "prob", "ref_calor", "severidad_media_previa"]]
    d = d.drop(columns=["prob", "prob_calibrada", "umbral_prob", "severidad_prevista"], errors="ignore").merge(f, on=["unidad", "anio"], how="inner")
    frecuencia = d["pago_regla"].mean()
    d["umbral_prob"] = d["prob"].quantile(1 - frecuencia)          # el modelo paga con la misma frecuencia que la regla
    d["umbral_calor"] = d["ref_calor"].quantile(1 - frecuencia)
    return d.sort_values(["unidad", "anio"])


ESTADOS_EEUU = {"IA": "Iowa", "IL": "Illinois", "IN": "Indiana", "NE": "Nebraska (prueba a ciegas)", "MN": "Minnesota (prueba a ciegas)",
                "OH": "Ohio (prueba a ciegas)", "MO": "Missouri (prueba a ciegas)", "KS": "Kansas (prueba a ciegas)",
                "SD": "South Dakota (prueba a ciegas)", "WI": "Wisconsin (prueba a ciegas)"}


def elegir_condado(us, clave):
    nombres = ESTADOS_EEUU
    c1, c2 = st.columns(2)
    est = c1.selectbox("Estado", sorted(us["nombre_grupo"].unique(), key=lambda e: (e not in ("IA", "IL", "IN"), nombres[e])), format_func=nombres.get, key=f"{clave}_est")
    cond = c2.selectbox("Condado", sorted(us.loc[us["nombre_grupo"] == est, "nombre"].dropna().unique()), key=f"{clave}_cond")
    return us[(us["nombre_grupo"] == est) & (us["nombre"] == cond)].sort_values("anio")


def ejes_limpios(*ejes):
    for ax in ejes:
        ax.grid(axis="y", color=REJILLA, linewidth=0.7, zorder=0)
        for lado in ("top", "right"):
            ax.spines[lado].set_visible(False)


st.title("Simulador de seguro paramétrico de sequía")
st.caption("El seguro paga automáticamente cuando el clima del verano anticipa una mala cosecha, sin visitar la finca. "
           "Compara los años en que habría pagado con los años en que de verdad se perdió la cosecha de maíz en Estados Unidos.")
(tab_us_riesgo, tab_us_semaforo, tab_us_seguro) = st.tabs(
    ["Riesgo por condado", "Semáforo de condados", "Simular el seguro"])

# ---------------------------------------------------------------- EE. UU.: riesgo por condado
with tab_us_riesgo:
    us = cargar_eeuu()
    d = elegir_condado(us, "riesgo")
    st.caption("Modelo final: logística con curvas suaves sobre el clima del verano frente a lo normal. Cada probabilidad sale de un modelo "
               "entrenado solo con años anteriores y solo con Iowa, Illinois e Indiana (en los otros siete estados es una predicción a ciegas).")
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 5), sharex=True)
    a1.bar(d["anio"], d["lluvia_jun_ago_mm"], color=[NARANJA if p_ else AZUL for p_ in d["pago_regla"]], width=0.7, zorder=3)
    a1.set_ylabel("Lluvia de junio a agosto (mm)", color=TINTA_2)
    a1.legend(handles=[Patch(color=NARANJA, label="La regla de lluvia habría pagado"), Patch(color=AZUL, label="La regla no paga")], frameon=False, fontsize=8)
    a2.bar(d["anio"], 100 * d["prob"], color=[NARANJA if f else REJILLA for f in d["perdida"]], width=0.7, zorder=3)
    a2.set_ylabel("Probabilidad de pérdida (%)", color=TINTA_2)
    a2.legend(handles=[Patch(color=NARANJA, label="Año con pérdida real"), Patch(color=REJILLA, label="Año sin pérdida")], frameon=False, fontsize=8)
    ejes_limpios(a1, a2)
    fig.tight_layout()
    st.pyplot(fig)
    st.caption("Pérdida: rendimiento de 80 % o menos de lo esperado por la tendencia de los años anteriores (NASS). Lluvia: CHIRPS.")
    with st.expander("Ver la tabla año por año"):
        st.dataframe(d[["anio", "lluvia_jun_ago_mm", "lluvia_pct_normal", "prob", "perdida", "pago_regla"]], hide_index=True)
    st.caption("La probabilidad no está calibrada: sirve sobre todo para ordenar el riesgo. En los estados nuevos, cuando dice 60 % la pérdida ocurrió cerca de 38 % de las veces.")

# ---------------------------------------------------------------- Semáforo de condados
with tab_us_semaforo:
    # Colores de 2025, calculados solo con datos hasta 2024, para los diez estados (scripts 36 y 44)
    crit36 = leer_json("ciegas_semaforo_criterio.json")
    critc = leer_json("cierre_semaforo_causa_criterio.json")
    sem36 = leer_opcional("ciegas_semaforo_colores_adelante.csv", None)
    semc = leer_opcional("cierre_semaforo_causa_colores.csv", None)
    cumple36 = bool(crit36 and crit36["prueba 1: hacia adelante, 10 estados | regla base"]["cumple"])
    cumplec = bool(critc and critc.get("semaforo_causa_cumple"))
    opciones = {}
    if sem36 is not None:
        opciones["Calidad del dato y sensibilidad al clima"] = ("color_base", sem36[sem36["anio"] == sem36["anio"].max()], cumple36)
    if semc is not None:
        opciones["Por causa de los siniestros (parte pagada por sequía)"] = ("color_causa", semc[semc["anio"] == semc["anio"].max()], cumplec)
    if not opciones:
        st.info("No hay tablas del semáforo en datos/procesados.")
    else:
        nombres = sorted(opciones, key=lambda n: not opciones[n][2])          # el que cumplió el criterio va primero
        if not any(o[2] for o in opciones.values()):
            st.warning("**El semáforo todavía no está probado:** los condados verdes salen mejor, pero el margen de error incluye el cero.")
        else:
            st.success("Hay un semáforo que cumplió el criterio fijado de antemano; es la primera opción.")
        eleccion = st.radio("Semáforo", nombres, horizontal=True, key="sem_eleccion")
        columna, sem, cumple = opciones[eleccion]
        ub = cargar("eeuu_ciegas_app.csv", "unidad").groupby("unidad").agg(
            estado=("nombre_grupo", "first"), condado=("nombre", "first"), latitud=("latitud", "first"), longitud=("longitud", "first")).reset_index()
        sem = sem.merge(ub, on="unidad", how="left")
        st.markdown("**Pruebas con pérdidas (criterio fijado de antemano: verdes mejores que rojos en las tres medidas, con rango de 95 % sin el cero):**")
        if crit36:
            for etiqueta, clave in [("Calidad y sensibilidad, año por año, diez estados (2006 a 2025)", "prueba 1: hacia adelante, 10 estados | regla base"),
                                    ("Calidad y sensibilidad, estados nuevos con datos hasta 2018, probados en 2019 a 2025", "prueba 2: nuevos hasta 2018 y 2019-2025 | regla base")]:
                ok = crit36[clave]["cumple"]
                (st.success if ok else st.warning)(f"{etiqueta}: " + ("los verdes salieron mejor que los rojos." if ok else "los verdes no salieron claramente mejor que los rojos."))
        if critc:
            (st.success if cumplec else st.warning)("Por causa, año por año, diez estados (1999 a 2025): " +
                                                    ("los verdes salieron mejor que los rojos." if cumplec else "los verdes no salieron claramente mejor que los rojos."))
        st.caption("Detalle: docs/resultados_prueba_ciegas.md y docs/resultados_cierre.md.")
        estados = st.multiselect("Estados", sorted(sem["estado"].dropna().unique()), default=sorted(sem["estado"].dropna().unique()), key="sem_estados",
                                 format_func=lambda e: ESTADOS_EEUU.get(e, e))
        v = sem[sem["estado"].isin(estados)]
        colores = {"verde": "#1baf7a", "amarillo": "#e8b00f", "rojo": "#d64b3a"}
        fig, ax = plt.subplots(figsize=(9, 5))
        for c, g in v.dropna(subset=["latitud"]).groupby(columna):
            ax.scatter(g["longitud"], g["latitud"], color=colores[c], s=14, label=f"{c.capitalize()} ({len(g)})", zorder=3)
        ax.set_aspect(1.3)
        ax.set_xlabel("Longitud", color=TINTA_2)
        ax.set_ylabel("Latitud", color=TINTA_2)
        ax.legend(frameon=False, fontsize=8)
        ejes_limpios(ax)
        st.pyplot(fig)
        if columna == "color_causa":
            st.caption("Un punto por condado, en su centro. Verde: de sus indemnizaciones de maíz anteriores, una parte alta fue por sequía. "
                       "Rojo: parte baja, pocos años con siniestros o dato dudoso.")
            tabla = v[["estado", "condado", "color_causa", "parte_sequia", "anios_con_siniestros"]].rename(columns={"color_causa": "color", "anios_con_siniestros": "años con siniestros"})
        else:
            st.caption("Un punto por condado, en su centro. Verde: dato bueno y la cosecha responde mucho al clima del verano. "
                       "Rojo: dato dudoso o responde poco. La columna de riego muestra la parte del maíz con riego (censos agropecuarios).")
            tabla = v[["estado", "condado", "color_base", "color_riego", "riego"]].rename(columns={"color_base": "color", "color_riego": "color si se pone rojo el mucho riego"})
        st.dataframe(tabla.sort_values(["estado", "condado"]), hide_index=True)

# ---------------------------------------------------------------- Simular el seguro en EE. UU.
with tab_us_seguro:
    us = cargar_eeuu()
    resumen_us = json.loads((PROCESADOS / "ciegas_impacto_resumen.json").read_text(encoding="utf-8"))
    resumen_us["subsidio_real"] = resumen_us["subsidio_real_2014_2018"]["diez estados"]
    resumen_us["periodo_subsidio"] = [2014, 2018]
    d = elegir_condado(us, "seguro").copy()
    valor_acre = (d["valor_esperado_usd"] / d["area_cosechada_acres"]).mean()
    c1, c2, c3 = st.columns(3)
    hay_topes = bool(d["factor_tope"].notna().any())
    disparador = c1.selectbox("Disparador", ["Regla de lluvia", "Modelo", "Índice de calor", "Contrato Palmer"] + (["Contrato Palmer con topes"] if hay_topes else []), key="us_disp")
    sugerida = valor_acre * (0.75 if disparador == "Contrato Palmer con topes" else 1.0)
    suma_acre = c2.number_input("Suma asegurada por acre (US$)", min_value=50, max_value=2000, value=int(round(sugerida, -1)), step=10, key=f"us_suma_{disparador}")
    if disparador == "Contrato Palmer con topes":
        c3.caption("Igual que el contrato Palmer, con suma asegurada de 50 % a 75 % del valor esperado y un tope de pago por año en los diez estados "
                   "(2 veces la prima pura anual). Si un año se pasa del tope, todos los pagos de ese año bajan en la misma proporción. "
                   "Este contrato todavía no se considera vendible: docs/resultados_cierre.md.")
        paga = d["fraccion_palmer"] * d["factor_tope"].fillna(1.0) > 0
    elif disparador == "Contrato Palmer":
        c3.caption("Paga si el índice de Palmer de julio y agosto queda bajo el percentil 15 de los años anteriores del condado: "
                   "0 % de la suma en el percentil 15 y 100 % en el percentil 2, en línea recta.")
        paga = d["fraccion_palmer"] > 0
    elif disparador == "Modelo":
        umbral = c3.slider("Umbral de pago: probabilidad de pérdida", 0.05, 0.95, float(round(d["umbral_prob"].median(), 2)), 0.01, key="us_umbral_prob")
        paga = d["prob"] >= umbral
    elif disparador == "Índice de calor":
        c3.caption("Paga si la temperatura máxima de julio y agosto, frente a lo normal del condado, queda en el mismo porcentaje "
                   "más caluroso de los años en que paga la regla de lluvia en los diez estados.")
        paga = d["ref_calor"] >= d["umbral_calor"]
    elif c3.checkbox("Usar el umbral pactado (lluvia bajo el percentil 15 del condado)", value=True, key="us_pactado"):
        paga = d["pago_regla"]
    else:
        umbral = c3.slider("Umbral de pago: lluvia de junio a agosto (% de lo normal)", 30, 100, 70, key="us_umbral_lluvia")
        paga = d["lluvia_pct_normal"] < umbral
    c4, c5 = st.columns(2)
    subsidio = c4.slider("Subsidio a la prima (%)", 0, 100, int(round(100 * resumen_us["subsidio_real"])), key="us_subsidio") / 100
    recargo = c5.slider("Recargo sobre la prima pura (%, SUPUESTO)", 0, 100, 30, key="us_recargo") / 100
    st.caption(f"El subsidio sugerido es el promedio real de la RMA para el maíz de estos estados en {resumen_us['periodo_subsidio'][0]}-{resumen_us['periodo_subsidio'][1]}. "
               f"La suma sugerida es el valor esperado de la cosecha por acre, en dólares de {resumen_us['anio_dolares']}.")

    d["paga"] = paga.to_numpy()
    if disparador == "Contrato Palmer con topes":
        d["pago_usd"] = suma_acre * d["area_cosechada_acres"] * d["fraccion_palmer"] * d["factor_tope"].fillna(1.0)   # proporcional y con tope del año
    elif disparador == "Contrato Palmer":
        d["pago_usd"] = suma_acre * d["area_cosechada_acres"] * d["fraccion_palmer"]          # pago proporcional
    else:
        d["pago_usd"] = d["paga"] * suma_acre * d["area_cosechada_acres"] * d["severidad_media_previa"]   # tamaño medio de las pérdidas de años anteriores
    prima_pura = d["pago_usd"].mean()
    prima = prima_pura * (1 + recargo)
    bien = d.loc[d["perdida"], "pago_usd"].sum()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Prima pura (pago promedio por año)", dolares(prima_pura))
    m2.metric("Prima con recargo", dolares(prima))
    m3.metric("Pérdida real promedio por año", dolares(d["perdida_usd"].mean()))
    m4.metric("Indemnización real promedio de la RMA", dolares(d["indemnizacion"].fillna(0).mean()))
    if d["pago_usd"].sum() == 0:
        st.info("Con estos valores, el seguro no habría pagado en ningún año, así que no se puede decir a dónde iría el subsidio.")
    else:
        st.success(f"De cada $100 de subsidio en este condado, ${100 * bien / d['pago_usd'].sum() / (1 + recargo):.0f} habrían llegado a años con pérdida real.")
    fig, ax = plt.subplots(figsize=(10, 3.6))
    ax.bar(d["anio"] - 0.2, d["pago_usd"] / 1e6, width=0.4, color=[AZUL if f else NARANJA for f in d["perdida"]], zorder=3)
    ax.bar(d["anio"] + 0.2, d["perdida_usd"] / 1e6, width=0.4, color=REJILLA, zorder=3)
    ax.plot(d["anio"], d["indemnizacion"].fillna(0) / 1e6, color=TINTA, marker="o", ms=3, lw=1, zorder=4)
    ax.set_ylabel("Millones de dólares de 2025", color=TINTA_2)
    ax.legend(handles=[Patch(color=AZUL, label="Pago del índice con pérdida"), Patch(color=NARANJA, label="Pago del índice sin pérdida"),
                       Patch(color=REJILLA, label="Pérdida real"), Line2D([], [], color=TINTA, marker="o", label="Indemnización real de la RMA")],
              frameon=False, fontsize=8, ncol=2)
    ejes_limpios(ax)
    fig.tight_layout()
    st.pyplot(fig)
    st.caption(f"Con regla, modelo o índice de calor, el pago es la suma asegurada por el área cosechada y por el tamaño medio de las pérdidas de los años anteriores. Precio nacional de cada campaña (USDA ERS), "
               f"en dólares de {resumen_us['anio_dolares']}. La RMA cubre todas las causas, también la caída del precio.")
    vista = d.assign(resultado=[("Pagó y hubo pérdida" if p_ and f else "Pagó sin pérdida" if p_ else "Hubo pérdida y no pagó" if f else "Sin pago ni pérdida")
                                for p_, f in zip(d["paga"], d["perdida"])])
    st.dataframe(vista[["anio", "lluvia_jun_ago_mm", "prob", "pago_usd", "perdida_usd", "indemnizacion", "resultado"]], hide_index=True)
