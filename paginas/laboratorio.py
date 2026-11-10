"""Laboratorio de desempeño: curvas, año por año, calibración, modelo frente a calor, por estado y los diez modelos."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from sklearn.metrics import average_precision_score, brier_score_loss, precision_recall_curve, roc_curve

import app_comun as ac

st.title("Laboratorio de desempeño")
st.markdown("Para especialistas: cada cifra se recalcula con los filtros. Predicciones fuera de muestra del modelo final "
            "(cada año, entrenado solo con años anteriores y con Iowa, Illinois e Indiana).")

d = ac.predicciones()
c1, c2 = st.columns(2)
with c1:
    grupo = ac.selector("Estados", ac.GRUPOS, "siete", "lab_grupo")
with c2:
    periodo = ac.selector("Periodo", ac.PERIODOS, "todo", "lab_periodo")
g = ac.filtrar(d, grupo, periodo)
estados_disp = sorted(g["estado"].unique())
estados = st.multiselect("Filtrar estados", estados_disp, default=estados_disp, key=f"lab_estados_{grupo}")
g = g[g["estado"].isin(estados)] if estados else g
st.caption(f"{ac.AVISO_GRUPO[grupo]} · {ac.entero(len(g))} condado-años, {ac.entero(g['y'].sum())} con pérdida ({ac.num(100 * g['y'].mean(), 1)} %).")

if g["y"].nunique() < 2:
    st.warning("Con estos filtros no hay pérdidas y no pérdidas a la vez: no se puede medir.")
    st.stop()

(t_curvas, t_matrices, t_anio, t_calibracion, t_calor, t_estado, t_diez) = st.tabs(
    ["Curvas ROC y de precisión", "Matrices de confusión", "Año por año", "Calibración", "¿Gana al índice de calor?", "Por estado", "Los diez modelos"])

# ---------------------------------------------------------------- curvas
with t_curvas:
    izq, der = st.columns(2)
    roc, pr = go.Figure(), go.Figure()
    for k in ac.PUNTAJES:
        fpr, tpr, _ = roc_curve(g["y"], g[k])
        paso = max(1, len(fpr) // 400)
        roc.add_trace(go.Scatter(x=fpr[::paso], y=tpr[::paso], mode="lines", line=dict(color=ac.COLORES[k], width=2),
                                 name=f"{ac.NOMBRES[k]} (AUC {ac.num(ac.auc(g['y'], g[k]))})",
                                 hovertemplate="falsos positivos %{x:.2f}, verdaderos positivos %{y:.2f}"))
        p, r, _ = precision_recall_curve(g["y"], g[k])
        paso = max(1, len(p) // 400)
        pr.add_trace(go.Scatter(x=r[::paso], y=p[::paso], mode="lines", line=dict(color=ac.COLORES[k], width=2),
                                name=f"{ac.NOMBRES[k]} (AP {ac.num(average_precision_score(g['y'], g[k]))})",
                                hovertemplate="exhaustividad %{x:.2f}, precisión %{y:.2f}"))
    roc.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color=ac.COLORES["azar"], dash="dot", width=1.5), name="Azar"))
    pr.add_hline(y=g["y"].mean(), line_dash="dot", line_color=ac.COLORES["azar"], annotation_text="azar (tasa de pérdida)")
    roc.update_layout(xaxis_title="Tasa de falsos positivos", yaxis_title="Tasa de verdaderos positivos", legend=dict(y=-0.25, yanchor="top"))
    pr.update_layout(xaxis_title="Exhaustividad (pérdidas detectadas)", yaxis_title="Precisión (pagos con pérdida)", legend=dict(y=-0.25, yanchor="top"))
    izq.plotly_chart(ac.estilo(roc, 470).update_layout(legend=dict(y=-0.2, yanchor="top")), width="stretch")
    der.plotly_chart(ac.estilo(pr, 470).update_layout(legend=dict(y=-0.2, yanchor="top")), width="stretch")
    st.caption("La curva de precisión es la más exigente con pérdidas poco frecuentes: su referencia de azar es la tasa de pérdida, no 0,5. "
               "AP = precisión promedio.")

# ---------------------------------------------------------------- matrices de confusión
with t_matrices:
    st.markdown("Las tres matrices usan **la misma frecuencia de pago**: cada disparador paga en el mismo número de condado-años, "
                "los de mayor riesgo según su puntaje. Así no gana el que paga más veces.")
    f_regla = float(g["pago_regla"].mean())
    opciones = sorted({0.05, 0.10, round(f_regla, 6), 0.20, 0.25, 0.30})
    frecuencia = st.select_slider("¿En qué parte de los condado-años paga el seguro?", opciones, value=round(f_regla, 6), key=f"lab_frec_{grupo}_{periodo}",
                                  format_func=lambda f: f"{ac.num(100 * f, 1)} %" + (" (la de la regla)" if f == round(f_regla, 6) else ""))
    y = g["y"].to_numpy()
    filas = []
    columnas = st.columns(3)
    for col, (k, paga) in zip(columnas, ac.pagos(g, frecuencia).items()):
        a, b = int((y & paga).sum()), int((~y & paga).sum())
        c, d_ = int((y & ~paga).sum()), int((~y & ~paga).sum())
        conteos = np.array([[a, c], [b, d_]])                       # filas: realidad; columnas: decisión
        por_fila = conteos / conteos.sum(axis=1, keepdims=True)
        texto = [[f"<b>{ac.entero(conteos[i, j])}</b><br>{ac.num(100 * por_fila[i, j], 0)} %" for j in range(2)] for i in range(2)]
        fig = go.Figure(go.Heatmap(
            z=por_fila, x=["Paga", "No paga"], y=["Hubo pérdida", "No hubo pérdida"], text=texto, texttemplate="%{text}",
            textfont=dict(size=15), zmin=0, zmax=1, showscale=False, xgap=3, ygap=3,
            colorscale=[[0, "#f4f3ef"], [1, ac.COLORES[k]]],
            hovertemplate="%{y} y %{x}: %{text}<extra></extra>"))
        fig.update_layout(yaxis=dict(autorange="reversed"), xaxis=dict(side="top"))
        col.markdown(f"**{ac.NOMBRES_LARGOS[k]}**")
        col.plotly_chart(ac.estilo(fig, 280, leyenda=False), width="stretch", key=f"matriz_{k}")
        precision = a / (a + b) if a + b else np.nan
        exhaustividad = a / (a + c) if a + c else np.nan
        filas.append({"Disparador": ac.NOMBRES[k], "Pagos": a + b,
                      "Precisión (pagos con pérdida)": round(precision, 3),
                      "Exhaustividad (pérdidas con pago)": round(exhaustividad, 3),
                      "F1": round(2 * precision * exhaustividad / (precision + exhaustividad), 3) if a else np.nan,
                      "Especificidad (sin pérdida y sin pago)": round(d_ / (b + d_), 3) if b + d_ else np.nan,
                      "Heidke": round(ac.heidke(y, paga), 3)})
    st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
    azar = frecuencia * y.sum()
    st.caption(f"Filas: lo que pasó; columnas: lo que decidió el seguro. El porcentaje es sobre la fila (por ejemplo, de las pérdidas, qué parte tuvo pago). "
               f"Pagando al azar con esta frecuencia se acertarían unas {ac.entero(round(azar))} pérdidas y la precisión sería la tasa de pérdida "
               f"({ac.num(100 * y.mean(), 1)} %). Con frecuencias distintas a la de la regla, la regla paga en los condado-años más secos frente a lo normal.")

# ---------------------------------------------------------------- año por año
with t_anio:
    pa = ac.auc_por_anio(g)
    st.markdown("**AUC dentro de cada año** (solo años con 10 o más pérdidas; los demás quedan en blanco) **y pérdidas por año**")
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.65, 0.35], vertical_spacing=0.06)
    ok = pa[pa["perdidas"] >= ac.MIN_PERDIDAS_ANIO]
    hueco = pa.assign(**{k: pa[k].where(pa["perdidas"] >= ac.MIN_PERDIDAS_ANIO) for k in ac.PUNTAJES})   # sin unir años que no cuentan
    for k in ac.PUNTAJES:
        fig.add_trace(go.Scatter(x=hueco["anio"], y=hueco[k], mode="lines+markers", name=ac.NOMBRES[k], line=dict(color=ac.COLORES[k], width=2),
                                 marker=dict(size=8), connectgaps=False, hovertemplate="%{x}: %{y:.3f}"), row=1, col=1)
    fig.add_hline(y=0.5, line_dash="dot", line_color=ac.TINTA_2, row=1, col=1)
    fig.add_trace(go.Bar(x=pa["anio"], y=pa["perdidas"], name="Pérdidas", marker=dict(color=ac.GRIS_SUAVE, cornerradius=3),
                         showlegend=False, hovertemplate="%{x}: %{y} pérdidas<extra></extra>"), row=2, col=1)
    fig.update_yaxes(title_text="AUC", row=1, col=1)
    fig.update_yaxes(title_text="Pérdidas", row=2, col=1)
    st.plotly_chart(ac.estilo(fig, 560), width="stretch")
    resumen = pd.DataFrame({"Disparador": [ac.NOMBRES[k] for k in ac.PUNTAJES],
                            "AUC dentro del año (ponderado)": [round(ac.auc_dentro(g, k), 3) for k in ac.PUNTAJES],
                            "Años que gana a los otros dos": [int((ok[k] == ok[ac.PUNTAJES].max(axis=1)).sum()) for k in ac.PUNTAJES],
                            "Años bajo 0,6": [int((ok[k] < 0.6).sum()) for k in ac.PUNTAJES]})
    st.dataframe(resumen, hide_index=True, width="stretch")
    p = pa.sort_values("perdidas", ascending=False)
    st.caption(f"Los 5 años con más pérdidas ({', '.join(map(str, p['anio'].head(5)))}) reúnen el "
               f"{ac.num(100 * p['perdidas'].head(5).sum() / p['perdidas'].sum(), 0)} % de las pérdidas: la muestra efectiva es pequeña.")

# ---------------------------------------------------------------- calibración
with t_calibracion:
    c = g.assign(decil=pd.qcut(g["prob"].rank(method="first"), 10, labels=False)).groupby("decil").agg(
        predicho=("prob", "mean"), observado=("y", "mean"), n=("y", "size")).reset_index()
    tope = max(c["predicho"].max(), c["observado"].max()) * 1.1
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, tope], y=[0, tope], mode="lines", line=dict(color=ac.COLORES["azar"], dash="dot", width=1.5), name="Calibración perfecta"))
    fig.add_trace(go.Scatter(x=c["predicho"], y=c["observado"], mode="lines+markers", name="Modelo final (décimos de riesgo)",
                             line=dict(color=ac.COLORES["prob"], width=2), marker=dict(size=9),
                             customdata=np.c_[c["decil"] + 1, c["n"]],
                             hovertemplate="Décimo %{customdata[0]}: predijo %{x:.1%}, ocurrió %{y:.1%} (%{customdata[1]} condado-años)<extra></extra>"))
    fig.update_layout(xaxis=dict(title="Probabilidad predicha", tickformat=".0%"), yaxis=dict(title="Pérdida observada", tickformat=".0%"))
    izq, der = st.columns([3, 2])
    izq.plotly_chart(ac.estilo(fig, 420), width="stretch")
    brier = brier_score_loss(g["y"], g["prob"])
    brier_tasa = brier_score_loss(g["y"], np.full(len(g), g["y"].mean()))
    der.metric("Brier del modelo", ac.num(brier, 4), delta=f"{brier - brier_tasa:+.4f}".replace(".", ",") + " frente a la tasa media", delta_color="inverse")
    der.metric("Brier de la tasa media", ac.num(brier_tasa, 4))
    ultimo = c.iloc[-1]
    der.markdown(f"En el décimo de más riesgo, el modelo dice **{ac.num(100 * ultimo['predicho'], 0)} %** y ocurrió **{ac.num(100 * ultimo['observado'], 0)} %**.")
    der.caption("La tasa media se calcula con los mismos datos que se evalúan, así que la comparación la favorece. "
                "El modelo va sin calibrar: la calibración isotónica con 3 años empeoraba el Brier (bitácora, novena parte). "
                "Úsese para ordenar el riesgo más que como probabilidad exacta.")

# ---------------------------------------------------------------- modelo frente a calor
with t_calor:
    dif = ac.tabla("app_diferencias.csv")
    comparador = st.segmented_control("Comparar el modelo con", ["ref_calor", "ref_regla"], format_func=ac.NOMBRES.get, default="ref_calor",
                                      key="lab_comp") or "ref_calor"
    v = dif[(dif["grupo"] == grupo) & (dif["periodo"] == periodo) & (dif["comparador"] == comparador)]
    izq, der = st.columns(2)
    for contenedor, col, titulo in [(izq, "dif_auc", "Diferencia de AUC total"), (der, "dif_dentro", "Diferencia de AUC dentro del año")]:
        estado, inf, sup, no_gana = ac.veredicto(v[col].to_numpy())
        fig = go.Figure(go.Histogram(x=v[col], nbinsx=40, marker=dict(color=ac.COLORES["prob"], line=dict(width=1, color="white")),
                                     hovertemplate="%{x}: %{y} remuestreos<extra></extra>"))
        fig.add_vline(x=0, line_color=ac.TINTA_2, line_width=2, annotation_text="sin diferencia")
        fig.add_vrect(x0=inf, x1=sup, fillcolor=ac.COLORES["prob"], opacity=0.08, line_width=0)
        fig.update_layout(title=dict(text=titulo, font=dict(size=14)), xaxis_title=f"Modelo menos {ac.NOMBRES[comparador].lower()}", yaxis_title="Remuestreos")
        contenedor.plotly_chart(ac.estilo(fig, 340, leyenda=False), width="stretch")
        contenedor.markdown(f"Rango 95 %: **{ac.signo(inf)} a {ac.signo(sup)}** · el modelo no gana en **{ac.num(100 * no_gana, 0)} %** "
                            f"de los remuestreos · veredicto: **{estado}**.")
    st.caption("1.000 remuestreos de años completos; en cada uno se usan los mismos años para el modelo y la referencia (`scripts/54_tablas_app.py`). "
               "Usa el grupo y el periodo elegidos arriba, con todos los estados del grupo (no aplica el filtro de estados).")

# ---------------------------------------------------------------- por estado
with t_estado:
    filas = []
    for est, ge in g.groupby("estado"):
        for k in ac.PUNTAJES:
            filas.append({"estado": est, "clave": k, "auc": ac.auc(ge["y"], ge[k]), "perdidas": int(ge["y"].sum())})
    pe = pd.DataFrame(filas)
    orden_est = pe[pe["clave"] == "prob"].sort_values("auc")["estado"].tolist()
    fig = go.Figure()
    for k in ac.PUNTAJES:
        s = pe[pe["clave"] == k].set_index("estado").loc[orden_est]
        fig.add_trace(go.Scatter(x=s["auc"], y=orden_est, mode="markers", name=ac.NOMBRES[k], marker=dict(color=ac.COLORES[k], size=11),
                                 customdata=s["perdidas"], hovertemplate="%{y}: %{x:.3f} (%{customdata} pérdidas)"))
    fig.add_vline(x=0.5, line_dash="dot", line_color=ac.TINTA_2, annotation_text="azar")
    fig.update_layout(xaxis=dict(title="AUC", range=[0.3, 1]))
    st.plotly_chart(ac.estilo(fig, 120 + 45 * len(orden_est)), width="stretch")
    st.caption("Minnesota es el caso débil conocido: allí la sequía es la parte más baja de lo que paga el seguro real, y el exceso de humedad la más alta.")

# ---------------------------------------------------------------- los diez modelos
with t_diez:
    st.markdown("Los 5 modelos × 2 conjuntos de variables de la comparación final (`scripts/50_comparacion_final.py`), **siempre en los siete estados nuevos**. "
                "El modelo se escogió con 1991-2010, con un criterio fijado antes de correr; 2011-2025 es la confirmación.")
    fr = ac.tabla("final_resultados.csv")
    per = st.segmented_control("Periodo", ["seleccion 1991-2010", "confirmacion 2011-2025", "todo 1991-2025"], default="confirmacion 2011-2025",
                               key="lab_per10") or "confirmacion 2011-2025"
    f = fr[(fr["periodo"] == per) & ~fr["clave"].isin(["ref_azar"])].sort_values("auc")
    color = [ac.COLORES["prob"] if k == "splines_A" else ac.COLORES["ref_calor"] if k == "ref_calor" else ac.COLORES["ref_regla"] if k == "ref_regla"
             else ac.TINTA_2 if k.startswith("ref_") else ac.GRIS_SUAVE for k in f["clave"]]
    fig = go.Figure(go.Scatter(
        x=f["auc"], y=f["modelo"], mode="markers", marker=dict(color=color, size=11),
        error_x=dict(type="data", symmetric=False, array=f["auc_ic_sup"] - f["auc"], arrayminus=f["auc"] - f["auc_ic_inf"], thickness=2, width=0),
        hovertemplate="%{y}: %{x:.3f}<extra></extra>"))
    fig.update_layout(xaxis=dict(title="AUC con rango de 95 %", range=[0.3, 1]))
    st.plotly_chart(ac.estilo(fig, 560, leyenda=False), width="stretch")
    st.caption("Azul: el modelo elegido (logística con splines, clima mensual). Naranja: índice de calor. Verde: regla de lluvia. Los rangos se superponen: "
               "el orden entre modelos cambia según el periodo.")
    st.dataframe(f.sort_values("puntaje_eleccion", ascending=False)[["modelo", "auc", "auc_ic_inf", "auc_ic_sup", "auc_sin_2012", "auc_dentro_anio", "heidke",
                                                                     "puntaje_eleccion"]].round(3).rename(columns={
        "modelo": "Modelo", "auc": "AUC", "auc_ic_inf": "Rango inf.", "auc_ic_sup": "Rango sup.", "auc_sin_2012": "AUC sin 2012",
        "auc_dentro_anio": "AUC dentro del año", "heidke": "Heidke", "puntaje_eleccion": "Puntaje de elección"}), hide_index=True, width="stretch")
