"""Pruebas de las funciones clave. Uso, desde la carpeta del proyecto:  python -m pytest tests"""
import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import comun  # noqa: E402


def test_heidke_coincide_con_el_ejemplo_de_la_metodologia():
    perdida = np.array([True] * 20 + [False] * 80)
    pago = np.array([True] * 10 + [False] * 10 + [True] * 10 + [False] * 70)
    assert comun.heidke(perdida, pago) == pytest.approx(0.375)


def test_heidke_es_cero_si_el_pago_es_independiente_de_la_perdida():
    perdida = np.array([True] * 20 + [False] * 80)
    pago = np.array([True] * 4 + [False] * 16 + [True] * 16 + [False] * 64)
    assert comun.heidke(perdida, pago) == pytest.approx(0.0)


def test_particion_no_repite_anios_y_respeta_el_orden():
    entrenamiento, validacion, prueba = comun.particion(range(1981, 2026))
    assert max(entrenamiento) < min(validacion) and max(validacion) < min(prueba)
    assert len(entrenamiento) + len(validacion) + len(prueba) == 45


def test_pago_con_la_misma_frecuencia_escoge_los_puntajes_mas_altos():
    pago = comun.pagar_igual_que_regla(np.array([0.1, 0.9, 0.5, 0.2]), 0.5)
    assert pago.tolist() == [False, True, True, False]
    assert not comun.pagar_igual_que_regla(np.array([0.1, 0.9]), 0).any()


def test_fases_de_el_nino_en_sus_limites():
    assert comun.fase_oni(np.array([0.5, 0.49, -0.49, -0.5])).tolist() == ["El Niño", "Neutral", "Neutral", "La Niña"]


def test_tendencia_recupera_una_recta_y_marca_la_caida():
    anios = np.arange(1991, 2004)
    rendimiento = 1.0 + 0.1 * (anios - 1991)
    rendimiento[-1] *= 0.5
    d = pd.DataFrame({"unidad": "A", "anio": anios, "rendimiento_t_ha": rendimiento})
    t = comun.tendencia(d)
    assert t.iloc[-1]["relativo"] < t.iloc[0]["relativo"]


def test_tendencia_descarta_series_cortas():
    d = pd.DataFrame({"unidad": ["A"] * 5 + ["B"] * 12, "anio": list(range(1991, 1996)) + list(range(1991, 2003)), "rendimiento_t_ha": np.linspace(1, 2, 17)})
    assert set(comun.tendencia(d)["unidad"]) == {"B"}


def test_tendencia_sin_anios_futuros_no_cambia_si_cambia_el_futuro():
    anios = np.arange(1991, 2004)
    d = pd.DataFrame({"unidad": "A", "anio": anios, "rendimiento_t_ha": 1.0 + 0.1 * (anios - 1991)})
    otra = d.copy()
    otra.loc[otra["anio"] > 1999, "rendimiento_t_ha"] = 99.0
    a = comun.tendencia(d, 1999, 8).query("anio <= 1999")["esperado"].to_numpy()
    b = comun.tendencia(otra, 1999, 8).query("anio <= 1999")["esperado"].to_numpy()
    assert a == pytest.approx(b)


e29 = importlib.import_module("29_modelos_eeuu")
e31 = importlib.import_module("31_impacto_eeuu")


def test_el_modelo_paga_en_tantos_condado_anios_como_la_regla_en_todo_el_periodo():
    d = pd.DataFrame({"anio": [2000] * 4 + [2001] * 4, "prob": [0.9, 0.1, 0.5, 0.2, 0.3, 0.8, 0.7, 0.1],
                      "pago_regla": [True, True, True, False, False, False, False, False]})
    pago = e29.igual_que_regla(d, "prob")
    # La regla paga 3 veces, todas en 2000; el modelo paga sus 3 puntajes más altos, sin copiar el año de la regla
    assert pago.tolist() == [True, False, False, False, False, True, True, False]


def test_simulacion_cuenta_bien_los_pagos_mal_dirigidos():
    d = pd.DataFrame({"anio": [2019, 2019, 2020, 2020], "valor_esperado_usd": [100.0] * 4, "severidad_prevista": [0.5] * 4,
                      "perdida": [True, False, True, False], "perdida_usd": [40.0, 0, 60.0, 0],
                      "pago_regla": [True, True, False, False], "pago_umbral": [True, False, True, False]})
    regla, modelo = e31.simular(d, 1.0, 0.3, 0.5)
    assert regla["de_cada_100_pagados"] == pytest.approx(50) and modelo["de_cada_100_pagados"] == pytest.approx(100)
    assert modelo["pagos_sin_perdida_usd"] == 0 and regla["perdida_sin_pago_usd"] == pytest.approx(60)
    assert modelo["pct_perdida_cubierta"] == pytest.approx(100 * (40 + 50) / 100)
    assert modelo["prima_con_recargo_anual_usd"] == pytest.approx(1.3 * 100 / 2)


def test_salto_de_nivel_detecta_un_cambio_de_area():
    assert comun.salto_de_nivel(pd.Series([100.0] * 5 + [600.0] * 5)) == pytest.approx(6.0)
    assert comun.salto_de_nivel(pd.Series([100.0] * 10)) == pytest.approx(1.0)


def test_tendencia_ciclos_marca_perdida_bajo_el_80_por_ciento():
    anios = np.arange(1991, 2004)
    rendimiento = 10.0 + 0.0 * anios
    rendimiento[-1] = 5.0
    d = pd.DataFrame({"fips": "19001", "anio": anios, "rendimiento_t_ha": rendimiento})
    t = comun.tendencia_ciclos(d, ["fips"], 10)
    assert t["perdida"].tolist() == [False] * 12 + [True]


e49 = importlib.import_module("49_temperatura_diaria")


def test_grados_dia_con_el_metodo_del_seno():
    tmin, tmax = np.array([20.0, 30.0, 10.0]), np.array([38.0, 40.0, 25.0])
    # Cruza el umbral: media 29, amplitud 9 -> 9 / pi; todo el día arriba: 35 - 29 = 6; nunca llega: 0
    assert e49.grados_dia(tmin, tmax, 29.0) == pytest.approx([9 / np.pi, 6.0, 0.0])


def test_grados_dia_crecen_con_el_calor():
    base = e49.grados_dia(np.array([18.0]), np.array([32.0]), 29.0)[0]
    mas = e49.grados_dia(np.array([18.0]), np.array([36.0]), 29.0)[0]
    assert 0 < base < mas


def test_las_siglas_de_noaa_se_traducen_al_fips_del_census():
    assert e49.SIGLA_A_FIPS["IA"] == "19" and e49.SIGLA_A_FIPS["IL"] == "17" and e49.SIGLA_A_FIPS["NE"] == "31"
    assert len(set(e49.SIGLA_A_FIPS.values())) == 10
