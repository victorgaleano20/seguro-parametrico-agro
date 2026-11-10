# Historia del proyecto: decisiones, razones y cómo contarlo

> **Estado (2026-11-05, cierre):** el proyecto está terminado. Lo más reciente está en la **sección 8**; el resumen de una página, en `docs/resumen_final.md`.

Este documento resume por qué se tomó cada decisión del seguro de sequía para el maíz de EE. UU., no solo qué se hizo. El detalle técnico de cada sesión está en `docs/bitacora.md`. La metodología y las métricas están en `docs/metodologia.md`.

---

## 1. El encargo

- Materia: **Proyecto 2**, Especialización en Ciencia de Datos e IA. Es una competencia.
- Presentación: **10 minutos + 5 de preguntas**.
- Rúbrica:

| Criterio | Peso | Qué piden |
|---|---:|---|
| Claridad del problema | 30 % | Descripción del problema según la necesidad del usuario (20 %) e importancia o impacto en el proceso actual (10 %) |
| Alcance de la solución | 15 % | Claridad del flujo entregado (10 %) y qué la hace única (5 %) |
| Viabilidad técnica | 25 % | Tecnología adecuada para el problema (10 %) y software o herramientas adecuados (15 %) |
| Impacto y beneficios | 30 % | Beneficios clave para los usuarios (25 %) y escalabilidad (5 %) |

- El profesor pidió: problemática real y relevante, impacto claro, aplicar ciencia de datos/IA/bases de datos, trabajo en equipo.
- Nuestra condición: **datos reales y públicos**, tema actual y que no sea una idea genérica (otro compañero recibió las mismas ideas "típicas": accidentes, calidad del aire, dengue…).

## 2. Por qué un seguro paramétrico agrícola

- **Es real y hay plata pública de por medio:** en EE. UU. el Gobierno paga cerca del 57 % de la prima del seguro de cosechas de maíz en los diez estados estudiados. Importa saber cuánto de lo que paga llega a quien perdió.
- **Se puede medir con datos públicos:** rendimiento por condado (NASS), clima por condado (CHIRPS y NOAA) y lo que de verdad pagó el seguro (RMA).
- **Es poco común** como proyecto de clase y combina datos, clima y seguros.

## 3. Qué es un seguro paramétrico (explicación sencilla)

- **Seguro normal:** como el del carro. Hay un choque, viene alguien a revisar el daño y pagan según lo que encuentre. En el campo eso es carísimo: mandar a alguien a cada finca lejana.
- **Seguro paramétrico:** no revisa la finca. Mira un dato público, como la lluvia o el calor del verano. Si en los meses en que crece el cultivo el dato cruza un umbral pactado, paga automáticamente.
- **¿Por qué paga si llueve poco?** Porque las plantas necesitan agua. Si llueve muy poco, la cosecha se pierde. La lluvia es un atajo para adivinar la pérdida sin ir a la finca.
- **Analogía que funciona:** la mamá que pone la mano en la frente. No necesita un médico para saber que uno tiene fiebre… pero a veces se equivoca.
- **Ese error tiene nombre: riesgo de base.** Puede llover "normal" y perderse la cosecha (no paga), o llover poco y la cosecha salir bien (paga sin pérdida). **Medir ese error es la pregunta del proyecto.**

## Reglas de trabajo del equipo

- Escribir el plan **antes** de correr y no agregar variantes después.
- Comparar siempre contra el azar (Heidke y valor p barajando años completos) y contra una regla simple de lluvia.
- Python simple, comentarios y mensajes en español, sin emojis.
- No inventar datos. Si algo no se encuentra, se dice.
- Cada sesión se registra en `docs/bitacora.md`.

## 4. El modelo de sequía para el maíz de Estados Unidos (4 de noviembre de 2026)

**Por qué EE. UU.:** hay rendimiento de maíz por condado durante 45 años, de una sola fuente (NASS); siniestros reales del seguro de cosechas por condado, cultivo y causa (RMA), y clima por condado (CHIRPS y NOAA). Con eso se puede comprobar un índice contra lo que de verdad pagó el seguro. El objetivo es un seguro de sequía útil allá, con modelo, semáforo, dólares y simulador.

**Lo que faltaba en esta etapa:**
- **Solo 3 estados (Iowa, Illinois e Indiana):** todavía no había clave de NASS, y el archivo masivo pesa 1,05 GB. Se resolvió en la prueba a ciegas (sección 5).
- **No había dato de riego:** los censos de NASS respondieron 404. También se resolvió con la clave de NASS.
- **No hay soya,** por la misma falta de dato.

**Resultados clave:**

| Cifra | Valor |
|---|---|
| Capacidad de distinguir año por año, 1991–2025 (0,5 = azar) | Modelo 0,82; regla 0,69; solo ubicación 0,56 |
| Sin 1988 ni 2012 | Modelo 0,70; regla 0,60 |
| Lo que más pesa | Calor de julio y agosto y lluvia de julio |
| Semáforo en 2019–2025 | No se sostiene: los verdes no tuvieron pérdidas |
| Pérdida real 1988–2025, dólares de 2025 | $35.400 millones (2012: $15.130 millones) |
| De cada $100 que pagaría el índice, a quien perdió (1991–2025) | Modelo $43; regla $39; azar $12 |
| Pérdida real cubierta por el modelo | 45 % |

**Lo que NO debemos decir:**
- **No** decir que el modelo "resuelve" el riesgo de base: más de la mitad de lo que pagaría llega a condados sin pérdida.
- **No** presentar el semáforo como herramienta: no se pudo comprobar.
- **No** decir que el modelo "predice la cosecha": se evalúa con el clima de todo el verano, a fines de septiembre, cuando ya pasó la floración.
- **No** decir que la prueba es a ciegas: el control de EE. UU. ya se había mirado. Por eso todas las decisiones se tomaron con años hasta 2018 y la medida principal es año por año.
- **No** decir que el seguro real de EE. UU. paga mal: cubre más causas y paga por finca.
- **No** presentar la prima como cotización: el recargo es un supuesto y el área es la cosechada.

**Frase para la presentación:** *"En el maíz de Estados Unidos, el calor y la falta de agua de julio y agosto anticipan la pérdida mucho mejor que una regla de lluvia o que saber dónde queda el condado. Un seguro con ese modelo haría llegar $43 de cada $100 a quien perdió, frente a $12 pagando al azar. Pero todavía más de la mitad de la plata va a quien no perdió: el riesgo de base baja, no desaparece."*

## 5. La prueba a ciegas con siete estados nuevos (5 de noviembre de 2026)

**Por qué:** el control de EE. UU. ya se había mirado, y en 2019-2025 hubo 14 pérdidas. Se aplicó todo, congelado, a siete estados que nunca se habían visto. Plan: `docs/plan_prueba_ciegas.md`; resultados: `docs/resultados_prueba_ciegas.md`.

**Qué se puede decir:**
- *"El modelo, entrenado solo con Iowa, Illinois e Indiana, distinguió las pérdidas en siete estados que nunca vio mejor que la regla de lluvia: 0,74 frente a 0,66, con el criterio fijado de antemano cumplido."* Y se mantiene sin 2012 y sin los condados con mucho riego.
- *"Un contrato simple con el índice de Palmer es tan bueno como la regla de lluvia, pero queda a 0,08 del modelo."*
- En los diez estados, de cada $100 que paga un índice con el modelo, $34 llegan a condados que perdieron (pagando al azar, $10). **Corrección del 2026-11-08:** antes se decía "igual que con el seguro real"; esa comparación no es válida (sección 7).

**Qué NO se puede decir:**
- **No** decir que el semáforo funciona: falló dos veces. La segunda, con pérdidas, los verdes salieron mejor en la estimación pero con un margen de error que incluye el cero.
- **No** decir que el modelo funciona en todos los estados: en Minnesota no distingue mejor que el azar y en Wisconsin pierde contra la regla.
- **No** decir que sus probabilidades están calibradas en estados nuevos: el Brier es peor que la tasa media, salvo recalibrando con datos locales.
- **No** decir que el índice reemplaza al seguro real: cubre más riesgos (precio, exceso de lluvia) y paga por finca. El costo de operar el índice es un supuesto.
- **No** decir que el contrato con Palmer es seguro: con suma asegurada de 100 % habría pagado en 2012 el triple de la pérdida real.
- **No** extender nada de esto a otros países o cultivos: no se probó.

**Frase para la presentación:** *"Probamos el modelo en siete estados que nunca había visto. Distinguió las pérdidas mejor que una regla de lluvia, pero no en todos los estados, y sus probabilidades no se pueden usar sin recalibrar. El semáforo no se sostuvo, y un contrato simple con el índice de Palmer queda cerca de la regla, no del modelo."*

## 6. El cierre del proyecto (5 de noviembre de 2026)

**Por qué:** la prueba a ciegas dejó cuatro preguntas abiertas. Se resolvieron con un plan congelado (`docs/plan_cierre.md`) y se dejó el proyecto empaquetado: cuaderno final, resumen de una página y simulador listo para publicar.

**Resultados** (detalle en `docs/resultados_cierre.md`):
- **El modelo aprende sobre todo clima:** sin latitud, longitud ni estado, 0,734 frente a 0,739.
- **Hacen falta unos 15 años locales** para que las probabilidades de un estado nuevo superen a la tasa media en al menos 5 de 7 estados.
- **El contrato Palmer con topes no es vendible:** el tope arregla 2012, pero paga más de 1,5 veces la pérdida real en 18 a 23 de 35 años.
- **Minnesota:** la sequía pesa menos entre las causas de sus siniestros (26 %, el más bajo de los diez estados) y más el exceso de humedad (41 %). Coincidencia, no causa demostrada.
- **Ningún semáforo se sostiene:** ni el de calidad y sensibilidad ni el de causa.

**Lo que NO debemos decir:**
- **No** decir que el contrato Palmer con topes se puede vender tal cual.
- **No** decir que algún semáforo funciona.
- **No** decir que las causas explican la falla del modelo en Minnesota.
- **No** decir que "15 años" es una cifra exacta: con 10 años solo 3 de 7 estados mejoran, y Ohio y Minnesota no mejoran con ninguno.
- **No** decir que el modelo sin ubicación es igual de bueno en todo: el Heidke baja de 0,318 a 0,284.

**Frase para la presentación:** *"El modelo aprende clima, no geografía, así que lo que aprende en tres estados se traslada a otros. Pero para confiar en sus probabilidades en un estado nuevo hacen falta unos 15 años de historia local, el contrato simple con topes todavía no se puede vender, y el semáforo no se sostiene."*

## 7. La auditoría y el relato final (8 de noviembre de 2026)

**Por qué:** se pidió revisar el proyecto con sinceridad y buscar sus puntos débiles. Detalle en `docs/bitacora.md` y en la sección 11 del cuaderno final.

**Lo que se encontró:**
- **La comparación con el seguro real no es válida.** El "$34 de cada $100" del seguro real midió sus pagos con la pérdida del condado, pero el seguro real paga por finca y por otras causas (precio, exceso de lluvia). Se retiró la frase "igual que el seguro real".
- **En EE. UU. ya existe un seguro que paga por el rendimiento del condado** (seguro por rendimiento del área de la RMA). Un índice de clima allá solo agrega rapidez. Su valor está en medir el método y en lo que le falta a Colombia.
- **Buena parte del acierto es saber qué años fueron malos:** el promedio del año solo da 0,723 frente a 0,739 del modelo. Dentro de cada año, 0,708 frente a 0,650 de la regla.
- **LightGBM no es claramente el mejor:** los tres modelos quedaron muy cerca.
- **Falta lo que recomienda la literatura:** horas de calor por encima de 29 °C y vegetación o humedad del suelo desde satélite.

**Decisión:** se recupera Colombia como el lugar donde el método hace falta (`docs/requisitos_datos.md`), con EE. UU. como laboratorio.

**Lo que NO debemos decir:**
- **No** decir que el índice dirige la plata igual o mejor que el seguro real.
- **No** presentar el índice de clima como un seguro nuevo para EE. UU.
- **No** decir que LightGBM es el mejor modelo posible.

**Frase para la presentación:** *"En Colombia no pudimos saber si un seguro por índice protege, porque el dato de cosecha no es confiable. Por eso medimos el método donde sí se puede: el maíz de EE. UU. Un modelo de clima, probado a ciegas en siete estados, ordena el riesgo mejor que una regla de lluvia, pero de cada $100 que pagaría, $66 irían a condados sin pérdida, y sin unos 15 años de historia local no se le puede poner precio. Para Colombia, el primer paso no es un modelo: es un dato de cosecha confiable y pagos públicos."*

## 8. EDA, cinco modelos y el modelo final (8 de noviembre de 2026)

**Por qué:** la auditoría técnica mostró que un índice simple de calor casi igualaba al LightGBM, que no estaba demostrado que LightGBM fuera el mejor y que el modelo del tamaño de la pérdida casi no aportaba. Se pidió un trabajo de nivel de especialización: EDA completo y comparación rigurosa de modelos.

**Qué se hizo** (detalle en `docs/bitacora.md`, partes cuarta a décima):
- Se descargaron los datos de los diez estados y la **temperatura diaria por condado** (NOAA nClimGrid-Daily) para calcular grados-día de calor. En la primera descarga se filtraron mal los estados (NOAA no usa el código FIPS); se detectó antes de usar los datos y se corrigió.
- **EDA** (`notebooks/eda.ipynb`): datos limpios; las pérdidas se concentran en pocos años y regiones (el condado explica el 3 % de la variación); el clima medido frente a lo normal se traslada entre estados y la ubicación no.
- **Cinco modelos × dos conjuntos de variables**, entrenados con 3 estados y probados a ciegas en 7, con el criterio fijado antes de correr.
- La calibración con 3 años **empeoraba** las probabilidades; el modelo final se usa sin calibrar.

**Resultado:** el modelo final es una **logística con curvas suaves sobre el clima frente a lo normal** (AUC 0,762 a ciegas, frente a 0,659 de la regla y 0,710 del índice de calor). En dólares, el modelo ($31,7 de cada $100) y el índice de calor ($32,4) dirigen la plata casi igual.

**Lo que NO debemos decir:**
- **No** decir que el aprendizaje automático es mucho mejor que un índice simple: la ventaja es pequeña y en dólares desaparece.
- **No** decir que los grados-día "mejoran el modelo" como resultado firme: frente a lo normal ayudan, pero es exploratorio.
- **No** seguir diciendo "$34 de cada $100": esa cifra era del LightGBM anterior; ahora son unos $32.
- **No** decir que las probabilidades "no sirven sin 15 años locales" sin el matiz: sin la calibración de 3 años, ya superan a la tasa media.

## 9. Auditoría externa, app nueva y validación por estado (9 de noviembre de 2026)

**Por qué:** una auditoría externa revisó cifras y afirmaciones contra las tablas. Detalle en `docs/bitacora.md` (2026-11-09, tres partes).

**Qué cambió en lo que se puede decir:**
- **"A ciegas" tiene un matiz:** los siete estados no se usaron para entrenar, pero sus años 1991-2010 sí se usaron para **escoger** el modelo. La medida limpia es 2011-2025.
- **Frente al índice de calor, el modelo no se distingue:** en 2011-2025, +0,021 de AUC con rango de 95 % de −0,009 a +0,086, y dentro de cada año −0,017. En 1991-2025 (+0,009 a +0,106) y sin los años de lo normal (1995-2025: +0,0005 a +0,047) la ventaja total excluye el cero, pero esos periodos incluyen los años usados para escoger el modelo. Lo que se sostiene: **ventaja pequeña en saber qué años son malos, ninguna en qué condados**.
- **Entrenar con 9 estados no mejora al modelo** (validación dejando un estado afuera, `55`): en 2011-2025 da lo mismo que entrenar con 3 (0,858 frente a 0,856), y sigue empatado con el índice de calor.
- **El método no es universal:** fuera de su estado funciona en Illinois (0,91), Indiana, Ohio, Kansas, South Dakota y Missouri; es débil en Nebraska, Wisconsin e Iowa (0,57), y falla en Minnesota (0,40), donde más calor va con **menos** pérdida (allí pesan el frío y el exceso de humedad).
- **No copia al índice de calor:** coinciden en 68 % de los pagos; donde no coinciden, lo que paga solo el modelo tiene 22 % de pérdidas y lo que paga solo el calor, 13 %. Esa ganancia es real pero pequeña frente al ruido de pocos años malos.

**Lo que NO debemos decir:**
- **No** decir que el modelo es "mejor" que el índice de calor, ni siquiera "algo mejor": no se distingue en el periodo limpio.
- **No** decir "estados que nunca vio" sin el matiz de que se usaron para escoger el modelo.
- **No** decir que un índice de calor sirve en cualquier zona: depende de la causa de la pérdida.

**Frase para la presentación:** *"Probamos cinco modelos con un plan fijado antes de correr, entrenando en tres estados y midiendo en siete que no se usaron para entrenar. Ganó el más sencillo: curvas suaves sobre el calor y la falta de agua del verano, medidos frente a lo normal de cada condado. Ordena el riesgo mucho mejor que una regla de lluvia, pero un índice simple de calor de julio y agosto hace prácticamente lo mismo, y con cualquiera de los dos unos $2 de cada $3 irían a condados sin pérdida. Además, el índice funciona donde la pérdida viene del calor y falla donde viene del frío o del exceso de agua. La lección para Colombia no es el algoritmo: es tener datos de cosecha y de pagos confiables, y diseñar el índice según la causa de pérdida de cada zona."*
