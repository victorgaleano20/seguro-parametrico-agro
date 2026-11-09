# Plan congelado del cierre (maíz de EE. UU.)

**Fecha:** 2026-11-05. **Estado:** escrito y subido a git ANTES de correr ninguna de las cuatro fases. El commit "Plan congelado del cierre" es la prueba de ese orden.

**Objetivo de la parte A:** cerrar cuatro preguntas que dejó abierta la prueba a ciegas (`docs/resultados_prueba_ciegas.md`). Todo es adicional: no se cambia el modelo principal ni sus resultados. Los datos y las predicciones de la prueba a ciegas (`ciegas_predicciones_principal.csv`) se leen tal cual.

**Qué se declara antes de empezar:**
- Los resultados de la prueba a ciegas ya se conocen. Lo único que no se ha visto es: el modelo sin ubicación, la recalibración con años locales, el contrato Palmer con topes, las causas de siniestros por estado y el semáforo por causa.
- Los criterios de abajo no se cambian después de ver resultados. Si no se cumplen, se dice.
- Si un dato falta o algo falla, se anota, se decide lo más razonable, se explica y se sigue.

## Fase 1. ¿El modelo aprende clima o geografía?

**Qué se hace.** Se repite la prueba a ciegas principal: cada año *t* de 1991 a 2025, el modelo se entrena solo con Iowa, Illinois e Indiana en años anteriores a *t* y predice los siete estados nuevos. Todo igual a `35_prueba_ciegas.py` (mismo LightGBM, misma rejilla de hiperparámetros escogida por AUC en los 3 años previos, misma calibración isotónica, mismo corte de pago, misma regla de lluvia, mismas semillas), con **un solo cambio**: se quitan latitud, longitud y la variable de estado (`grupo`). No queda ninguna variable que identifique el estado ni el condado. Quedan: lluvia de mayo a septiembre (% de lo normal), meses secos seguidos, falta de lluvia de julio y agosto, temperatura máxima de junio a agosto y Palmer de junio a agosto.

**Qué se compara.** Modelo sin ubicación, modelo original (el de la prueba a ciegas) y regla de lluvia, todos con la misma frecuencia de pago (la de la regla en los siete estados nuevos). Medidas: AUC, Heidke, % de pérdidas captadas, valor p barajando años completos (1.000 veces) e intervalos de 95 % remuestreando años completos (1.000 veces, semilla 2026). Todo con todos los años, sin 2012 y por estado (también 1995-2025 y sin condados con más de 25 % de riego, como contexto). Se reporta además la diferencia de AUC original menos sin ubicación con su intervalo (remuestreo de años pareado).

**Interpretación fijada.** Se mide con los siete estados nuevos juntos, todos los años 1991-2025:
- Si el AUC del modelo sin ubicación queda a **0,02 o menos** por debajo del original, el modelo aprende sobre todo clima.
- Si baja **más de 0,02**, parte de lo que aprende es geografía, y se dice.

## Fase 2. ¿Cuántos años locales hacen falta para entrar a un estado nuevo?

**Qué se hace.** En cada uno de los siete estados nuevos, con las probabilidades del modelo original (prueba principal, entrenado solo en los tres estados), se recalibra con regresión isotónica (la misma de `29`, límites 0 y 1) usando **solo los primeros K años disponibles de ese estado**, con K = 0, 3, 5, 10 y 15.
- Los años disponibles de predicción empiezan en 1991. Con K = 15 se usan 1991-2005.
- **K = 0:** no hay datos locales. Se usa la probabilidad calibrada de la prueba principal (calibrada con los tres estados originales).
- **K de 3 a 15:** la isotónica se ajusta, por estado, con la probabilidad sin calibrar (`prob`) y la pérdida real de los primeros K años de ese estado, y se aplica a los años posteriores.
- **Años de evaluación, iguales para todos los K: 2006-2025** (los años posteriores a los 15 de calibración más largos). Así todos los K son comparables.

**Qué se reporta.** Para cada K y cada estado, el Brier de la probabilidad recalibrada frente al Brier de la tasa media de pérdida de ese estado en los años de evaluación (la misma referencia de los resultados anteriores). Curva de calibración (diez grupos de igual tamaño por probabilidad, con los siete estados juntos) para cada K.

**Conclusión fijada.** El menor K con el que el Brier queda mejor que la tasa media en **al menos 5 de los 7 estados**. Si ningún K lo logra, se dice.

## Fase 3. Contrato Palmer con topes

**Disparador.** El de `37_palmer_ciegas.py`: promedio del Palmer de julio y agosto del condado bajo el percentil 15 de los años anteriores del condado (mínimo 10), con pago en línea recta hasta el 100 % en el percentil 2. Diez estados, 1991-2025 (las mismas filas de `ciegas_impacto_detalle.csv`).

**Dos cambios:**
1. **Suma asegurada** de 50 % y 75 % del valor esperado (más 100 % como referencia sin topes).
2. **Tope de pago total por año**, en los diez estados juntos, igual a **2 veces la prima pura anual** del mismo contrato y la misma suma asegurada. La prima pura anual es el pago total promedio por año de ese contrato sin tope, 1991-2025. Si un año se pasa del tope, todos los pagos de ese año se reducen en la misma proporción.

**Comparaciones.** Contrato Palmer con y sin tope, regla de lluvia (misma fórmula proporcional, con la misma regla de tope calculada con su propia prima) y modelo (pago = suma × severidad prevista cuando se activa el corte aplicable, también con y sin la misma regla de tope). Medidas: pagos totales, pago en 2012 frente a la pérdida real de 2012, % de la pérdida en dólares cubierta, de cada $100 cuántos llegan a quien perdió (condado-años con pérdida) y prima pura como % de la suma asegurada. Dólares de 2025.

**Interpretación fijada.** El contrato con topes es **"vendible"** si se cumplen las dos condiciones, en cada una de las sumas aseguradas (50 % y 75 %):
1. En **ningún año** de 1991-2025 el pago total de los diez estados supera **1,5 veces** la pérdida real de ese año (suma de los diez estados).
2. De cada $100 que paga, llegan a quien perdió **al menos lo mismo** que con la regla de lluvia con tope (misma suma y misma regla de tope). Se reporta también frente a la regla de lluvia sin tope.

Si no, se dice cuál condición falla y en qué años.

## Fase 4. Minnesota y un semáforo por causa de los siniestros

### A. Diagnóstico de Minnesota (descriptivo; no se afirman causas que los datos no muestren)
- **Fuente:** Cause of Loss de la RMA (`colsom_*.zip`, ya en `datos/crudos/eeuu/rma`), maíz (cultivo 0041), 1989-2025, diez estados, indemnización en dólares de 2025 (CPI-U, como `31`).
- **Grupos de causa (se fijan aquí):**
  - **Sequía:** código 11 (Drought). Es la misma definición que ya usa `31` para "indemnización por sequía". Calor (12) y viento caliente (62) quedan en "otras" y se muestran aparte en la tabla de detalle.
  - **Exceso de humedad:** 31 (Excess Moisture/Precipitation/Rain) y 51 (Flood).
  - **Heladas o frío:** 41 (Frost), 42 (Freeze), 43 (Cold Winter), 44 (Cold Wet Weather), 45 (Insufficient Chilling Hours).
  - **Granizo:** 21.
  - **Precio:** 01 (Decline in Price).
  - **Otras:** todo lo demás (calor, vientos, insectos, enfermedades, fauna, incendio, otras).
- **Qué se calcula:** por estado, la parte de las indemnizaciones por cada grupo; Minnesota frente a los otros nueve estados; y Minnesota en los **años de falla del modelo**, definidos como los años en que al menos 10 % de los condados de Minnesota con dato tuvieron pérdida y el modelo (prueba principal, mismo corte de pago de 35) captó menos de la mitad de esas pérdidas. Se compara la mezcla de causas en esos años contra los demás años de Minnesota y contra los otros estados en los mismos años.

### B. Semáforo por causa (alternativa al semáforo de `30` y `36`)
- **Para cada condado y cada año *t*:** con las indemnizaciones de maíz de los años 1989 a *t* − 1, la parte de sus indemnizaciones (dólares de 2025) que fue por sequía (código 11).
- **Condado elegible:** pasa los filtros de calidad de `36` (dato bueno con años anteriores a *t*) y tiene **al menos 10 años anteriores a *t* con indemnización de maíz mayor que cero**.
- **Colores, por terciles de esa parte, calculados cada año entre los condados elegibles de los diez estados** (corte en los percentiles 1/3 y 2/3, como en `36`):
  - **VERDE:** el tercio con más sequía (parte mayor al segundo corte).
  - **ROJO:** el tercio con menos sequía (parte menor o igual al primer corte), o el condado no pasa los filtros de calidad, o tiene menos de 10 años con siniestros.
  - **AMARILLO:** el resto.
- **Evaluación hacia adelante, diez estados:** todos los años *t* con al menos 10 años de indemnizaciones anteriores (1999-2025, porque la RMA empieza en 1989). Es la prueba principal. Con las predicciones del modelo de la prueba a ciegas y de la regla (como en `36`). Como comparación pareja se repite en 2006-2025, los mismos años del semáforo de `36`.
- **Criterio de éxito (el mismo de `36`, con el modelo):** los verdes superan a los rojos en Heidke, en % de pérdidas captadas y en "de cada $100 que llegan a quien perdió", y el intervalo de 95 % de la diferencia verde menos rojo (remuestreo de años completos, 1.000 veces, semilla 2026) **no incluye el cero** en las tres medidas.
- **Se reportan lado a lado** el semáforo de `36` (prueba 1, 2006-2025) y este. Si ninguno cumple, se dice.
- **Limitación que se declara de antemano:** "pocos años con siniestros" no es lo mismo que "poco riesgo". Un condado con pocos siniestros queda en rojo aunque sea de bajo riesgo real.

## Fase 5. Entregables del análisis

`docs/resultados_cierre.md` (plan, resultado de cada fase, si cada criterio se cumplió y qué significa, con "qué se puede decir y qué no"); figuras `docs/figuras/pitch_cierre_*.png` (modelo con y sin ubicación, calibración según años locales, Palmer con y sin topes año por año, causas de los siniestros por estado, semáforo por causa en años de prueba y mapa del semáforo por causa); `docs/requisitos_datos.md` actualizado si un resultado cambia una recomendación; scripts `40` a `44`; commit y push.

## Parte B (sin análisis nuevos y sin cambiar cifras)

Cuaderno final `notebooks/proyecto_final.ipynb` con su HTML sin código; resumen de una página; simulador listo para publicar; limpieza y actualización de CLAUDE.md, README, bitácora, metodología e historia del proyecto; pruebas; zip de contexto.

## Reglas de decisión si algo falla

- Un dato que no existe se anota, se decide lo más razonable, se explica y se sigue.
- Los criterios de arriba no se modifican después de ver resultados.
- Nunca se escriben claves en archivos.
