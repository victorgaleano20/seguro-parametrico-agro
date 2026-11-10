"""Pruebas de la app: las cifras coinciden con las de los scripts 50 y 53, y cada página carga sin errores.
Uso, desde la carpeta del proyecto:  python -m pytest tests"""
import sys
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
PROCESADOS = RAIZ / "datos" / "procesados"
falta = not (PROCESADOS / "modelo_final_predicciones.csv").exists() or not (PROCESADOS / "app_metricas.csv").exists()
pytestmark = pytest.mark.skipif(falta, reason="faltan las tablas de 53 y 54 en datos/procesados")


def test_metricas_de_54_coinciden_con_50_y_53():
    met = pd.read_csv(PROCESADOS / "app_metricas.csv").set_index(["grupo", "periodo", "puntaje"])
    fr = pd.read_csv(PROCESADOS / "final_resultados.csv").set_index(["periodo", "clave"])
    for periodo, periodo_50 in [("todo", "todo 1991-2025"), ("confirmacion", "confirmacion 2011-2025"), ("seleccion", "seleccion 1991-2010")]:
        assert met.loc[("siete", periodo, "prob"), "auc"] == pytest.approx(fr.loc[(periodo_50, "splines_A"), "auc"], abs=1e-6)
        assert met.loc[("siete", periodo, "ref_calor"), "auc"] == pytest.approx(fr.loc[(periodo_50, "ref_calor"), "auc"], abs=1e-6)
        assert met.loc[("siete", periodo, "ref_regla"), "auc"] == pytest.approx(fr.loc[(periodo_50, "ref_regla"), "auc"], abs=1e-6)
    m53 = pd.read_csv(PROCESADOS / "modelo_final_metricas.csv")
    m53 = m53[m53["grupo"] == "diez estados"].set_index("puntaje")
    assert met.loc[("diez", "todo", "prob"), "auc"] == pytest.approx(m53.loc["Modelo final", "auc"], abs=1e-6)
    assert met.loc[("diez", "todo", "prob"), "auc_dentro"] == pytest.approx(m53.loc["Modelo final", "auc_dentro_anio"], abs=1e-6)


def test_contrato_reproduce_los_dolares_de_53():
    import app_comun as ac
    d = ac.predicciones()
    res, _ = ac.contrato(d, d["pago_regla"].mean())
    r = res.set_index("clave")["de_cada_100"]
    d53 = pd.read_csv(PROCESADOS / "modelo_final_dolares.csv")
    d53 = d53[(d53["grupo"] == "diez estados") & (d53["periodo"] == "1991-2025")].set_index("disparador")["de_cada_100"]
    assert r["prob"] == pytest.approx(d53["Modelo final"], abs=1e-6)
    assert r["ref_regla"] == pytest.approx(d53["Regla de lluvia jun-ago"], abs=1e-6)
    assert r["azar"] == pytest.approx(d53["Pagar al azar"], abs=1e-6)
    assert r["ref_calor"] == pytest.approx(d53.filter(like="calor").iloc[0], abs=1e-6)


def test_todos_los_disparadores_pagan_lo_mismo():
    import app_comun as ac
    g = ac.filtrar(ac.predicciones(), "siete")
    for f in (0.05, g["pago_regla"].mean(), 0.30):
        n = {k: int(v.sum()) for k, v in ac.pagos(g, f).items()}
        assert len(set(n.values())) == 1, n


def test_veredicto_solo_supera_si_el_rango_excluye_el_cero():
    import numpy as np
    import app_comun as ac
    assert ac.veredicto(np.linspace(0.01, 0.1, 100))[0] == "supera"
    assert ac.veredicto(np.linspace(-0.02, 0.1, 100))[0] == "no se distingue"
    assert ac.veredicto(np.linspace(-0.1, -0.01, 100))[0] == "queda por debajo"


@pytest.mark.parametrize("pagina", ["paginas/resumen.py", "paginas/contrato.py", "paginas/laboratorio.py"])
def test_cada_pagina_carga_sin_errores(pagina):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180).run()
    at.switch_page(pagina).run()
    assert not at.exception, [e.value for e in at.exception]
