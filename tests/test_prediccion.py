"""Pruebas de la página "Predicción": funciones de app_prediccion.py y carga de la página.
Uso, desde la carpeta del proyecto:  python -m pytest tests"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
import app_prediccion as ap  # noqa: E402

TABLA = RAIZ / "datos" / "procesados" / "app_prediccion.csv"


def test_prima_y_resultado():
    pura, comercial = ap.calcular_prima(0.2, 1000, 0.3)
    assert pura == pytest.approx(200) and comercial == pytest.approx(260)
    assert ap.calcular_resultado(comercial, 0.2, 1000) == pytest.approx(60)          # en promedio, justo el recargo
    assert ap.resultado_escenario(comercial, True, 1000) == pytest.approx(-740)
    assert ap.resultado_escenario(comercial, False, 1000) == pytest.approx(260)


def test_pago_y_validaciones():
    assert ap.calcular_pago(100, 2000, 0.35) == pytest.approx(70000)
    with pytest.raises(ValueError):
        ap.calcular_pago(0, 2000, 0.35)
    with pytest.raises(ValueError):
        ap.calcular_prima(1.5, 1000, 0.3)
    with pytest.raises(ValueError):
        ap.umbrales_globales(pd.DataFrame({"prob_modelo": [0.1], "indice_calor": [1.0]}), 0)


def test_activacion_y_riesgo_de_base():
    assert ap.se_activa("modelo", 0.5, 0.3) and not ap.se_activa("modelo", 0.2, 0.3)
    assert ap.se_activa("regla", 60, 70) and not ap.se_activa("regla", 90, 70)       # la regla paga con poca lluvia
    assert ap.riesgo_de_base(True, 0.3) == ("Paga sin pérdida", pytest.approx(0.7))
    assert ap.riesgo_de_base(False, 0.3) == ("Pérdida sin pago", pytest.approx(0.3))
    assert [ap.nivel_riesgo(p) for p in (0.05, 0.15, 0.6)] == ["Bajo", "Medio", "Alto"]


@pytest.mark.skipif(not TABLA.exists(), reason="falta app_prediccion.csv (script 56)")
def test_frecuencia_de_activacion_en_los_diez_estados():
    t = pd.read_csv(TABLA, dtype={"unidad": str})
    u = ap.umbrales_globales(t, 0.144)
    for disparador in ("modelo", "calor"):
        tasa = ap.activaciones_historicas(t, disparador, u, 0.144).mean()
        assert tasa == pytest.approx(0.144, abs=0.002)


@pytest.mark.skipif(not TABLA.exists(), reason="falta app_prediccion.csv (script 56)")
def test_probabilidad_coincide_con_la_tabla():
    import joblib
    paquete = joblib.load(RAIZ / "modelos" / "modelo_final.joblib")
    t = pd.read_csv(TABLA, dtype={"unidad": str}).head(50)
    p = ap.predecir_probabilidad(paquete["modelo"], paquete["columnas"], t)
    assert np.allclose(p, t["prob_modelo"], atol=1e-4)


@pytest.mark.skipif(not TABLA.exists(), reason="falta app_prediccion.csv (script 56)")
def test_la_pagina_carga_en_escenario_y_en_proyeccion():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=180).run()
    at.switch_page("paginas/prediccion.py").run()
    assert not at.exception, [e.value for e in at.exception]
    at.number_input(key="pre_anio").set_value(2030).run()
    assert not at.exception, [e.value for e in at.exception]
    at.number_input(key="pre_anio").set_value(2012).run()
    for d in ("calor", "regla"):
        at.session_state["pre_disparador"] = d
        at.run()
        assert not at.exception, [e.value for e in at.exception]
