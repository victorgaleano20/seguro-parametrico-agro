# Metodología: el modelo y las métricas, explicados sin tecnicismos

Este documento explica **qué es "el modelo"** del seguro de sequía para el maíz de EE. UU., **cómo se construye cada pieza**, en qué archivo está, y **cómo se mide si sirve**. No hace falta saber de seguros ni de estadística. Las decisiones y sus razones están en `docs/historia_del_proyecto.md`, y el detalle de cada sesión en `docs/bitacora.md`.

---

## 1. Qué es "el modelo"

Hay dos formas de decidir cuándo paga el seguro, y el proyecto las compara:

- **La regla de lluvia** (la referencia): *"si la lluvia de junio a agosto queda en el 15 % de veranos más secos del condado, el seguro paga"*. Es transparente: cualquiera puede revisar la lluvia y el umbral y llegar al mismo resultado.
- **El modelo:** aprende de los años anteriores qué combinación de clima del verano (lluvia, meses secos seguidos, temperatura máxima e índice de sequía de Palmer, medidos frente a lo normal) anticipa una pérdida, y devuelve una probabilidad. El primero fue un LightGBM; el **modelo final** es una logística con curvas suaves (splines), elegida entre cinco modelos (sección 8).

Las dos se **evalúan** contra lo que pasó de verdad: ¿en los condados y años en que se perdió la cosecha, habrían pagado?

**Para comparar en igualdad, el modelo paga en tantos condado-años como la regla.** Así no gana solo por pagar más veces.

---

## 2. Las piezas

| Pieza | Definición exacta | Dónde está |
|---|---|---|
| **Unidad de análisis** | Condado × año, porque hay un solo ciclo de maíz al año. Tres estados de entrenamiento (Iowa, Illinois e Indiana) y siete de la prueba a ciegas. | `scripts/08_base_eeuu.py`, `28_base_eeuu.py` y `34_base_ciegas.py` |
| **Lluvia del condado** | Promedio de la lluvia mensual CHIRPS (píxeles de unos 5 km) de los píxeles cuyo centro cae dentro del condado. Si ningún centro cae adentro, se usa el píxel más cercano. | `scripts/comun.py`: `asignar_pixeles()` y `lluvia_mensual()` |
| **Temperatura y Palmer** | Temperatura máxima mensual e índice de sequía de Palmer de NOAA (nClimDiv) por condado. | `28_base_eeuu.py` y `34_base_ciegas.py` |
| **Rendimiento** | Producción / área cosechada de NASS, pasado a t/ha. | `08_base_eeuu.py` y `34_base_ciegas.py` |
| **Filtro de calidad** | Se excluyen (1) **rendimientos repetidos**: iguales, a 3 decimales, a los del año anterior, porque pueden ser un dato copiado, y (2) **condados con salto de área**: cambio de nivel de 5 veces o más entre la mediana del área cosechada antes y después de un año de corte, con al menos 3 años de cada lado. | `comun.py`: `salto_de_nivel()`; `08_base_eeuu.py` y `34_base_ciegas.py` |
| **Tendencia** | Recta (regresión lineal) del rendimiento contra el año, por condado, con 10 o más años válidos. Representa el rendimiento **esperado** de cada año, porque la tecnología sube los rendimientos con el tiempo. En la evaluación año por año se ajusta solo con años anteriores. | `comun.py`: `tendencia()` y `tendencia_ciclos()` |
| **Pérdida** | Un condado-año **es pérdida** si el rendimiento es de **80 % o menos del esperado** por la tendencia. Ejemplo: si se esperaban 10 t/ha y salieron 7,8 t/ha (78 %), es pérdida. | `comun.py`: `UMBRAL_PERDIDA = 0.8` |
| **Regla de lluvia** | Paga si la lluvia de junio a agosto queda bajo el percentil 15 de los años anteriores del condado. | `29_modelos_eeuu.py` y `35_prueba_ciegas.py` |
| **Modelos** | Primero: regresión logística, bosque aleatorio y LightGBM (se eligió LightGBM). Después: cinco modelos con y sin grados-día, probados a ciegas; ganó la logística con splines (sección 8). | `29_modelos_eeuu.py`, `47_cinco_modelos.py` y `50_comparacion_final.py` |
| **Calibración** | Regresión isotónica con los 3 años anteriores al que se predice, para que "30 %" signifique cerca de 3 de cada 10. | `29_modelos_eeuu.py` |
| **Pago del modelo** | Paga en los condado-años con mayor probabilidad, tantos como paga la regla. | `comun.py`: `pagar_igual_que_regla()` |
| **Contrato Palmer** | Paga si el Palmer de julio y agosto queda bajo el percentil 15 de los años anteriores del condado: 0 % en el percentil 15 y 100 % en el percentil 2, en línea recta. | `37_palmer_ciegas.py` y `42_palmer_topes.py` |
| **Pérdida y pagos en dólares** | Valor esperado de la cosecha = rendimiento esperado × área cosechada × precio nacional de la campaña (ERS), en dólares de 2025 (BLS). Lo que pagó el seguro real sale de la RMA. | `31_impacto_eeuu.py` y `38_impacto_ciegas.py`; `comun.py`: `leer_rma()` |
| **Prima comercial** | Prima pura (pago promedio por año) × (1 + recargo). **El recargo es un supuesto**, no se calculó con datos de ninguna aseguradora. | `31_impacto_eeuu.py` y `app.py` |

---

## 3. La tabla 2×2: la base de todas las métricas

Cada condado-año cae en una de cuatro casillas:

| | **Hubo pérdida** | **No hubo pérdida** |
|---|---|---|
| **El seguro paga** | **a** = acierto (pérdida con pago) | **b** = pago sin pérdida |
| **El seguro no paga** | **c** = pérdida sin pago | **d** = acierto (ni pérdida ni pago) |

**Ejemplo que se usa en todo el documento:** 100 condado-años, con 20 pérdidas y 20 pagos.

| | Hubo pérdida | No hubo pérdida | Total |
|---|---:|---:|---:|
| **Paga** | a = 10 | b = 10 | 20 |
| **No paga** | c = 10 | d = 70 | 80 |
| **Total** | 20 | 80 | 100 |

Las casillas **b** y **c** son el **riesgo de base**: el seguro se equivoca.

---

## 4. Las métricas

### 4.1 Aciertos esperados por azar

**Fórmula:** aciertos por azar = pagos × pérdidas / condado-años.

**Ejemplo:** 20 × 20 / 100 = **4**. Si el seguro pagara en 20 condado-años escogidos al azar, coincidiría con unas 4 pérdidas. En el ejemplo, el seguro tuvo 10.

**Cómo se lee:** si los aciertos observados se parecen a los del azar, el seguro no sirve.

### 4.2 Índice de Heidke

**Fórmula:** Heidke = 2 (a·d − b·c) / [ (a + c)(c + d) + (a + b)(b + d) ].

**Ejemplo:** 2 (10·70 − 10·10) / [ (20)(80) + (20)(80) ] = 1.200 / 3.200 = **0,375**.

**Si fuera puro azar** (a = 4, b = 16, c = 16, d = 64): 2 (256 − 256) / … = **0**.

| Heidke | Significa |
|---|---|
| 0 | Igual que el azar |
| 1 | Perfecto |
| Negativo | Peor que el azar |
| Alrededor de 0,3 | Ya es una señal útil (el modelo en los siete estados nuevos: 0,318) |

**Por qué no usar solo el "% de aciertos":** un seguro que nunca paga "acierta" en todos los años sin pérdida, y eso se ve bien sin servir para nada. El Heidke descuenta lo que se acertaría por casualidad.

Está en `comun.py`, `heidke()`.

### 4.3 AUC (acierto al ordenar)

**Idea:** si se toma al azar un condado-año con pérdida y otro sin pérdida, ¿con qué frecuencia el modelo le da más riesgo al que sí tuvo pérdida?

| AUC | Significa |
|---|---|
| 0,5 | Igual que tirar una moneda |
| 1 | Perfecto |
| 0,74 | El modelo en los siete estados nuevos (la regla de lluvia: 0,66) |

A diferencia del Heidke, no depende del umbral de pago: mide qué tan bien ordena el riesgo.

### 4.4 Valor p barajando años completos

**Idea:** ¿qué tan fácil es sacar este resultado por pura suerte?

**Cómo se calcula:**
1. Se **barajan años completos**: las pérdidas de todos los condados en un año se pasan juntas a otro año, y se comparan con el puntaje que el seguro dio en ese otro año. Se baraja el año entero, y no condado por condado, porque una sequía golpea a todos los condados a la vez.
2. Se recalcula la métrica. Esto se repite 1.000 veces.
3. Valor p = (veces en que la métrica barajada iguala o supera a la real + 1) / (1.000 + 1).

**Ejemplo:** si en 0 de las 1.000 barajadas se iguala el resultado real, p = 1/1.001 ≈ **0,001**: muy difícil que sea suerte. Si se iguala en 150, p ≈ **0,15**: podría ser suerte.

**Cómo se lee:** se usa p < 0,05 como "no parece suerte".

### 4.5 Rangos de 95 %

Se repite la cuenta muchas veces con años sorteados con reposición (1.000 remuestreos de años completos). El rango que deja fuera el 2,5 % más bajo y el 2,5 % más alto es el rango de 95 %. Si el rango de una diferencia incluye el cero, no se puede decir que la diferencia sea real.

### 4.6 Porcentaje de pérdidas sin pago y de pagos sin pérdida

- **Pérdidas sin pago:** c / (a + c). En el ejemplo, 10 / 20 = **50 %**: la mitad de las malas cosechas se quedarían sin pago. Es el error que más le duele al agricultor.
- **Pagos sin pérdida:** b / (a + b). En el ejemplo, 10 / 20 = **50 %**: la mitad de los pagos irían a condado-años en que la cosecha estuvo bien. Es el error que encarece la prima.

### 4.7 De cada $100 pagados, cuántos llegan a quien perdió

Es la versión en dólares de los pagos sin pérdida: la suma de lo que el seguro paga en condado-años con pérdida, dividida por todo lo que paga, por 100. Se compara con lo que daría pagar al azar. **No se compara con el seguro real de la RMA:** este paga por finca y por otras causas (precio, exceso de lluvia), así que medirlo con la pérdida del condado no es justo.

Está en `31_impacto_eeuu.py`, `simular()`, y en `38_impacto_ciegas.py`.

### 4.8 Brier (qué tan buenas son las probabilidades)

Es el promedio de (probabilidad − resultado)², donde el resultado es 1 si hubo pérdida y 0 si no. Entre más bajo, mejor. Se compara con usar siempre la tasa media de pérdida: si el modelo no la mejora, sus probabilidades no aportan.

---

## 5. El modelo de sequía para el maíz de EE. UU.

Detalle: `docs/resultados_modelo_eeuu.md` y `docs/impacto_economico_eeuu.md`.

**La pregunta.** Con el clima del verano, conocido a fines de septiembre, ¿se puede saber qué condados perdieron la cosecha de maíz y cuánto? Si se puede, un seguro paga sin visitar la finca.

| Pieza | Qué es, en palabras simples |
|---|---|
| Unidad | Un condado en un año: Iowa, Illinois e Indiana, 1981–2025 |
| Pérdida | Que el rendimiento quede en 80 % o menos de lo que se esperaba por la tendencia del condado |
| Clima | Lluvia por satélite de mayo a septiembre, temperatura máxima de junio a agosto y un índice de sequía de NOAA (Palmer), todo frente a lo normal del condado |
| Regla | Paga si la lluvia de junio a agosto queda en el 15 % más seco de la historia del condado |
| Modelos | Regresión logística, bosque aleatorio y LightGBM: aprenden de años anteriores qué combinación de clima anticipa una pérdida |
| Severidad | Un segundo modelo estima cuánto se queda corto el rendimiento cuando hay pérdida |
| Pérdida esperada | Probabilidad de pérdida × tamaño de la pérdida |

**Cómo se mide sin hacer trampa.** Cada año se predice con modelos que solo conocen los años anteriores, como si se estuviera en ese momento. También la tendencia y la pérdida salen solo de años anteriores. Se compara siempre con:
1. **el azar**;
2. **la regla de lluvia**;
3. **un modelo que solo sabe dónde está el condado**. Este último es el que dice cuánto agrega el clima.

**Por qué no una partición al azar de los datos.** El modelo vería el clima de los años que debe predecir. Cada año se predice solo con años anteriores, como pasaría en la vida real.

**El semáforo.** Para cada condado, con años hasta 2018:
- **Calidad del dato:** años con dato, cifras repetidas y saltos de área.
- **Sensibilidad:** cuánto responde la cosecha al clima del verano. Se acerca al promedio del estado, porque un condado tiene pocas pérdidas para medirse solo.

**La prueba del semáforo** es ver, en 2019–2025, si los verdes salen mejor que los rojos.

**El resultado, en una frase.** El clima sí anticipa la pérdida mucho mejor que la ubicación y que la regla, sobre todo el calor y la falta de agua de julio y agosto. Aun así, más de la mitad de lo que pagaría el seguro llega a condados sin pérdida, y el semáforo no se pudo comprobar.

## 6. La prueba a ciegas

Detalle: `docs/plan_prueba_ciegas.md` y `docs/resultados_prueba_ciegas.md`.

**Por qué.** Iowa, Illinois e Indiana se habían mirado muchas veces, así que ya no eran una prueba limpia. Y en 2019-2025 casi no hubo pérdidas (14), así que el semáforo no se podía probar.

**Cómo.** Se escribió el plan y se subió a git antes de bajar los datos de siete estados nuevos (Nebraska, Minnesota, Ohio, Missouri, Kansas, South Dakota y Wisconsin). El modelo, la regla y el semáforo se congelaron. El modelo se entrena solo con los tres estados originales, año por año hacia adelante, y predice los siete nuevos, que nunca se usan para entrenar, escoger ni calibrar.

**Con quién se compara.** La regla de lluvia, la tasa de pérdida de cada condado en sus años anteriores (en lugar de "solo ubicación", que no se traslada a otros estados) y el azar, todos con la misma frecuencia de pago.

**El criterio.** El modelo "pasa" si su AUC es al menos 0,05 mayor que el de la regla, su Heidke es mayor y el valor p (barajando años completos) es menor de 0,05. Los criterios se fijaron antes de ver los resultados.

**El semáforo, otra vez.** Dos pruebas: año por año con colores recalculados solo con años anteriores, y colores de los estados nuevos con datos hasta 2018 probados en 2019-2025. Se cumple si los verdes superan a los rojos en tres medidas con un rango de 95 % que no incluya el cero.

**El contrato con Palmer.** Un contrato que se puede escribir: paga si el índice de sequía de Palmer de julio y agosto queda bajo el percentil 15 de los años anteriores del condado, con pago proporcional hasta el percentil 2. Si queda a 0,03 o menos del modelo, se puede proponer como contrato simple.

## 7. El cierre

Plan: `docs/plan_cierre.md`; resultados: `docs/resultados_cierre.md`.

- **¿Clima o geografía?** Se repitió la prueba a ciegas quitando latitud, longitud y estado. Si el acierto baja 0,02 o menos, el modelo aprende sobre todo clima. Bajó 0,005.
- **Años locales.** Una probabilidad "calibrada" es una que, cuando dice 30 %, se cumple 3 de cada 10 veces. Para calibrar en un estado nuevo se ajusta una curva escalonada (regresión isotónica) con los primeros K años de ese estado y se mide siempre en los mismos años posteriores (2006-2025). Se compara con la tasa media del propio estado: si el Brier queda mejor, la probabilidad aporta algo. Hacen falta 15 años para lograrlo en 5 de 7 estados.
- **Contrato con topes.** El pago es proporcional (0 en el percentil 15 del Palmer del condado y 100 % en el percentil 2). El tope anual es 2 veces la prima pura, es decir, 2 veces lo que el contrato paga en promedio por año en los diez estados; si un año se pasa, todos los pagos de ese año bajan en la misma proporción. "Vendible" quiere decir: en ningún año paga más de 1,5 veces la pérdida real y manda a quien perdió al menos lo mismo que la regla de lluvia.
- **Causas de siniestros.** Con las indemnizaciones de maíz de la RMA agrupadas en sequía (código 11), exceso de humedad (31 y 51), heladas o frío (41 a 45), granizo (21), precio (01) y otras, en dólares de 2025. Es descriptivo.
- **Semáforo por causa.** Cada año, con los siniestros anteriores, el tercio de condados con más parte pagada por sequía es verde y el de menos es rojo (también rojo si el dato es dudoso o hay menos de 10 años con siniestros). Se mide igual que el semáforo anterior: los verdes deben superar a los rojos con un margen de error de 95 % que no incluya el cero. No se cumple.

---

## 8. Cinco modelos y el modelo final

Detalle: `docs/bitacora.md` (partes cuarta a décima) y la sección 8 del cuaderno final.

**Los cinco modelos:**
| Modelo | Qué hace, en palabras simples |
|---|---|
| Regresión logística | Suma ponderada de las variables, convertida en probabilidad |
| Logística con splines (**el elegido**) | Igual, pero cada variable entra como una curva suave, así puede capturar que el riesgo sube rápido con mucho calor o con exceso de agua |
| Bosque aleatorio | Promedio de cientos de árboles de decisión |
| Boosting de gradiente | Árboles en secuencia, cada uno corrige al anterior (como LightGBM) |
| Boosting monótono | Boosting obligado a que más calor o más sequía nunca bajen el riesgo |

**Conjuntos de variables:** A = clima del verano medido frente a lo normal del condado (lluvia de mayo a septiembre, meses secos seguidos, déficit de julio y agosto, temperatura máxima y Palmer de junio a agosto); B = A más grados-día de calor diario en valor absoluto. Sin ubicación, porque en estados nuevos queda fuera de rango.

**Grados-día:** con la temperatura máxima y mínima de cada día se dibuja una curva seno y se mide cuánto pasa por encima de un umbral. Los grados-día por encima de 29 °C miden el calor que daña al maíz (Schlenker y Roberts, 2009).

**Cómo se eligió:** entrenando solo con Iowa, Illinois e Indiana y prediciendo año por año los siete estados nuevos. Se escogió con 1991-2010 (puntaje = promedio del AUC global y del AUC dentro de cada año); 2011-2025 solo confirma. El criterio se fijó antes de correr.

**Calibración:** la isotónica con los 3 años más recientes empeoraba las probabilidades cuando esos años tenían pocas pérdidas; el modelo final se usa sin calibrar.

**Comparación justa en dólares:** todos los disparadores pagan en la misma cantidad de condado-años y con el mismo monto (tamaño medio de las pérdidas de años anteriores); solo cambia a quién se paga.

---

## 9. Lo que NO afirmamos

- **No** decimos que el semáforo funcione: ninguno de los dos cumplió el criterio.
- **No** decimos que el modelo sirva en cualquier estado: en Minnesota no distingue mejor que el azar y en Wisconsin pierde contra la regla.
- **No** decimos que sus probabilidades estén calibradas en un estado nuevo sin unos 15 años de datos locales.
- **No** decimos que el contrato Palmer con topes sea vendible tal cual.
- **No** decimos que el índice reemplace al seguro real: este cubre más riesgos (precio, exceso de lluvia) y paga por finca. El costo de operar el índice es un supuesto.
- **No** decimos que el modelo "predice la cosecha": se evalúa con el clima de todo el verano, a fines de septiembre.
- **No** decimos que el índice dirija la plata igual o mejor que el seguro real: no se midieron con la misma vara.
- **No** decimos que el aprendizaje automático sea mucho mejor que un índice simple de calor: la ventaja es pequeña y, en dólares, desaparece.

**Pruebas automáticas:** `tests/` comprueba que las funciones clave hacen lo que dicen, por ejemplo que el Heidke dé 0,375 en el ejemplo de la sección 4.2.
