"""Contrato y riesgo de base: todos los disparadores pagan en el mismo número de condado-años; solo cambia a quién."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import app_comun as ac

st.title("Contrato y riesgo de base")
st.markdown("Si el seguro paga en el mismo número de condado-años con cada disparador, **¿cuál dirige mejor la plata a quien perdió?** "
            "Todos pagan el mismo monto por condado (valor esperado de la cosecha × tamaño medio de las pérdidas de años anteriores); "
            "solo cambia **a quién** le pagan. Dólares de 2025.")

d = ac.predicciones()
c1, c2, c3 = st.columns([3, 1, 2])
with c1:
    grupo = ac.selector("Estados", ac.GRUPOS, "diez", "con_grupo")
with c2:
    con_2012 = st.toggle("Incluir 2012", value=True, key="con_2012", help="2012 fue la peor sequía del periodo: pesa mucho en los dólares.")
g = ac.filtrar(d, grupo, "todo" if con_2012 else "sin_2012").reset_index(drop=True)
f_regla = float(g["pago_regla"].mean())
opciones = sorted({0.05, 0.10, round(f_regla, 6), 0.20, 0.25, 0.30})
with c3:
    frecuencia = st.select_slider(
        "¿En qué parte de los condado-años paga el seguro?", opciones, value=round(f_regla, 6), key="con_frecuencia",
        format_func=lambda f: f"{ac.num(100 * f, 1)} %" + (" (la de la regla)" if f == round(f_regla, 6) else ""))

res, anual = ac.contrato(g, frecuencia)
r = res.set_index("clave")

# ---------------------------------------------------------------- de cada $100
st.subheader("De cada $100 que paga el seguro, ¿cuántos llegan a condados con pérdida?")
cols = st.columns(4)
for col, k in zip(cols, ["prob", "ref_calor", "ref_regla", "azar"]):
    col.metric(ac.NOMBRES[k], f"${ac.num(r.loc[k, 'de_cada_100'], 1)}",
               help="Pagos en condado-años con pérdida / todos los pagos × 100." if k != "azar" else
               "Lo que se espera si los mismos pagos se repartieran al azar.")
fig = go.Figure()
orden = ["azar", "ref_regla", "ref_calor", "prob"]
fig.add_trace(go.Bar(x=[r.loc[k, "de_cada_100"] for k in orden], y=[ac.NOMBRES[k] for k in orden], orientation="h",
                     marker=dict(color=[ac.COLORES[k] for k in orden], cornerradius=4),
                     text=[f"${ac.num(r.loc[k, 'de_cada_100'], 1)}" for k in orden], textposition="outside",
                     hovertemplate="%{y}: $%{x:.1f} de cada $100<extra></extra>"))
fig.update_layout(xaxis=dict(range=[0, 100], title="Dólares de cada $100 pagados que llegan a quien perdió"))
st.plotly_chart(ac.estilo(fig, 230, leyenda=False), width="stretch")
mejor = res[res["clave"] != "azar"].sort_values("de_cada_100", ascending=False)
st.caption(f"El resto (\\${ac.num(100 - mejor['de_cada_100'].iloc[0], 0)} de cada \\$100 en el mejor caso) va a condados que perdieron menos de 20 %: "
           "es el **riesgo de base**. Pérdida = rendimiento del condado de 80 % o menos de lo esperado por su tendencia.")

# ---------------------------------------------------------------- tabla completa
st.subheader("Todas las medidas")
t = res[res["clave"] != "azar"].copy()
tabla = pd.DataFrame({
    "Disparador": t["disparador"],
    "De cada $100": t["de_cada_100"].round(1),
    "Pérdida cubierta %": t["perdida_cubierta"].round(1),
    "Pérdidas sin pago %": t["perdidas_sin_pago"].round(1),
    "Pagos sin pérdida %": t["pagos_sin_perdida"].round(1),
    "Heidke": t["heidke"].round(3),
    "Prima pura (US$ mill./año)": (t["prima_pura"] / 1e6).round(0),
    "Peor año (× prima)": t["peor_anio_veces"].round(1),
})
st.dataframe(tabla, hide_index=True, width="stretch")
st.caption(f"Los tres pagan en {ac.entero(t['pagos'].iloc[0])} condado-años. **De cada \\$100:** dólares que llegan a condados con pérdida. **Pérdida cubierta:** parte de la pérdida real "
           "que cubren los pagos. **Heidke:** acierto por encima del azar (0 = azar, 1 = perfecto). **Peor año:** lo que se pagaría en el peor año dividido por el pago "
           "promedio anual; mide cuánto capital necesitaría la aseguradora.")

# ---------------------------------------------------------------- año por año
st.subheader("Año por año: lo que pagaría frente a la pérdida real")
k = st.segmented_control("Disparador", ac.PUNTAJES, format_func=ac.NOMBRES.get, default="prob", key="con_disp") or "prob"
a = anual[anual["clave"] == k]
fig = go.Figure()
fig.add_trace(go.Bar(x=a["anio"], y=a["con_perdida"] / 1e6, name="Pago a condados con pérdida", marker=dict(color=ac.COLORES[k], cornerradius=3),
                     hovertemplate="%{x}: US$%{y:,.0f} millones<extra>a condados con pérdida</extra>"))
fig.add_trace(go.Bar(x=a["anio"], y=a["sin_perdida"] / 1e6, name="Pago a condados sin pérdida", marker=dict(color=ac.GRIS_SUAVE, cornerradius=3),
                     hovertemplate="%{x}: US$%{y:,.0f} millones<extra>a condados sin pérdida</extra>"))
fig.add_trace(go.Scatter(x=a["anio"], y=a["perdida_real"] / 1e6, name="Pérdida real", mode="markers",
                         marker=dict(symbol="diamond", size=9, color=ac.TINTA_2, line=dict(width=2, color="white")),
                         hovertemplate="%{x}: US$%{y:,.0f} millones<extra>pérdida real</extra>"))
fig.update_layout(barmode="stack", bargap=0.25, yaxis=dict(title="US$ millones de 2025", tickformat=",.0f"))
st.plotly_chart(ac.estilo(fig, 400), width="stretch")

fila = r.loc[k]
st.markdown(f"**Tabla de aciertos de {ac.NOMBRES_LARGOS[k].lower()}** (condado-años)")
c1, c2 = st.columns([1, 1])
c1.dataframe(pd.DataFrame({"": ["Paga", "No paga"], "Hubo pérdida": [int(fila["a"]), int(fila["c"])],
                           "No hubo pérdida": [int(fila["b"]), int(fila["d"])]}), hide_index=True, width="stretch")
c2.markdown(f"- Pagó y hubo pérdida: **{ac.entero(fila['a'])}**\n- Pagó sin pérdida: **{ac.entero(fila['b'])}** ({ac.num(fila['pagos_sin_perdida'], 0)} % de los pagos)\n"
            f"- Hubo pérdida y no pagó: **{ac.entero(fila['c'])}** ({ac.num(fila['perdidas_sin_pago'], 0)} % de las pérdidas)")

with st.expander("Cómo se calcula y qué no dice"):
    st.markdown(
        "- **Mismo número de pagos:** cada disparador paga en los condado-años de mayor riesgo según su puntaje, tantos como la frecuencia elegida. "
        "Con la frecuencia de la regla, la regla usa su umbral pactado (lluvia de junio a agosto bajo el percentil 15 del condado); con otra frecuencia, "
        "paga en los condado-años más secos frente a lo normal.\n"
        "- **Monto:** valor esperado de la cosecha (rendimiento esperado × área cosechada × precio nacional de la campaña, USDA ERS) × tamaño medio de "
        "las pérdidas de los años anteriores en Iowa, Illinois e Indiana. Es igual para todos los disparadores, así que solo cambia a quién se paga.\n"
        "- **Modelo:** cada año se predice con un modelo entrenado solo con años anteriores y con Iowa, Illinois e Indiana.\n"
        "- **No se compara con el seguro real de la RMA:** este paga por finca y por otras causas (precio, exceso de lluvia), así que medirlo con la "
        "pérdida del condado no es justo.\n"
        "- **Supuestos:** área asegurada = área cosechada; precio nacional, no por estado. En sequías fuertes, los lotes abandonados pueden esconder "
        "parte de la pérdida (no se verificó).\n"
        "- Las cifras de los diez estados con la frecuencia de la regla coinciden con `scripts/53_dolares_modelo_final.py`.")
