# Plan congelado de la prueba a ciegas (maíz de EE. UU.)

**Fecha:** 2026-11-05. **Estado:** escrito y subido a git ANTES de descargar o mirar cualquier dato de los estados nuevos (Nebraska, Minnesota, Ohio, Missouri, Kansas, South Dakota y Wisconsin). El commit "Plan congelado de la prueba a ciegas" es la prueba de ese orden.

**Qué no se ha visto:** rendimientos, pérdidas, lluvia, temperatura, Palmer, riego ni siniestros de los estados nuevos. Solo se comprobó que la clave de NASS funciona, con una consulta de conteo (sin valores).

**Qué sí se ha visto, y se declara:** Iowa, Illinois e Indiana se miraron varias veces. Por eso la prueba a ciegas usa estados que nunca se han mirado.

**Objetivo:** probar mejor lo que ya existe, sin modelos ni variables nuevas. Todo lo de abajo queda congelado. Si algo se cambia después de ver resultados, se anota como cambio y se reporta aparte, no como parte de la prueba.

## 1. Lo que queda fijo (no se toca)

| Pieza | Valor congelado | Dónde está |
|---|---|---|
| Modelo | LightGBM de `29_modelos_eeuu.py`, variables "todas": latitud, longitud, estado, lluvia de mayo a septiembre (% de lo normal 1981-1994), meses secos seguidos, falta de lluvia de julio y agosto, temperatura máxima de junio a agosto, Palmer de junio a agosto. **Sin riego** (el modelo congelado no lo usó) | `29_modelos_eeuu.py` |
| Hiperparámetros | Rejilla de LightGBM de `20_modelos.py` (hojas 7, 15, 31; hoja mínima 20, 50), escogidos por AUC en los 3 años previos a t; si en esos 3 años no hubo pérdidas, la primera opción de la rejilla | `escoger` de `29` |
| Calibración | Regresión isotónica con los 3 años previos a t | `hacia_adelante` de `29` |
| Corte de pago | El que, en los 3 años previos a t, paga con la misma frecuencia que la regla de lluvia (`pago_umbral`) | `29` |
| Severidad | LightGBM de regresión, 200 árboles, 7 hojas, hoja mínima 20, tasa 0,03, solo filas con pérdida | `29` |
| Regla de lluvia | Lluvia CHIRPS de junio a agosto bajo el percentil 15 del condado, con sus propios años anteriores a t (mínimo 10 años) | `regla` de `29` |
| Pérdida | Rendimiento de 80 % o menos del esperado; el esperado sale de la tendencia lineal del condado con **solo años anteriores a t** (mínimo 8 años válidos) | `etiquetas_previas` de `29` |
| Filtros de calidad | Rendimiento = producción / área cosechada; se excluyen cifras repetidas respecto al año anterior y condados con salto de área de 5 veces o más; condados con al menos 15 años válidos | `08` y `28` |
| Semáforo | Regla de `30_semaforo_eeuu.py`: dato bueno (al menos 25 años válidos, a lo sumo 5 % de repetidos, sin salto de área), sensibilidad con encogimiento de Bayes empírico por estado, terciles; verde = dato bueno y tercil alto; rojo = dato malo o tercil bajo; amarillo = el resto | `30` |
| Contrato Palmer | Fase 3B de abajo | este plan |
| Semillas y remuestreos | Semilla 2026; 1.000 remuestreos de años; 1.000 barajadas de años completos | `29` |

Dos aclaraciones que se fijan aquí:
- Las variables tipo "lo normal" usan 1981-1994 en cada condado, como en los tres estados originales. Esa ventana se cruza con los primeros años evaluados (1991-1994). Para ver si importa, se reporta también la evaluación 1995-2025 como línea secundaria.
- La variable "estado" de los estados nuevos no existe en el entrenamiento; el codificador la ignora (queda en ceros). No se cambia.

## 2. Datos de los estados nuevos (Fase 1)

- **Estados, en orden de prioridad si algo no cabe:** Nebraska, Minnesota, Ohio, Missouri, Kansas, South Dakota, Wisconsin. Cualquier descarga de más de 500 MB no se hace: se usan menos estados y se anota.
- **NASS (API, con clave en la variable de entorno, nunca en archivos):** rendimiento, producción, área cosechada y área sembrada de maíz para grano por condado, 1981 a 2025. Área de maíz con riego por condado de los censos 1997, 2002, 2007, 2012, 2017 y 2022, para los estados nuevos y los tres originales.
- **Lluvia CHIRPS por condado:** el mismo método de `27`/`08` (recorte CHIRPS mensual de la IRI Data Library, promedio por polígono de condado con `04_lluvia_municipios.lluvia_mensual`), con un recuadro que cubra los siete estados.
- **Temperatura máxima y Palmer:** los archivos nClimDiv de NOAA que ya están (cubren todo el país).
- **RMA:** Cause of Loss y Summary of Business que ya están en `datos/crudos`; se verifica que incluyan estos estados.
- **Mismos filtros de calidad y misma definición de pérdida** de la sección 1.
- Todo se anota en `datos/crudos/registro_descargas.csv`, sin la clave.

## 3. Prueba a ciegas del modelo (Fase 2, resultado principal)

**Prueba principal.** Para cada año t de 1991 a 2025:
1. Se entrena **solo con Iowa, Illinois e Indiana, años anteriores a t**. Los hiperparámetros, la calibración y el corte de pago salen también solo de esos tres estados.
2. Se predice cada condado de los siete estados nuevos en el año t.
3. Los estados nuevos **nunca** se usan para entrenar, escoger hiperparámetros ni calibrar.

**Variante secundaria.** Igual, pero entrenando con los tres estados más los años anteriores a t de los estados nuevos.

**Con quién se compara (todos con la misma frecuencia de pago, es decir, pagan en tantos condado-años como la regla en el conjunto evaluado):**
- la regla de lluvia (percentiles de cada condado con sus propios años anteriores);
- la **tasa histórica de pérdida de cada condado** con sus años anteriores (puntaje = su tasa de pérdida previa; reemplaza a "solo ubicación", que no se traslada a otros estados);
- el azar (permutaciones de años completos y pagar al azar).

**Métricas, en los estados nuevos, 1991-2025:** AUC, Heidke, % de pérdidas captadas, % de alertas sin pérdida, Brier (calibrado y de la tasa media), intervalos de 95 % remuestreando años completos y valor p barajando años completos. Todo con y sin 2012, y por estado. También 1995-2025 (ver sección 1).

**Corte de riego fijado:** se reporta también sin los condados con **más de 25 %** del área de maíz para grano cosechada con riego (promedio de los censos disponibles). Ese corte de 25 % queda fijado aquí y se aplica a todos los estados, no solo a Nebraska o Kansas.

**Criterio de éxito (se evalúa con los siete estados nuevos juntos, 1991-2025, todos los años, prueba principal):**
1. AUC del modelo al menos **0,05 mayor** que el de la regla, y
2. Heidke del modelo **mayor** que el de la regla, y
3. valor p del AUC del modelo (barajando años completos) **menor de 0,05**.

Si falla alguna de las tres, se reporta que **no pasó**. Las versiones sin 2012, sin riego alto, por estado y la variante secundaria se reportan como contexto y no cambian el veredicto.

## 4. Dos pruebas del semáforo, con pérdidas (Fase 3A)

**Regla del color:** la de `30` (sección 1), que corrió sin dato de riego. **Variante fijada:** la misma regla, más "rojo si más de 25 % del área de maíz tiene riego" (riego con solo censos anteriores al año de los colores en la prueba 1, y censos hasta 2017 en la prueba 2). Los terciles de sensibilidad se calculan entre los condados con al menos 10 años de datos.

- **Prueba 1 (hacia adelante):** cada año t se recalculan los colores con la regla congelada usando **solo años anteriores a t**, en los diez estados juntos (terciles y encogimiento con los condados de los diez estados, por estado). Se evalúa en todos los años t en que hay al menos 25 años previos para colorear (de 2006 a 2025). Las predicciones del modelo y de la regla son las de la validación hacia adelante (tres estados originales) y las de la prueba a ciegas principal (siete nuevos).
- **Prueba 2 (geográfica):** colores de los **estados nuevos** con sus años hasta 2018 (terciles y encogimiento entre los siete estados nuevos), evaluados en 2019-2025.

**Qué se mide por color:** AUC, Heidke, % de pérdidas captadas y "de cada $100 que paga el seguro, cuántos llegan a quien perdió" (pago = suma asegurada de 100 % × valor esperado × severidad prevista, cuando el disparador se activa; mismo cálculo de `31_impacto_eeuu.py`, con el corte aplicable). Con el modelo y con la regla.

**Criterio de éxito (se evalúa con el modelo, en cada prueba):** los verdes superan a los rojos en Heidke, en % de pérdidas captadas y en "de cada $100 que llegan a quien perdió", **y** el intervalo de 95 % de la diferencia verde − rojo (remuestreando años completos, 1.000 veces) **no incluye el cero** en las tres métricas. Se reporta por separado la regla base y la variante con riego.

**Se reporta además** que la primera prueba (2026-11-04, partición fija 2019-2025) falló, y por qué: los condados verdes no tuvieron ni una pérdida en un periodo con solo 14 pérdidas, así que no había con qué comparar, y Iowa quedó casi todo rojo por la inundación de 1993.

## 5. Contrato simple con el índice de Palmer (Fase 3B)

- **Índice:** promedio del Palmer (PDSI de NOAA) de julio y agosto del condado en el año t.
- **Disparador y pago proporcional:** paga cuando ese promedio queda **por debajo del percentil 15** de los valores de los años anteriores a t de ese condado (mínimo 10 años). El pago es **0 en el percentil 15 y 100 % de la suma asegurada en el percentil 2**, en línea recta; por debajo del percentil 2 paga el 100 %. Los percentiles se calculan con la interpolación lineal de `numpy.quantile` sobre los años anteriores.
- **Misma fórmula para la regla de lluvia:** lluvia de junio a agosto, mismos percentiles 15 y 2 del condado, con años anteriores.
- **Comparación en igualdad:** Palmer, regla de lluvia y modelo con la **misma frecuencia de pago** (la del contrato Palmer en el conjunto evaluado; regla y modelo se igualan por puntaje). El pago en dólares del Palmer y de la regla es el proporcional de arriba; el del modelo es suma × severidad prevista cuando se activa.
- **Métricas, en los estados nuevos y en los originales:** AUC (puntaje del Palmer: su distancia estandarizada bajo la media de años anteriores del condado, cambiada de signo), Heidke, % de la pérdida en dólares cubierta y "de cada $100, cuántos llegan a quien perdió".
- **Interpretación fijada:** si el AUC del Palmer queda a **0,03 o menos** del AUC del modelo, se puede proponer como contrato simple. Si no, el modelo aporta algo que el contrato no captura.

## 6. Impacto económico (Fase 4)

- Se repiten los cálculos de `31_impacto_eeuu.py` para los siete estados nuevos y para los diez juntos: dólares de 2025 (CPI-U), pérdida real, indemnización de la RMA (por sequía y en total), subsidio real, y seguro simulado con modelo, regla y Palmer. Suma asegurada de 100 % (y 75 % como sensibilidad), recargo de 30 % (supuesto).
- **Costo de operar el seguro real:** se buscan en fuentes oficiales (RMA, USDA, GAO, CBO) los reembolsos a las aseguradoras por gastos de administración y operación (A&O) y el tiempo medio de pago de una indemnización, con cada fuente citada. Si no hay cifras de maíz, se usan las del programa completo y se dice.
- **De cada $100 que llegan a quien perdió, cuánto cuesta administrarlo.** Seguro real: A&O reembolsado sobre la prima de los condado-años, dividido entre las indemnizaciones que llegan a condado-años con pérdida. Índice: el costo de operar es un **SUPUESTO**; se prueban 5 %, 10 % y 20 % de la prima pura, marcados como supuesto.
- No se dirá que el índice reemplaza al seguro real: el seguro real cubre más riesgos (precio, exceso de lluvia) y paga por finca.

## 7. Entregables (Fases 5 y 6)

`docs/requisitos_datos.md`, `docs/resultados_prueba_ciegas.md`, `docs/impacto_economico_eeuu.md` actualizado, ocho figuras `docs/figuras/pitch_ciegas_*.png`, estados nuevos y "Contrato Palmer" en `app.py`, registro en MLflow, documentos actualizados, pruebas, commit y push, y el zip de contexto.

**Opcional, solo si todo lo demás terminó:** soya en los diez estados con el mismo código congelado.

## 8. Reglas de decisión si algo falla

- Un dato que no existe o una descarga que falla se anota, se toma la decisión más razonable, se explica y se sigue.
- Un estado sin datos suficientes sale de la prueba y se anota. No se reemplaza por otro fuera de la lista sin decirlo.
- Los criterios de éxito de arriba no se modifican después de ver los resultados. Si no se cumplen, se reporta tal cual.
