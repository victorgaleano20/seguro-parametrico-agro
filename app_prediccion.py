"""
app_prediccion.py
Cálculos de la página "Predicción" (plan en docs/bitacora.md, 2026-11-12). Funciones puras, sin Streamlit, para
poder probarlas (tests/test_prediccion.py).

Disparadores (los mismos del proyecto):
- "modelo": probabilidad de pérdida del modelo final guardado; se activa si supera su umbral.
- "calor": índice de calor = tmax de julio + tmax de agosto frente a lo normal; se activa si supera su umbral.
- "regla": lluvia de junio a agosto en % de lo normal; se activa si queda bajo el percentil del condado.
El umbral sale de la frecuencia de pago: con frecuencia f, el modelo y el calor pagan en el f más alto de los diez
estados, y la regla en el f más seco de cada condado.
"""
import numpy as np
import pandas as pd

DISPARADORES = {"modelo": "Modelo final", "calor": "Índice de calor", "regla": "Regla de lluvia"}
NIVELES = [(0.10, "Bajo"), (0.25, "Medio"), (1.01, "Alto")]   # convención: tasa media de pérdida ~10 %


# ---------------------------------------------------------------- modelo
def predecir_probabilidad(modelo, columnas, valores):
    """Probabilidad de pérdida del modelo final para uno o varios escenarios (dict o DataFrame con las 13 columnas)."""
    x = pd.DataFrame([valores]) if isinstance(valores, dict) else valores
    faltan = [c for c in columnas if c not in x.columns]
    if faltan:
        raise ValueError(f"Faltan variables del modelo: {faltan}")
    return modelo.predict_proba(x[columnas])[:, 1]


# ---------------------------------------------------------------- umbrales y activación
def umbrales_globales(tabla, frecuencia):
    """Umbral del modelo y del índice de calor para pagar en la fracción `frecuencia` de los condado-años."""
    if not 0 < frecuencia < 1:
        raise ValueError("La frecuencia de pago debe estar entre 0 y 1.")
    return {"modelo": float(np.quantile(tabla["prob_modelo"], 1 - frecuencia)),
            "calor": float(np.quantile(tabla["indice_calor"], 1 - frecuencia))}


def umbral_regla(historia_condado, frecuencia):
    """Percentil `frecuencia` de la lluvia de junio a agosto (% de lo normal) en la historia del condado."""
    return float(np.quantile(historia_condado["lluvia_jja_pct"], frecuencia))


def puntaje(disparador, prob, indice_calor, lluvia_jja_pct):
    return {"modelo": prob, "calor": indice_calor, "regla": lluvia_jja_pct}[disparador]


def se_activa(disparador, valor, umbral):
    """El modelo y el calor pagan si su puntaje supera el umbral; la regla, si la lluvia queda por debajo."""
    return bool(valor <= umbral) if disparador == "regla" else bool(valor >= umbral)


def activaciones_historicas(historia_condado, disparador, umbrales, frecuencia):
    """Años de 1991-2025 en que el disparador se habría activado en el condado."""
    if disparador == "regla":
        u = umbral_regla(historia_condado, frecuencia)
        return historia_condado["lluvia_jja_pct"] <= u
    col = {"modelo": "prob_modelo", "calor": "indice_calor"}[disparador]
    return historia_condado[col] >= umbrales[disparador]


# ---------------------------------------------------------------- dinero
def calcular_pago(hectareas, suma_por_ha, porcentaje_pago):
    """Lo que paga la póliza si se activa: hectáreas × suma asegurada por hectárea × porcentaje que se paga."""
    if hectareas <= 0 or suma_por_ha <= 0 or not 0 < porcentaje_pago <= 1:
        raise ValueError("Hectáreas y suma asegurada deben ser positivas, y el porcentaje de pago entre 0 y 100 %.")
    return hectareas * suma_por_ha * porcentaje_pago


def calcular_prima(p_activacion, pago, recargo):
    """Prima pura = P(activación) × pago; prima comercial = prima pura × (1 + recargo)."""
    if not 0 <= p_activacion <= 1 or recargo < 0:
        raise ValueError("La probabilidad debe estar entre 0 y 1 y el recargo no puede ser negativo.")
    pura = p_activacion * pago
    return pura, pura * (1 + recargo)


def calcular_resultado(prima_cobrada, p_activacion, pago):
    """Resultado esperado de la aseguradora = prima cobrada − P(activación) × pago."""
    return prima_cobrada - p_activacion * pago


def resultado_escenario(prima_cobrada, activa, pago):
    """Lo que le queda a la aseguradora en un año concreto: la prima, menos el pago si el seguro se activa."""
    return prima_cobrada - (pago if activa else 0.0)


def nivel_riesgo(p):
    """Bajo / Medio / Alto según la probabilidad (convención: bajo la tasa media de ~10 %, hasta 25 %, más de 25 %)."""
    return next(etiqueta for tope, etiqueta in NIVELES if p < tope)


def riesgo_de_base(activa, p_perdida):
    """Si paga: probabilidad de pagar sin pérdida. Si no paga: probabilidad de pérdida sin pago."""
    return ("Paga sin pérdida", 1 - p_perdida) if activa else ("Pérdida sin pago", p_perdida)
