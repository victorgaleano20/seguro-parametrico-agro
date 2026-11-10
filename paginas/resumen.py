"""Resumen: el veredicto del proyecto en una pantalla, con rangos de 95 % (tablas de 54_tablas_app.py)."""
import numpy as np
import plotly.graph_objects as go
import streamlit as st

import app_comun as ac

st.title("¿El clima del verano anticipa la pérdida de maíz?")
st.markdown("Un seguro paramétrico paga solo, mirando el clima, sin visitar la finca. Funciona si el clima del verano "
            "**señala bien qué condados perdieron la cosecha** (rendimiento de 80 % o menos de lo esperado). "
            "Aquí se compara el modelo con dos disparadores simples, en años y estados que el modelo no usó para entrenar.")

met = ac.tabla("app_metricas.csv")
dif = ac.tabla("app_diferencias.csv")

c1, c2 = st.columns(2)
with c1:
    grupo = ac.selector("Estados", ac.GRUPOS, "siete", "res_grupo")
with c2:
    periodo = ac.selector("Periodo", ac.PERIODOS, "confirmacion", "res_periodo")
st.caption(ac.AVISO_GRUPO[grupo])

m = met[(met["grupo"] == grupo) & (met["periodo"] == periodo)].set_index("puntaje")

# ---------------------------------------------------------------- indicadores
cols = st.columns(4)
for col, k in zip(cols, ac.PUNTAJES):
    r = m.loc[k]
    col.metric(ac.NOMBRES[k], ac.num(r["auc"]),
               help=f"AUC: probabilidad de que un condado-año con pérdida reciba más riesgo que uno sin pérdida. "
                    f"Rango de 95 % remuestreando años: {ac.num(r['auc_ic_inf'])} a {ac.num(r['auc_ic_sup'])}.")
    col.caption(f"Rango 95 %: {ac.num(r['auc_ic_inf'], 2)} a {ac.num(r['auc_ic_sup'], 2)} · dentro del año {ac.num(r['auc_dentro'])}")
cols[3].metric("Azar", "0,500")
cols[3].caption(f"{ac.entero(m['filas'].iloc[0])} condado-años, {ac.entero(m['perdidas'].iloc[0])} con pérdida")

# ---------------------------------------------------------------- veredicto calculado, no escrito a mano
st.subheader("Veredicto")
TEXTO = {"supera": "lo supera", "no se distingue": "no se distingue de él", "queda por debajo": "queda por debajo"}
for comparador in ("ref_regla", "ref_calor"):
    v = dif[(dif["grupo"] == grupo) & (dif["periodo"] == periodo) & (dif["comparador"] == comparador)]
    e_auc, inf, sup, no_gana = ac.veredicto(v["dif_auc"].to_numpy())
    e_den, inf_d, sup_d, no_gana_d = ac.veredicto(v["dif_dentro"].to_numpy())
    puntual = m.loc["prob", "auc"] - m.loc[comparador, "auc"]
    puntual_d = m.loc["prob", "auc_dentro"] - m.loc[comparador, "auc_dentro"]
    articulo = "a la" if comparador == "ref_regla" else "al"
    texto = (f"**Frente {articulo} {ac.NOMBRES[comparador].lower()}**, el modelo **{TEXTO[e_auc]}** en acierto total: "
             f"{ac.signo(puntual)} de AUC (rango 95 %: {ac.signo(inf)} a {ac.signo(sup)}; en {ac.num(100 * no_gana, 0)} % de los remuestreos no gana). "
             f"Dentro de cada año, {TEXTO[e_den]}: {ac.signo(puntual_d)} ({ac.signo(inf_d)} a {ac.signo(sup_d)}).")
    (st.success if e_auc == "supera" and e_den == "supera" else st.warning if e_auc != "queda por debajo" else st.error)(texto)

# ---------------------------------------------------------------- AUC por periodo con rangos
st.subheader("Acierto en cada periodo, con su rango de 95 %")
g = met[met["grupo"] == grupo]
izq, der = st.columns(2)
for contenedor, (valor, inf, sup, titulo) in zip(
        (izq, der), [("auc", "auc_ic_inf", "auc_ic_sup", "AUC total"), ("auc_dentro", "dentro_ic_inf", "dentro_ic_sup", "AUC dentro de cada año")]):
    fig = go.Figure()
    etiquetas = [ac.PERIODOS[p] for p in ac.PERIODOS]
    for i, k in enumerate(ac.PUNTAJES):
        s = g[g["puntaje"] == k].set_index("periodo").loc[list(ac.PERIODOS)]
        fig.add_trace(go.Scatter(
            x=s[valor], y=np.arange(len(s)) + (i - 1) * 0.22, mode="markers", name=ac.NOMBRES[k],
            marker=dict(color=ac.COLORES[k], size=10, line=dict(width=1.5, color="white")),
            error_x=dict(type="data", symmetric=False, array=s[sup] - s[valor], arrayminus=s[valor] - s[inf], thickness=2, width=0, color=ac.COLORES[k]),
            customdata=np.c_[etiquetas, s[inf], s[sup]],
            hovertemplate=f"{ac.NOMBRES[k]}, " + "%{customdata[0]}: %{x:.3f} (rango %{customdata[1]:.2f} a %{customdata[2]:.2f})<extra></extra>"))
    fig.add_vline(x=0.5, line_dash="dot", line_color=ac.TINTA_2, annotation_text="azar", annotation_position="bottom right")
    fig.update_layout(xaxis=dict(range=[0.25, 1], title="AUC"),
                      yaxis=dict(tickvals=list(range(len(etiquetas))), ticktext=etiquetas, autorange="reversed", showgrid=False))
    contenedor.markdown(f"**{titulo}**")
    contenedor.plotly_chart(ac.estilo(fig, 360), width="stretch")
st.caption("Cada punto es el AUC del periodo; la línea, su rango de 95 % remuestreando años completos (1.000 veces). "
           "Rangos anchos: pocos años malos (2012, 1993, 2002...) concentran buena parte de las pérdidas.")

# ---------------------------------------------------------------- lectura
st.subheader("Qué significa")
st.markdown(
    "- **El clima sí anticipa la pérdida**, también en estados que el modelo nunca usó para entrenar, y **mejor que la regla de lluvia**.\n"
    "- **Un índice simple de calor de julio y agosto hace casi lo mismo** que el modelo: la diferencia es pequeña y su rango incluye el cero en 2011-2025. "
    "Para un contrato, el índice simple es más fácil de explicar.\n"
    "- **El riesgo de base sigue alto:** cerca de \\$2 de cada \\$3 que pagaría el índice irían a condados sin pérdida (página *Contrato y riesgo de base*).\n"
    "- La etiqueta cuenta toda pérdida de 20 % o más, **también por exceso de agua** (1993), no solo por sequía.")
st.page_link("paginas/contrato.py", label="Ver el contrato y el riesgo de base", icon=":material/arrow_forward:")
st.page_link("paginas/laboratorio.py", label="Ver el detalle técnico (laboratorio)", icon=":material/arrow_forward:")

with st.expander("Cómo leer estas cifras"):
    st.markdown(
        "- **AUC total:** si se toma al azar un condado-año con pérdida y otro sin pérdida, con qué frecuencia el disparador le da más riesgo al que perdió. 0,5 es azar; 1, perfecto.\n"
        "- **AUC dentro de cada año:** lo mismo, pero comparando solo condados del mismo año (años con 10 o más pérdidas, ponderado por pérdidas). "
        "Mide si distingue **qué condados** pierden, no solo **qué años** son malos.\n"
        "- **Rango de 95 %:** se sortean años completos con reposición, porque una sequía golpea a todos los condados a la vez. "
        "En cada sorteo se usan los mismos años para el modelo y las referencias.\n"
        "- **Modelo final:** logística con curvas suaves (splines) sobre 13 variables de clima frente a lo normal del condado. "
        "Cada año se predice con un modelo entrenado solo con años anteriores y solo con Iowa, Illinois e Indiana.\n"
        "- **Índice de calor:** temperatura máxima de julio más la de agosto, frente a lo normal del condado. No se entrena.\n"
        "- **Regla de lluvia:** lluvia de junio a agosto frente a lo normal; el contrato paga bajo el percentil 15 del condado.")
