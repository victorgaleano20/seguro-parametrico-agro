"""
app.py - Seguro paramétrico de sequía para el maíz de EE. UU.: app para el jurado y para especialistas.

Solo LEE tablas ya calculadas en datos/procesados (no entrena nada): scripts 50, 53 y 54.
Las páginas están en paginas/ y comparten app_comun.py.
Uso, desde la carpeta del proyecto:
    streamlit run app.py
"""
import streamlit as st

st.set_page_config(page_title="Seguro paramétrico de maíz", page_icon=":material/agriculture:", layout="wide")

paginas = st.navigation([
    st.Page("paginas/resumen.py", title="Resumen", icon=":material/insights:", default=True),
    st.Page("paginas/contrato.py", title="Contrato y riesgo de base", icon=":material/payments:"),
    st.Page("paginas/laboratorio.py", title="Laboratorio de desempeño", icon=":material/science:"),
])
paginas.run()
