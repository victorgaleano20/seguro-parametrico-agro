"""Predicción: probabilidad de activación y de pérdida, riesgo de base, prima y resultado de la aseguradora para un
condado y un año (plan en docs/bitacora.md, 2026-11-12). Usa el modelo final guardado; no entrena nada."""
import joblib
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import app_comun as ac
import app_prediccion as ap

ULTIMO_ANIO = 2025
ACRE_A_HA = 0.404686
COLOR = {"modelo": ac.COLORES["prob"], "calor": ac.COLORES["ref_calor"], "regla": ac.COLORES["ref_regla"]}
VERDE, ROJO = "#1d7f5c", "#c4561f"
ETIQUETAS = {
    "lluvia_may": "Lluvia de mayo (% de lo normal)", "lluvia_jun": "Lluvia de junio (% de lo normal)",
    "lluvia_jul": "Lluvia de julio (% de lo normal)", "lluvia_ago": "Lluvia de agosto (% de lo normal)",
    "lluvia_sep": "Lluvia de septiembre (% de lo normal)", "racha_meses_secos": "Racha de meses secos (meses)",
    "deficit_jul_ago": "Déficit de lluvia jul-ago (% bajo lo normal)",
    "tmax_jun": "Temperatura máxima de junio (°C sobre lo normal)", "tmax_jul": "Temperatura máxima de julio (°C sobre lo normal)",
    "tmax_ago": "Temperatura máxima de agosto (°C sobre lo normal)",
    "palmer_jun": "Palmer de junio (negativo = sequía)", "palmer_jul": "Palmer de julio (negativo = sequía)",
    "palmer_ago": "Palmer de agosto (negativo = sequía)"}
GRUPOS_VARIABLES = {"Lluvia": ["lluvia_may", "lluvia_jun", "lluvia_jul", "lluvia_ago", "lluvia_sep", "racha_meses_secos", "deficit_jul_ago"],
                    "Calor": ["tmax_jun", "tmax_jul", "tmax_ago"], "Sequía (Palmer)": ["palmer_jun", "palmer_jul", "palmer_ago"]}


# ---------------------------------------------------------------- carga (en caché)
@st.cache_resource
def cargar_modelo():
    paquete = joblib.load(ac.RAIZ / "modelos" / "modelo_final.joblib")
    return paquete["modelo"], paquete["columnas"]


@st.cache_data
def cargar_tabla():
    return pd.read_csv(ac.PROCESADOS / "app_prediccion.csv", dtype={"unidad": str, "grupo": str})


@st.cache_data
def frecuencia_regla():
    return float(ac.predicciones()["pago_regla"].mean())


def dinero(x):
    return ("−" if x < 0 else "") + "US$" + f"{abs(x):,.0f}".replace(",", ".")


def md(texto):
    """Escapa el signo $ para que Streamlit no lo lea como fórmula matemática."""
    return texto.replace("$", "\$")


def pct(x, dec=1):
    return f"{ac.num(100 * x, dec)} %"


modelo, columnas = cargar_modelo()
tabla = cargar_tabla()
f_regla = frecuencia_regla()

st.title("Predicción")
st.markdown("Escoja un condado y un año, y el seguro que quiere evaluar. La página estima si el seguro se activaría, la probabilidad "
            "de pérdida de la cosecha, el riesgo de base, la prima y lo que le quedaría a la aseguradora.")
with st.expander("Qué usa el modelo y qué no (leer antes de interpretar)"):
    st.markdown(
        "- El modelo final recibe **solo 13 variables de clima del verano, medidas frente a lo normal del condado**. No usa el estado ni el año: "
        "aquí sirven para traer el clima de ese condado y ese año, que usted puede modificar para armar un escenario.\n"
        "- Su probabilidad **no está calibrada**: ordena bien el riesgo, pero exagera el riesgo alto (cuando dice 60 %, ocurrió cerca de 38 %).\n"
        "- Para un año futuro el clima no se conoce: la probabilidad de activación es la frecuencia con que el seguro se habría activado en ese "
        "condado entre 1991 y 2025.\n"
        "- La regla de lluvia usa aquí la lluvia de junio a agosto en % de lo normal; en el resto del proyecto usa milímetros, así que puede "
        "diferir un poco de la página del contrato.\n"
        "- Es una **estimación probabilística, no una garantía**. El recargo de la prima es un supuesto.")

# ---------------------------------------------------------------- 1. condado, año y seguro
c1, c2, c3 = st.columns([2, 3, 1.4])
siglas = sorted(tabla["sigla"].unique(), key=lambda s: (s not in ("IA", "IL", "IN"), s))
with c1:
    sigla = st.selectbox("Estado", siglas, format_func=lambda s: tabla.loc[tabla["sigla"] == s, "estado"].iloc[0], key="pre_estado")
estado_df = tabla[tabla["sigla"] == sigla]
with c2:
    condados = estado_df.groupby("unidad")["condado"].first().sort_values()
    unidad = st.selectbox("Condado", condados.index, format_func=lambda u: condados[u].title(), key=f"pre_condado_{sigla}")
historia = estado_df[estado_df["unidad"] == unidad].sort_values("anio")
with c3:
    anio = st.number_input("Año", min_value=int(historia["anio"].min()), max_value=ULTIMO_ANIO + 10,
                           value=int(historia["anio"].max()), step=1, key="pre_anio")
proyeccion = anio > ULTIMO_ANIO or anio not in set(historia["anio"])
if anio > ULTIMO_ANIO:
    st.info(f"**{anio} es un año futuro: es una proyección.** Como su clima no se conoce, la probabilidad de activación es la frecuencia "
            f"con que el seguro se habría activado en este condado entre {int(historia['anio'].min())} y {ULTIMO_ANIO}.")
elif proyeccion:
    st.warning(f"No hay datos de este condado en {anio} (falta el rendimiento o el clima). Se muestra como proyección con su historia.")

c1, c2 = st.columns([1.3, 2])
with c1:
    disparador = ac.selector("Disparador del seguro", ap.DISPARADORES, "modelo", "pre_disparador")
with c2:
    opciones = sorted({0.05, 0.10, round(f_regla, 6), 0.20, 0.25, 0.30})
    frecuencia = st.select_slider("Umbral de disparo: ¿en qué parte de los condado-años paga el seguro?", opciones, value=round(f_regla, 6),
                                  key="pre_frecuencia",
                                  format_func=lambda f: f"{ac.num(100 * f, 1)} %" + (" (la de la regla)" if f == round(f_regla, 6) else ""))

# ---------------------------------------------------------------- 2. clima y póliza (formulario)
fila = None if proyeccion else historia[historia["anio"] == anio].iloc[0]
valor_ha = float((estado_df["valor_esperado_usd"] / estado_df["area_ha"]).median())
porcentaje_def = float(tabla["severidad_media_previa"].median())
with st.form("pre_formulario"):
    valores = {}
    if not proyeccion:
        st.markdown(f"**Clima del verano de {anio} en {condados[unidad].title()}.** Vienen los datos reales; cámbielos para armar un escenario. "
                    "Los límites son el mínimo y el máximo observados en el estado.")
        columnas_ui = st.columns(3)
        for col_ui, (grupo, variables) in zip(columnas_ui, GRUPOS_VARIABLES.items()):
            with col_ui:
                st.markdown(f"*{grupo}*")
                for v in variables:
                    lo, hi, actual = float(estado_df[v].min()), float(estado_df[v].max()), float(fila[v])
                    entero = v.startswith(("lluvia", "deficit")) or v == "racha_meses_secos"
                    valores[v] = st.slider(ETIQUETAS[v], lo, hi, actual, 1.0 if entero else 0.1, format="%.0f" if entero else "%.1f",
                                           key=f"pre_{v}_{unidad}_{anio}")
    st.markdown("**Póliza** (valores por omisión tomados de los datos; puede cambiarlos)")
    p1, p2, p3, p4 = st.columns(4)
    hectareas = p1.number_input("Hectáreas aseguradas", min_value=1.0, value=100.0, step=10.0, key="pre_ha",
                                help="Ejemplo de 100 hectáreas; cámbielo por el tamaño de la póliza.")
    suma_ha = p2.number_input("Suma asegurada por hectárea (US$)", min_value=1.0, value=float(round(valor_ha, -1)), step=50.0, key=f"pre_suma_{sigla}",
                              help="Por omisión: mediana del valor esperado de la cosecha por hectárea en el estado (dólares de 2025).")
    porcentaje = p3.number_input("Porcentaje que paga si se activa (%)", min_value=1.0, max_value=100.0, value=round(100 * porcentaje_def, 1),
                                 step=1.0, key="pre_porcentaje",
                                 help="Por omisión: tamaño medio de las pérdidas de años anteriores, como en la página del contrato.") / 100
    recargo = p4.number_input("Recargo de la aseguradora (%)", min_value=0.0, max_value=200.0, value=30.0, step=5.0, key="pre_recargo",
                              help="Supuesto: no se calculó con datos de ninguna aseguradora.") / 100
    st.form_submit_button("Calcular predicción", type="primary")

# ---------------------------------------------------------------- 3. cálculos
try:
    pago = ap.calcular_pago(hectareas, suma_ha, porcentaje)
except ValueError as e:
    st.error(f"Revise la póliza: {e}")
    st.stop()
umbrales = ap.umbrales_globales(tabla, frecuencia)
activa_hist = ap.activaciones_historicas(historia, disparador, umbrales, frecuencia)
p_act_hist = float(activa_hist.mean())
tasa_perdida_hist = float(historia["perdida"].mean())
prima_pura, prima_comercial = ap.calcular_prima(p_act_hist, pago, recargo)      # la prima se fija con la historia del condado
umbral = ap.umbral_regla(historia, frecuencia) if disparador == "regla" else umbrales[disparador]

if proyeccion:
    p_activacion, p_perdida, activa = p_act_hist, tasa_perdida_hist, None
else:
    prob = float(ap.predecir_probabilidad(modelo, columnas, valores)[0])
    calor = valores["tmax_jul"] + valores["tmax_ago"]
    lluvia = float(np.mean([valores["lluvia_jun"], valores["lluvia_jul"], valores["lluvia_ago"]]))
    activa = ap.se_activa(disparador, ap.puntaje(disparador, prob, calor, lluvia), umbral)
    p_activacion, p_perdida = (1.0 if activa else 0.0), prob
resultado_esperado = ap.calcular_resultado(prima_comercial, p_act_hist, pago)
resultado_si_activa = ap.resultado_escenario(prima_comercial, True, pago)

# ---------------------------------------------------------------- 4. resultados
st.subheader("Resultados")
k1, k2, k3, k4 = st.columns(4)
if proyeccion:
    k1.metric("Probabilidad de activación", pct(p_act_hist), help=f"Se habría activado {int(activa_hist.sum())} de {len(activa_hist)} años en este condado.")
    k2.metric("Probabilidad de pérdida", pct(p_perdida), help="Tasa histórica de pérdida del condado (rendimiento de 80 % o menos de lo esperado).")
    nombre_rb, p_rb = "Paga sin pérdida", float((activa_hist & ~historia["perdida"]).sum() / max(activa_hist.sum(), 1))
    k3.metric("Riesgo de base: paga sin pérdida", pct(p_rb), help="De los años en que se habría activado, en cuántos no hubo pérdida.")
else:
    k1.metric("¿Se activa el seguro?", "Sí" if activa else "No",
              help=f"{ap.DISPARADORES[disparador]}: puntaje {ac.num(ap.puntaje(disparador, prob, calor, lluvia), 3)} frente a un umbral de {ac.num(umbral, 3)}.")
    k2.metric("Probabilidad de pérdida (modelo)", pct(p_perdida), help="Probabilidad del modelo final, sin calibrar: exagera el riesgo alto.")
    nombre_rb, p_rb = ap.riesgo_de_base(activa, p_perdida)
    k3.metric(f"Riesgo de base: {nombre_rb.lower()}", pct(p_rb),
              help="Si el seguro paga, probabilidad de que no haya pérdida; si no paga, probabilidad de que sí la haya.")
nivel = ap.nivel_riesgo(p_perdida)
with k4:
    st.metric("Nivel de riesgo de pérdida", nivel, help="Bajo: menos de 10 % (la tasa media); medio: 10 a 25 %; alto: 25 % o más.")
    (st.success if nivel == "Bajo" else st.warning if nivel == "Medio" else st.error)(f"Riesgo {nivel.lower()}")

f1, f2, f3, f4 = st.columns(4)
f1.metric("Pago si se activa", dinero(pago))
f2.metric("Prima pura (por año)", dinero(prima_pura), help=f"Frecuencia histórica de activación del condado ({pct(p_act_hist)}) × pago.")
f3.metric("Prima comercial (por año)", dinero(prima_comercial), help=f"Prima pura × (1 + recargo de {ac.num(100 * recargo, 0)} %).")
f4.metric("Ganancia esperada de la aseguradora" if resultado_esperado >= 0 else "Costo esperado de la aseguradora", dinero(resultado_esperado),
          help="Prima cobrada − probabilidad de activación × pago, en promedio de largo plazo.")
if not proyeccion:
    r_esc = ap.resultado_escenario(prima_comercial, activa, pago)
    (st.success if r_esc >= 0 else st.error)(md(
        f"**En este escenario** la aseguradora {'gana' if r_esc >= 0 else 'pierde'} {dinero(abs(r_esc))}: "
        + ("el seguro no se activa y se queda con la prima." if not activa else "el seguro se activa y paga más de lo que cobró.")))
st.caption(md(f"En el promedio de largo plazo la aseguradora gana justo el recargo. Pero cada año en que el seguro se activa pierde "
           f"{dinero(abs(resultado_si_activa))}; en este condado eso habría pasado {int(activa_hist.sum())} de {len(activa_hist)} años "
           f"({', '.join(map(str, historia.loc[activa_hist, 'anio'].tolist()[:12]))}{'…' if activa_hist.sum() > 12 else ''})."))

# ---------------------------------------------------------------- 5. gráficas
g1, g2 = st.columns([1, 1.4])
with g1:
    titulo_g = "Probabilidad de activación (histórica)" if proyeccion else "Probabilidad de pérdida (modelo)"
    valor_g = p_act_hist if proyeccion else p_perdida
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=100 * valor_g, number={"suffix": " %", "valueformat": ".1f"},
        title={"text": titulo_g, "font": {"size": 15}},
        gauge={"axis": {"range": [0, 100]}, "bar": {"color": COLOR[disparador]},
               "steps": [{"range": [0, 10], "color": "rgba(29,127,92,0.18)"}, {"range": [10, 25], "color": "rgba(217,162,27,0.22)"},
                         {"range": [25, 100], "color": "rgba(196,86,31,0.18)"}],
               "threshold": ({"line": {"color": ac.TINTA_2, "width": 3}, "value": 100 * umbral}
                             if disparador == "modelo" and not proyeccion else None)}))
    st.plotly_chart(ac.estilo(fig, 300, leyenda=False), width="stretch")
    st.caption("Franjas: riesgo bajo (verde), medio (amarillo) y alto (naranja)."
               + (" La raya marca el umbral de activación del modelo." if disparador == "modelo" and not proyeccion else ""))
with g2:
    barras = [("Prima cobrada", prima_comercial, ac.GRIS_SUAVE), ("Pago esperado", p_act_hist * pago, ROJO),
              ("Resultado esperado", resultado_esperado, VERDE if resultado_esperado >= 0 else ROJO)]
    if not proyeccion:
        r_esc = ap.resultado_escenario(prima_comercial, activa, pago)
        barras.append(("Resultado en este escenario", r_esc, VERDE if r_esc >= 0 else ROJO))
    fig = go.Figure(go.Bar(x=[b[0] for b in barras], y=[b[1] for b in barras], marker=dict(color=[b[2] for b in barras], cornerradius=4),
                           text=[dinero(b[1]) for b in barras], textposition="outside", hovertemplate="%{x}: US$%{y:,.0f}<extra></extra>"))
    fig.update_layout(yaxis=dict(title="US$ por año", tickformat=",.0f"), title=dict(text="La aseguradora: prima, pago y resultado", font=dict(size=15)))
    fig.add_hline(y=0, line_color=ac.TINTA_2, line_width=1)
    st.plotly_chart(ac.estilo(fig, 340, leyenda=False), width="stretch")

st.subheader(f"Historia de {condados[unidad].title()}: cuándo se habría activado")
col_p = {"modelo": "prob_modelo", "calor": "indice_calor", "regla": "lluvia_jja_pct"}[disparador]
nombre_eje = {"modelo": "Probabilidad de pérdida del modelo", "calor": "Índice de calor (°C sobre lo normal)",
              "regla": "Lluvia jun-ago (% de lo normal)"}[disparador]
fig = go.Figure()
fig.add_trace(go.Bar(x=historia["anio"], y=historia[col_p], name="Puntaje del disparador",
                     marker=dict(color=[COLOR[disparador] if a else ac.GRIS_SUAVE for a in activa_hist], cornerradius=3),
                     hovertemplate="%{x}: %{y:.3f}<extra></extra>"))
perd = historia[historia["perdida"]]
fig.add_trace(go.Scatter(x=perd["anio"], y=perd[col_p], mode="markers", name="Año con pérdida real",
                         marker=dict(symbol="diamond", size=10, color=ac.TINTA_2, line=dict(width=2, color="white"))))
fig.add_hline(y=umbral, line_dash="dash", line_color=ac.TINTA_2, annotation_text="umbral de disparo", annotation_position="top left")
if not proyeccion:
    fig.add_vline(x=anio, line_dash="dot", line_color=COLOR[disparador], annotation_text=str(anio))
fig.update_layout(yaxis_title=nombre_eje, barmode="overlay")
st.plotly_chart(ac.estilo(fig, 380), width="stretch")
st.caption("Barras de color: años en que el seguro se habría activado; grises: años sin pago. Rombos: años con pérdida real. "
           + ("En la regla de lluvia se activa cuando la barra queda por debajo del umbral." if disparador == "regla"
              else "Se activa cuando la barra supera el umbral.")
           + " La probabilidad del modelo en la historia es la del modelo final guardado, entrenado con todos los años: es optimista para el pasado.")

# ---------------------------------------------------------------- 6. sensibilidad
st.subheader("Análisis de sensibilidad")
t1, t2 = st.tabs(["Umbral de disparo", "Clima del escenario"])
with t1:
    filas = []
    for f in np.arange(0.05, 0.3001, 0.025):
        a = ap.activaciones_historicas(historia, disparador, ap.umbrales_globales(tabla, f), f)
        pura, com = ap.calcular_prima(float(a.mean()), pago, recargo)
        filas.append({"f": 100 * f, "prima": com, "acierto": 100 * (a & historia["perdida"]).sum() / a.sum() if a.sum() else np.nan,
                      "cubiertas": 100 * (a & historia["perdida"]).sum() / historia["perdida"].sum() if historia["perdida"].sum() else np.nan})
    s = pd.DataFrame(filas)
    i1, i2 = st.columns(2)
    fig = go.Figure(go.Scatter(x=s["f"], y=s["prima"], mode="lines+markers", line=dict(color=COLOR[disparador], width=2),
                               hovertemplate="%{x:.1f} %: US$%{y:,.0f}<extra></extra>"))
    fig.add_vline(x=100 * frecuencia, line_dash="dot", line_color=ac.TINTA_2)
    fig.update_layout(title=dict(text="Prima comercial por año", font=dict(size=14)), xaxis_title="Frecuencia de pago (%)", yaxis=dict(tickformat=",.0f"))
    i1.plotly_chart(ac.estilo(fig, 320, leyenda=False), width="stretch")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=s["f"], y=s["acierto"], mode="lines+markers", name="Activaciones con pérdida real", line=dict(color=COLOR[disparador], width=2)))
    fig.add_trace(go.Scatter(x=s["f"], y=s["cubiertas"], mode="lines+markers", name="Pérdidas con pago", line=dict(color=ac.TINTA_2, width=2, dash="dash")))
    fig.add_vline(x=100 * frecuencia, line_dash="dot", line_color=ac.TINTA_2)
    fig.update_layout(title=dict(text="Acierto en la historia del condado (%)", font=dict(size=14)), xaxis_title="Frecuencia de pago (%)",
                      yaxis=dict(range=[0, 105]), legend=dict(y=-0.3, yanchor="top"))
    i2.plotly_chart(ac.estilo(fig, 320).update_layout(legend=dict(y=-0.3, yanchor="top")), width="stretch")
    st.caption("Subir la frecuencia de pago encarece la prima y deja menos pérdidas sin pago, pero baja la parte de los pagos que llega a quien perdió.")
with t2:
    if proyeccion:
        st.info("Disponible solo para años con clima conocido (1991-2025), porque parte del clima de ese año.")
    else:
        variable = st.segmented_control("Variable que se mueve", ["calor", "lluvia"], default="calor", key="pre_sens_var",
                                        format_func={"calor": "Calor de julio y agosto", "lluvia": "Lluvia de junio a agosto"}.get) or "calor"
        deltas = np.linspace(-4, 4, 33) if variable == "calor" else np.linspace(-60, 60, 33)
        esc = pd.DataFrame([valores] * len(deltas))
        if variable == "calor":
            esc["tmax_jul"] += deltas; esc["tmax_ago"] += deltas
        else:
            for v in ("lluvia_jun", "lluvia_jul", "lluvia_ago"):
                esc[v] = (esc[v] + deltas).clip(lower=0)
        probs = ap.predecir_probabilidad(modelo, columnas, esc)
        calores = esc["tmax_jul"] + esc["tmax_ago"]
        lluvias = esc[["lluvia_jun", "lluvia_jul", "lluvia_ago"]].mean(axis=1)
        activas = [ap.se_activa(disparador, ap.puntaje(disparador, p, c, l), umbral) for p, c, l in zip(probs, calores, lluvias)]
        resultados = [ap.resultado_escenario(prima_comercial, a, pago) for a in activas]
        eje = "Cambio en el calor de cada mes (°C)" if variable == "calor" else "Cambio en la lluvia de cada mes (puntos de %)"
        j1, j2 = st.columns(2)
        fig = go.Figure(go.Scatter(x=deltas, y=100 * probs, mode="lines+markers", line=dict(color=ac.COLORES["prob"], width=2),
                                   marker=dict(color=[COLOR[disparador] if a else ac.GRIS_SUAVE for a in activas], size=8),
                                   hovertemplate="%{x:+.1f}: %{y:.1f} %<extra></extra>"))
        fig.add_vline(x=0, line_dash="dot", line_color=ac.TINTA_2, annotation_text="escenario actual")
        fig.update_layout(title=dict(text="Probabilidad de pérdida del modelo (%)", font=dict(size=14)), xaxis_title=eje)
        j1.plotly_chart(ac.estilo(fig, 320, leyenda=False), width="stretch")
        fig = go.Figure(go.Bar(x=deltas, y=resultados, marker=dict(color=[ROJO if r < 0 else VERDE for r in resultados]),
                               hovertemplate="%{x:+.1f}: US$%{y:,.0f}<extra></extra>"))
        fig.update_layout(title=dict(text="Resultado de la aseguradora en ese escenario (US$)", font=dict(size=14)), xaxis_title=eje,
                          yaxis=dict(tickformat=",.0f"))
        j2.plotly_chart(ac.estilo(fig, 320, leyenda=False), width="stretch")
        st.caption("Izquierda: puntos de color donde el seguro se activaría con el disparador escogido. Derecha: en verde la aseguradora se "
                   "queda con la prima; en naranja paga más de lo que cobró.")

# ---------------------------------------------------------------- 7. explicación
st.subheader("En pocas palabras")
nombre = f"{condados[unidad].title()} ({tabla.loc[tabla['sigla'] == sigla, 'estado'].iloc[0]})"
if proyeccion:
    texto = (f"Para {nombre} en {anio}, con el {ap.DISPARADORES[disparador].lower()} pagando en el {pct(frecuencia)} de los condado-años, "
             f"el seguro se activaría con una probabilidad de {pct(p_act_hist)}, que es la frecuencia con que se habría activado en este condado "
             f"entre {int(historia['anio'].min())} y {ULTIMO_ANIO}. ")
else:
    texto = (f"Para {nombre} con el clima de {anio}{' modificado' if any(abs(valores[v] - float(fila[v])) > 1e-9 for v in columnas) else ''}, "
             f"el modelo estima una probabilidad de pérdida de {pct(p_perdida)} y el {ap.DISPARADORES[disparador].lower()} "
             f"{'sí' if activa else 'no'} activaría el seguro. ")
texto += (f"Con una suma asegurada de {dinero(hectareas * suma_ha)} ({ac.num(hectareas, 0)} hectáreas) y un pago de {dinero(pago)} si se activa, "
          f"la prima pura es {dinero(prima_pura)} y la comercial {dinero(prima_comercial)} por año, así que la aseguradora tendría una "
          f"{'ganancia' if resultado_esperado >= 0 else 'pérdida'} esperada de {dinero(abs(resultado_esperado))} por año en el largo plazo"
          + ("." if proyeccion else f", y en este escenario {'ganaría' if ap.resultado_escenario(prima_comercial, activa, pago) >= 0 else 'perdería'} "
             f"{dinero(abs(ap.resultado_escenario(prima_comercial, activa, pago)))}."))
st.markdown(md(texto))
st.caption("Es una estimación probabilística, no una garantía. El modelo ordena bien el riesgo pero sus probabilidades no están calibradas; "
           "el recargo es un supuesto, y la prima se fija con la historia del condado.")
