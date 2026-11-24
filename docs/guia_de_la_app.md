# Cómo funciona la app del seguro paramétrico de maíz

**Proyecto:** Seguro paramétrico de sequía para el maíz de Estados Unidos, diez estados, 1991-2025.
**Materia:** Proyecto 2, Especialización en Ciencia de Datos e Inteligencia Artificial.
**Fecha de este documento:** noviembre de 2026.
**Repositorio:** github.com/victorgaleano20/seguro-parametrico-agro

Este documento explica, de principio a fin, qué es la app del proyecto, para qué sirve, qué muestra cada página, cómo se calcula cada cifra y cómo hay que leerla. Está escrito para que se entienda sin ver la pantalla: cada gráfica se describe con palabras y cada número importante aparece con su significado. Todas las cifras de ejemplo salen de las tablas del repositorio.

---

## 1. Para qué existe la app

### 1.1 El problema que estudia el proyecto

Un **seguro paramétrico**, también llamado seguro por índice, es un seguro que paga automáticamente cuando un dato público cruza un umbral. Por ejemplo: "si el calor de julio y agosto en tu condado es mucho mayor que lo normal, el seguro paga". No hace falta que un perito visite la finca ni que el agricultor demuestre su pérdida. Eso lo hace rápido y barato.

Su gran debilidad tiene nombre: **riesgo de base**. El clima no siempre coincide con lo que pasó en la cosecha. Puede haber calor y la cosecha salir bien, y entonces el seguro paga sin que haya pérdida. O puede perderse la cosecha por otra causa, y el seguro no paga. Si el seguro tiene dinero público de por medio, importa mucho que la plata llegue a quien de verdad perdió.

El proyecto se pregunta: **¿el clima del verano señala bien en qué condados se perdió la cosecha de maíz?** Para responderlo usa datos de diez estados de Estados Unidos entre 1991 y 2025. Estados Unidos sirve de laboratorio porque tiene 45 años de rendimiento de maíz por condado, clima por condado y los pagos reales del seguro agrícola. En Colombia, que es donde hace falta este tipo de seguro, el dato de cosecha municipal no permite medir la pérdida: el 23,5 % de los rendimientos de maíz aparecen repetidos de un año a otro.

### 1.2 Qué compara la app

La app pone a competir tres maneras de decidir cuándo paga el seguro. A lo largo de toda la app se les llama **disparadores**, y cada uno tiene siempre el mismo color:

1. **El modelo final (azul).** Es una regresión logística con curvas suaves, llamadas splines. Recibe trece variables del clima del verano, todas medidas frente a lo normal del condado: la lluvia de mayo a septiembre, la racha de meses secos, el déficit de lluvia de julio y agosto, la temperatura máxima de junio, julio y agosto, y el índice de sequía de Palmer de junio, julio y agosto. Devuelve una probabilidad de pérdida para cada condado y año.
2. **El índice de calor (naranja).** Es la temperatura máxima de julio más la de agosto, medidas frente a lo normal del condado. No se entrena con datos: es una regla simple que cualquiera puede calcular. Es la comparación más exigente y más justa para el modelo, porque el calor de julio y agosto resultó ser casi toda la señal.
3. **La regla de lluvia (verde).** Paga si la lluvia de junio a agosto queda en el 15 % de los veranos más secos del condado. Es el tipo de contrato más tradicional.

También aparece una cuarta referencia, **el azar (gris)**: lo que pasaría si el seguro pagara en condados escogidos al azar. Sirve para saber cuánto mejor que nada es cada disparador.

### 1.3 Qué se considera una pérdida

Un condado tiene **pérdida** en un año si su rendimiento de maíz queda en **80 % o menos de lo esperado**. Lo esperado sale de una recta de tendencia del rendimiento del condado, ajustada **solo con los años anteriores**. Se usa la tendencia porque la tecnología hace subir los rendimientos con el tiempo: lo que en 1990 era un buen rendimiento, hoy sería malo. Por ejemplo, si se esperaban 10 toneladas por hectárea y salieron 7,8, el rendimiento fue el 78 % de lo esperado y eso cuenta como pérdida.

Un detalle importante: esta etiqueta cuenta cualquier pérdida de 20 % o más, sin importar la causa. Incluye las pérdidas por exceso de agua, como las inundaciones de 1993, no solo las de sequía.

### 1.4 Para quién es la app

La app tiene dos públicos:
- **El jurado de la presentación**, que necesita entender en pocos minutos si el método funciona y cuánto cuesta el error.
- **Especialistas en ciencia de datos**, que quieren revisar el desempeño con detalle: curvas, matrices de confusión, calibración, años malos y estados difíciles.

Por eso cada página tiene arriba una lectura rápida y, más abajo o en secciones desplegables, el detalle técnico.

---

## 2. Cómo se abre y cómo está construida

### 2.1 Cómo abrirla

La app se abre en el computador, desde la carpeta del proyecto, con el comando `streamlit run app.py`. Se abre en el navegador, normalmente en la dirección `localhost:8501`. Necesita las librerías de `requirements-app.txt`: pandas, numpy, scikit-learn, plotly y streamlit.

### 2.2 Qué no hace la app

La app **no entrena ningún modelo** al abrirse. Solo lee tablas que ya se calcularon con los scripts del proyecto. Eso tiene dos ventajas: abre rápido, y las cifras que muestra son exactamente las mismas de los documentos del proyecto, sin riesgo de que el texto y la app se contradigan.

### 2.3 Las piezas

- **`app.py`** es la puerta de entrada. Configura la página y arma el menú lateral con las tres páginas.
- **`app_comun.py`** guarda todo lo que comparten las páginas: la carga de datos, los colores, los nombres de los disparadores y las funciones de cálculo (el AUC, el AUC dentro de cada año, el Heidke, la regla para que todos paguen igual de seguido, el cálculo en dólares del contrato y la lectura del veredicto).
- **La carpeta `paginas/`** tiene una archivo por página: `resumen.py`, `contrato.py` y `laboratorio.py`.

### 2.4 De dónde salen los datos

La app lee cuatro grupos de tablas de la carpeta `datos/procesados/`:

1. **`modelo_final_predicciones.csv`**, del script 53. Es la tabla central. Tiene una fila por condado y año (25.452 filas de los diez estados, de 1991 a 2025) con: si hubo pérdida, la probabilidad del modelo, el puntaje del índice de calor, el puntaje y la decisión de la regla de lluvia, el valor esperado de la cosecha en dólares, la pérdida real en dólares y el tamaño medio de las pérdidas de años anteriores. La probabilidad de cada año viene de un modelo **entrenado solo con años anteriores y solo con Iowa, Illinois e Indiana**. Por eso todas las cifras son "fuera de muestra": el modelo nunca vio el año que predice.
2. **`app_metricas.csv`, `app_diferencias.csv` y `app_auc_por_anio.csv`**, del script 54. Guardan, ya calculados, el AUC de cada disparador con sus rangos de 95 % y la distribución de las diferencias entre el modelo y las referencias en 1.000 remuestreos. Se precalculan porque tardan unos dos minutos y medio, y la app debe responder al instante.
3. **`final_resultados.csv`**, del script 50. Tiene los resultados de los diez modelos que se compararon para escoger el modelo final.
4. **`eeuu_ciegas_app.csv`**, del script 34. Tiene los nombres de los condados y su ubicación.

### 2.5 Cómo se organizan los estados y los periodos

En casi todas las páginas aparecen dos controles que conviene entender desde ya.

**El control de estados** tiene tres opciones:
- **Siete estados nuevos:** Nebraska, Minnesota, Ohio, Missouri, Kansas, South Dakota y Wisconsin. El modelo nunca se entrenó con ellos. Es la prueba principal.
- **Tres estados originales:** Iowa, Illinois e Indiana. Son los estados con que se entrena el modelo. Aquí cada año se predice solo con años anteriores, pero no es una prueba a ciegas, porque se miraron muchas veces durante el proyecto.
- **Diez estados:** los dos grupos juntos.

**El control de periodo** tiene cuatro opciones:
- **1991-2025:** todo el periodo evaluado.
- **Sin 2012:** todo menos 2012, la peor sequía del periodo. Sirve para ver si el resultado depende de un solo año extremo.
- **1991-2010:** el periodo que se usó para **escoger** el modelo entre diez opciones.
- **2011-2025:** el periodo de **confirmación**, que no se usó para escoger. Es la medida más limpia.

Este último punto es muy importante para leer la app con honestidad. Los siete estados no se usaron para entrenar el modelo, pero sus años 1991-2010 sí se usaron para escogerlo entre diez candidatos. Escoger el mejor de diez mirando un periodo hace que ese periodo se vea un poco mejor de lo que es. Por eso la cifra limpia es la de 2011-2025, y la app lo recuerda con un aviso debajo del control de estados.

### 2.6 Convenciones de la app

- Los números usan **coma decimal y punto de miles**, como en español: 0,762 o 15.838.
- Los colores siguen siempre al disparador, no a su posición: azul es el modelo, naranja el índice de calor, verde la regla de lluvia y gris el azar.
- Las gráficas son interactivas. Al pasar el mouse sobre un punto o una barra aparece su valor exacto. Se puede hacer zoom y descargar la imagen desde la esquina de cada gráfica.

---

## 3. Las medidas que usa la app, explicadas

Antes de recorrer las páginas, conviene entender las medidas. Aparecen en todas partes.

### 3.1 El AUC, o acierto al ordenar

Imagine que se toman al azar dos condado-años: uno en que hubo pérdida y otro en que no. El **AUC** es la probabilidad de que el disparador le dé más riesgo al que sí tuvo pérdida. Si el AUC es 0,5, el disparador acierta la mitad de las veces, igual que lanzar una moneda. Si es 1, acierta siempre. Un AUC de 0,76 quiere decir que acierta en 76 de cada 100 parejas.

El AUC tiene una ventaja: no depende de dónde se ponga el umbral de pago. Mide qué tan bien ordena el riesgo, de mayor a menor.

### 3.2 El AUC dentro de cada año

El AUC total tiene una trampa. Buena parte del acierto viene de saber qué **años** fueron malos: en 2012 casi todo el Cinturón del Maíz perdió, y cualquier índice de calor lo detecta. Pero para un seguro lo que importa es saber **a qué condados pagar** en un año dado.

Por eso la app también calcula el **AUC dentro de cada año**: el mismo AUC, pero comparando solo condados del mismo año. Se calcula en cada año con 10 o más pérdidas y luego se promedia, dando más peso a los años con más pérdidas. Este número dice si el disparador distingue condados, no solo años. Es más bajo que el AUC total y es el que decide el riesgo de base.

### 3.3 El rango de 95 %

Toda cifra viene acompañada de un **rango de 95 %**, que dice qué tan segura es. Se calcula así: se sortean los años con reposición, es decir, se arma una historia alternativa de 35 años en la que algunos años salen dos veces y otros ninguna; se recalcula la medida; y se repite mil veces. El rango deja fuera el 2,5 % de resultados más bajos y el 2,5 % más altos.

Se sortean **años completos** y no condados sueltos porque una sequía golpea a todos los condados a la vez: los condados del mismo año no son independientes. Sortear condados daría rangos falsamente estrechos.

Para comparar dos disparadores, la app usa los **mismos años sorteados** para los dos y mira la diferencia. Si el rango de la diferencia **no incluye el cero**, se puede decir que uno supera al otro. Si lo incluye, no se distinguen.

### 3.4 El Heidke

Es una medida de aciertos que descuenta los que se lograrían por casualidad. Si el seguro paga en el mismo número de condado-años pero escogidos al azar, también acertaría algunas pérdidas. El Heidke vale 0 si el disparador no es mejor que el azar y 1 si es perfecto. Un Heidke cercano a 0,3 ya es una señal útil.

### 3.5 El Brier

Mide qué tan buenas son las probabilidades, no solo el orden. Es el promedio del cuadrado de la diferencia entre la probabilidad y lo que pasó (1 si hubo pérdida, 0 si no). Entre más bajo, mejor. Se compara con usar siempre la tasa media de pérdida: si el modelo no la mejora, sus probabilidades no aportan.

### 3.6 Misma frecuencia de pago

Cuando la app compara disparadores en decisiones de pago o en dólares, **todos pagan en el mismo número de condado-años**. El modelo paga en los condado-años de mayor probabilidad, el índice de calor en los de más calor y la regla en los más secos, siempre la misma cantidad. Así ninguno gana solo por pagar más veces. Por omisión se usa la frecuencia de la regla de lluvia: en los diez estados, el 14,4 % de los condado-años.

---

## 4. Página 1: Resumen

### 4.1 Para qué sirve

Es la página para el jurado. Responde en una pantalla la pregunta del proyecto: ¿el clima del verano anticipa la pérdida, y es el modelo mejor que lo simple?

### 4.2 Cómo se ve, de arriba abajo

**El título** es la pregunta: "¿El clima del verano anticipa la pérdida de maíz?". Debajo, un párrafo explica qué es un seguro paramétrico y qué se compara.

**Los controles.** Dos filas de botones: el grupo de estados y el periodo. La página abre en **siete estados nuevos** y **2011-2025**, que es la medida más limpia. Debajo de los controles aparece un aviso que cambia según el grupo de estados. Con los siete estados dice que sus años 1991-2010 se usaron para escoger el modelo y que la cifra más limpia es 2011-2025.

**Los cuatro indicadores.** Cuatro números grandes: el AUC del modelo, el del índice de calor, el de la regla de lluvia y el del azar, que siempre es 0,500. Debajo de cada uno, en letra pequeña, va su rango de 95 % y su AUC dentro del año. Debajo del azar, el número de condado-años y de pérdidas del grupo y periodo elegidos.

Con la vista por omisión, siete estados y 2011-2025, se lee: modelo 0,856 (rango de 0,73 a 0,89, dentro del año 0,747); índice de calor 0,835 (rango de 0,66 a 0,89, dentro del año 0,764); regla de lluvia 0,786 (rango de 0,60 a 0,86, dentro del año 0,689); azar 0,500. Son 6.079 condado-años, 515 con pérdida.

**El veredicto.** Dos recuadros de color, uno frente a la regla de lluvia y otro frente al índice de calor. **No están escritos a mano**: la app los arma con los mil remuestreos. Si el rango de 95 % de la diferencia no incluye el cero, dice que el modelo "lo supera". Si lo incluye, dice que "no se distingue". El color también cambia: verde si supera en acierto total y dentro del año, amarillo si no se distingue en alguno de los dos, y rojo si queda por debajo. Cada recuadro dice además en qué porcentaje de los remuestreos el modelo no gana.

Con la vista por omisión:
- Frente a la regla de lluvia, el recuadro es verde: el modelo la supera por 0,069 de AUC, con rango de 0,028 a 0,147; en ningún remuestreo pierde. Dentro de cada año también la supera, por 0,058.
- Frente al índice de calor, el recuadro es amarillo: el modelo no se distingue. La diferencia es de 0,021, con rango de −0,009 a 0,086, y en 11 % de los remuestreos el modelo no gana. Dentro de cada año la diferencia es de −0,017, a favor del índice.

**La gráfica de rangos.** Dos gráficas lado a lado: a la izquierda el AUC total, a la derecha el AUC dentro de cada año. Cada una tiene cuatro filas, una por periodo (1991-2025, sin 2012, 1991-2010 y 2011-2025). En cada fila hay tres puntos de colores, uno por disparador, y cada punto tiene una línea horizontal que muestra su rango de 95 %. Una línea punteada vertical marca el 0,5, el azar. Cuando las líneas de dos colores se superponen mucho, esos dos disparadores no se pueden distinguir. Lo que se ve es que las líneas azul y naranja se tocan en casi todos los periodos, y que la verde queda más a la izquierda.

**Qué significa.** Cuatro frases que resumen la lectura: el clima sí anticipa la pérdida y mejor que la regla de lluvia; un índice simple de calor hace casi lo mismo; el riesgo de base sigue alto, porque cerca de 2 de cada 3 dólares irían a condados sin pérdida; y la etiqueta incluye pérdidas por exceso de agua. Debajo hay dos enlaces a las otras páginas y una sección desplegable, "Cómo leer estas cifras", que explica el AUC, el AUC dentro del año, los rangos y los tres disparadores.

### 4.3 Qué probar en esta página

- Cambiar el periodo a **1991-2025**: los números bajan (modelo 0,762, calor 0,710, regla 0,659) porque ese periodo incluye años más difíciles, como 1993. Aquí la ventaja del modelo sobre el calor sí excluye el cero, pero hay que recordar que ese periodo incluye los años usados para escoger el modelo.
- Cambiar a **sin 2012**: el modelo sigue por encima de la regla, así que el resultado no depende solo de la gran sequía.
- Cambiar a **tres estados originales** o **diez estados** y ver que la conclusión se mantiene.

---

## 5. Página 2: Contrato y riesgo de base

### 5.1 Para qué sirve

Pasa del acierto a la plata. La pregunta es: si el seguro paga el mismo número de veces con cada disparador, ¿cuál dirige mejor el dinero a quien perdió, y cuánto cuesta equivocarse?

### 5.2 Cómo se calculan los pagos

Todos los disparadores pagan en el mismo número de condado-años, los de mayor riesgo según su propio puntaje. El **monto** que recibe cada condado cuando el seguro paga es igual para todos los disparadores: el valor esperado de la cosecha del condado multiplicado por el tamaño medio de las pérdidas de los años anteriores. El valor esperado es el rendimiento esperado por el área cosechada por el precio nacional del maíz de esa campaña, llevado a dólares de 2025. Como el monto es igual para todos, lo único que cambia entre disparadores es **a quién** se le paga.

Cuando la frecuencia elegida es la de la regla, la regla usa su umbral pactado: lluvia de junio a agosto bajo el percentil 15 del condado. Con otra frecuencia, la regla paga en los condado-años más secos frente a lo normal.

### 5.3 Cómo se ve, de arriba abajo

**Los controles.** Tres controles en una fila:
- El grupo de estados. La página abre en **diez estados**.
- Un interruptor **"Incluir 2012"**, encendido por omisión. Apagarlo quita la peor sequía, que pesa muchísimo en los dólares: solo 2012 fue casi la mitad de la pérdida de todo el periodo.
- Un control deslizante: **"¿En qué parte de los condado-años paga el seguro?"**. Tiene las opciones 5 %, 10 %, la frecuencia de la regla, 20 %, 25 % y 30 %. Abre en la frecuencia de la regla, que en los diez estados es 14,4 %.

**De cada $100.** Cuatro números grandes que responden la pregunta central: de cada 100 dólares que pagaría el seguro, ¿cuántos llegan a condados con pérdida? Debajo, una gráfica de barras horizontales con los mismos cuatro valores, cada una de su color, en una escala de 0 a 100.

Con la vista por omisión: índice de calor $32,4; modelo $31,7; regla de lluvia $25,8; azar $8,4. El texto debajo aclara que el resto, unos $68 de cada $100 en el mejor caso, va a condados que perdieron menos del 20 %. Eso es el riesgo de base, medido en dinero.

**Todas las medidas.** Una tabla con una fila por disparador y estas columnas:
- **De cada $100:** lo mismo de arriba.
- **Pérdida cubierta:** qué parte de la pérdida real total cubren los pagos. A cada condado se le cuenta como cubierto, como máximo, lo que perdió.
- **Pérdidas sin pago:** de los condado-años con pérdida, qué parte no recibió pago.
- **Pagos sin pérdida:** de los pagos, qué parte fue a condado-años sin pérdida.
- **Heidke:** aciertos por encima del azar.
- **Prima pura:** el pago promedio por año, en millones de dólares. Es lo mínimo que tendría que cobrar el seguro para no perder plata, sin contar costos ni ganancia.
- **Peor año:** lo que se pagaría en el peor año dividido por la prima pura. Mide cuánto capital necesitaría la aseguradora.

Con la vista por omisión:
- **Modelo:** $31,7 de cada $100; cubre el 60,5 % de la pérdida; deja sin pago el 47,3 % de las pérdidas; el 64,8 % de sus pagos va a condados sin pérdida; Heidke 0,347; prima pura de unos 2.984 millones de dólares al año; el peor año pagaría 11,2 veces la prima.
- **Índice de calor:** $32,4; cubre el 56,2 %; deja sin pago el 51,7 %; el 67,8 % de sus pagos va a condados sin pérdida; Heidke 0,307; prima pura de unos 2.707 millones; peor año 12,9 veces la prima.
- **Regla de lluvia:** $25,8; cubre el 49,4 %; deja sin pago el 58,2 %; el 72,1 % de sus pagos va a condados sin pérdida; Heidke 0,248; prima pura de unos 2.981 millones; peor año 10,1 veces la prima.

Una nota debajo de la tabla dice que los tres pagan en 3.659 condado-años y explica cada columna.

**Año por año.** Un selector de tres botones para escoger el disparador (abre en el modelo) y una gráfica de barras con los años de 1991 a 2025 en el eje horizontal y millones de dólares de 2025 en el vertical. Cada año tiene una barra apilada: la parte de color es lo que se pagó a condados con pérdida, y la parte gris clara, lo que se pagó a condados sin pérdida. Encima, un rombo oscuro marca la pérdida real de ese año. Así se ve de un vistazo cuándo el seguro pagó bien, cuándo pagó de más y cuándo la pérdida quedó sin cubrir. La barra más alta, por mucho, es 2012: el seguro pagaría más de 33.000 millones de dólares, frente a una pérdida real de unos 22.000 millones, y buena parte de lo pagado iría a condados sin pérdida.

**La tabla de aciertos.** Debajo de la gráfica, una pequeña matriz de dos por dos del disparador elegido, con sus conteos: cuántas veces pagó y hubo pérdida, cuántas pagó sin pérdida, cuántas hubo pérdida y no pagó, y cuántas no hubo ni pérdida ni pago. Al lado, los mismos números en frases. Para el modelo en los diez estados: pagó y hubo pérdida 1.287 veces; pagó sin pérdida 2.372 veces, el 65 % de los pagos; hubo pérdida y no pagó 1.153 veces, el 47 % de las pérdidas; y en 20.640 condado-años no hubo ni pérdida ni pago.

**Cómo se calcula y qué no dice.** Una sección desplegable explica la regla de igual frecuencia, el cálculo del monto, que el modelo se entrena solo con años anteriores, que **no se compara con el seguro real** de la agencia de riesgo agrícola de Estados Unidos (la RMA), porque ese seguro paga por finca y por otras causas como la caída del precio, y los supuestos: área asegurada igual al área cosechada y precio nacional.

### 5.4 La lectura económica

Con la vista por omisión, el seguro pagaría en 35 años unos 104.000 millones de dólares con el modelo, 95.000 millones con el índice de calor y 104.000 millones con la regla, frente a una pérdida real de 46.000 millones. Paga más del doble de la pérdida porque paga en el 14,4 % de los condado-años y solo cerca del 10 % tiene pérdida. Dicho de otro modo, **por cada dólar de pérdida que cubre, el seguro paga unos 3,7 dólares con el modelo, 3,6 con el índice de calor y 4,6 con la regla**. El modelo cubre un poco más de pérdida, pero el índice de calor lo logra un poco más barato. En dólares, el modelo no supera al índice de calor; los dos superan claramente a la regla.

### 5.5 Qué probar en esta página

- **Apagar 2012:** de cada $100, el modelo baja a $18,8, el calor a $17,5 y la regla a $12,7. Gran parte del buen desempeño depende de un año extremo.
- **Bajar la frecuencia al 5 %:** el seguro paga menos veces, solo en los condados de más riesgo. De cada $100 llegan a quien perdió $48,8 con el modelo, $55,9 con el índice de calor y $40,2 con la regla, pero la pérdida cubierta baja a 43,9 %, 41,6 % y 33,0 %. Pagando poco, el índice de calor dirige la plata mejor que el modelo.
- **Subir la frecuencia al 30 %:** la pérdida cubierta sube a 69,2 % con el modelo, 66,0 % con el calor y 62,0 % con la regla, pero de cada $100 solo llegan unos $19 a quien perdió. Es el dilema de todo seguro por índice: pagar menos veces es más certero pero deja más pérdidas solas; pagar más veces cubre más, pero reparte mucho dinero a quien no perdió.
- **Cambiar a siete estados nuevos:** modelo $24,5, calor $26,5 y regla $20,0. En los estados que no se usaron para entrenar, la plata llega peor.

---

## 6. Página 3: Laboratorio de desempeño

### 6.1 Para qué sirve

Es la página para especialistas. Cada cifra se **recalcula en vivo** con los filtros, salvo la pestaña que usa los mil remuestreos precalculados. Sirve para responder preguntas técnicas del jurado sin salir de la app.

### 6.2 Los controles generales

Arriba de todo hay tres controles que afectan a todas las pestañas:
- **El grupo de estados**, que abre en siete estados nuevos.
- **El periodo**, que abre en 1991-2025.
- **Filtrar estados**: una lista con los estados del grupo elegido, todos marcados al inicio. Se pueden quitar estados para ver, por ejemplo, solo Minnesota.

Debajo, una línea recuerda el aviso del grupo y dice cuántos condado-años y pérdidas quedan. Con la vista por omisión: 15.838 condado-años, 1.622 con pérdida, un 10,2 %. Si los filtros dejan un grupo sin pérdidas o sin años normales, la página avisa que no se puede medir.

El laboratorio tiene siete pestañas.

### 6.3 Pestaña 1: Curvas ROC y de precisión

Dos gráficas lado a lado.

**La curva ROC**, a la izquierda, muestra qué pasa al mover el umbral de pago desde "no pagar nunca" hasta "pagar siempre". El eje horizontal es la tasa de falsos positivos: qué parte de los condado-años sin pérdida recibe pago. El eje vertical es la tasa de verdaderos positivos: qué parte de las pérdidas recibe pago. Una línea punteada en diagonal representa el azar. Entre más se curve una línea hacia la esquina de arriba a la izquierda, mejor. El área bajo cada curva es su AUC, que aparece en la leyenda: con la vista por omisión, modelo 0,762, índice de calor 0,710 y regla 0,659.

**La curva de precisión y exhaustividad**, a la derecha, es la más exigente cuando las pérdidas son poco frecuentes. El eje horizontal es la exhaustividad: qué parte de las pérdidas se detecta. El eje vertical es la precisión: qué parte de los pagos cae en condado-años con pérdida. Aquí la referencia del azar no es 0,5 sino la tasa de pérdida, unos 10 %, marcada con una línea punteada horizontal. La leyenda muestra la precisión promedio de cada disparador: modelo 0,334, índice de calor 0,333 y regla 0,271. Las curvas del modelo y del calor casi se montan una sobre otra.

### 6.4 Pestaña 2: Matrices de confusión

Muestra tres matrices de dos por dos lado a lado: modelo, índice de calor y regla, cada una en su color. Las filas son lo que pasó (hubo pérdida o no) y las columnas lo que decidió el seguro (pagó o no). Cada casilla muestra el número de condado-años y el porcentaje sobre su fila. Por ejemplo, en la fila "Hubo pérdida", el porcentaje de la casilla "Paga" dice qué parte de las pérdidas recibió pago. El color de cada casilla es más intenso entre mayor es ese porcentaje.

Las tres matrices pagan con **la misma frecuencia**, que se puede cambiar con un control deslizante igual al de la página del contrato. Abre en la frecuencia de la regla del grupo elegido: en los siete estados, 15,3 %.

Con la vista por omisión:
- **Modelo:** de 1.622 pérdidas, pagó en 793, el 49 %, y no pagó en 829. De los condado-años sin pérdida, pagó en 1.623, el 11 %, y no pagó en 12.593.
- **Índice de calor:** pagó en 746 pérdidas, el 46 %, y en 1.670 condado-años sin pérdida.
- **Regla de lluvia:** pagó en 634 pérdidas, el 39 %, y en 1.782 condado-años sin pérdida.

Debajo, una tabla con cinco medidas por disparador:
- **Precisión:** qué parte de los pagos tuvo pérdida. Modelo 0,328, calor 0,309, regla 0,262.
- **Exhaustividad:** qué parte de las pérdidas tuvo pago. Modelo 0,489, calor 0,460, regla 0,391.
- **F1:** un promedio de las dos anteriores. Modelo 0,393, calor 0,369, regla 0,314.
- **Especificidad:** qué parte de los condado-años sin pérdida quedó sin pago. Los tres cerca de 0,88.
- **Heidke:** modelo 0,308, calor 0,281, regla 0,218.

La nota final recuerda que, pagando al azar con esa frecuencia, se acertarían unas 247 pérdidas y la precisión sería igual a la tasa de pérdida, 10,2 %. Así, el modelo acierta más de tres veces lo que acertaría el azar, pero aun así la mitad de las pérdidas se queda sin pago y dos de cada tres pagos van a condados sin pérdida.

### 6.5 Pestaña 3: Año por año

Una gráfica de dos pisos que comparten el eje de los años.

**El piso de arriba** muestra el AUC dentro de cada año para los tres disparadores, con líneas y puntos de sus colores. Solo aparecen los años con 10 o más pérdidas; los demás quedan en blanco y las líneas se cortan, para no unir años que no cuentan. Una línea punteada marca el 0,5. Se ve que ningún disparador gana siempre: hay años en que el modelo baja de 0,5 y años en que el índice de calor o la regla quedan arriba.

**El piso de abajo** muestra, con barras grises, cuántas pérdidas hubo cada año. Se ve de inmediato que unos pocos años concentran casi todo: 1993, 2012, 2002, 1991 y 1995.

Debajo, una tabla resume por disparador el AUC dentro del año ponderado, en cuántos años gana a los otros dos y en cuántos queda bajo 0,6. Con la vista por omisión: el modelo tiene 0,700, gana en 15 años y queda bajo 0,6 en 4; el índice de calor tiene 0,679, gana en 8 y queda bajo 0,6 en 9; la regla tiene 0,650, gana en 4 y queda bajo 0,6 en 8.

La nota final dice que los cinco años con más pérdidas reúnen el 50 % de las pérdidas, y que por eso **la muestra efectiva es pequeña**: aunque hay miles de condado-años, la información útil viene de pocos años malos.

### 6.6 Pestaña 4: Calibración

Responde si las probabilidades del modelo se pueden leer como probabilidades. Por ejemplo: cuando dice 30 %, ¿la pérdida ocurre más o menos 3 de cada 10 veces?

**La gráfica** ordena los condado-años por probabilidad y los parte en diez grupos del mismo tamaño, llamados décimos. Para cada décimo dibuja un punto: en el eje horizontal, la probabilidad promedio que dijo el modelo; en el vertical, la parte que de verdad tuvo pérdida. Una diagonal punteada marca la calibración perfecta. Si los puntos caen sobre la diagonal, las probabilidades son exactas.

**A la derecha**, dos indicadores: el Brier del modelo y el Brier de usar siempre la tasa media, con la diferencia entre los dos. Con la vista por omisión, el modelo tiene 0,0864 y la tasa media 0,0919: el modelo es mejor. Debajo, una frase dice qué pasa en el décimo de más riesgo: el modelo dice 60 % y la pérdida ocurrió en el 38 %. Es decir, el modelo exagera el riesgo alto.

La nota explica dos cosas. Primero, que la tasa media se calcula con los mismos datos que se evalúan, lo que la favorece. Segundo, que el modelo va **sin calibrar**: el proyecto probó una calibración con los tres años más recientes y empeoraba el Brier, porque cuando esos tres años casi no tienen pérdidas la curva de ajuste queda plana. Por eso la probabilidad del modelo se usa sobre todo para ordenar el riesgo.

**Algo para probar:** dejar solo Minnesota en el filtro de estados. El Brier del modelo sube a 0,090 y el de la tasa media es 0,065: en Minnesota, el modelo es peor que no saber nada.

### 6.7 Pestaña 5: ¿Gana al índice de calor?

Muestra la prueba más importante del proyecto con todo su detalle. Un selector permite comparar el modelo con el índice de calor (por omisión) o con la regla de lluvia.

Hay dos histogramas lado a lado: a la izquierda la diferencia de AUC total y a la derecha la diferencia de AUC dentro del año. Cada histograma muestra cómo se reparten las mil diferencias de los remuestreos. Una línea vertical marca el cero, "sin diferencia", y una franja sombreada marca el rango de 95 %. Si casi todo el histograma queda a la derecha del cero, el modelo gana. Si el histograma se monta sobre el cero, no se distinguen.

Debajo de cada histograma, una línea dice el rango, en qué porcentaje de los remuestreos el modelo no gana, y el veredicto.

Con siete estados y 1991-2025, frente al índice de calor: en AUC total, el rango va de 0,009 a 0,106 y el veredicto es "supera"; dentro del año, el rango va de −0,022 a 0,078, el modelo no gana en 16 % de los remuestreos y el veredicto es "no se distingue". Si se cambia el periodo a 2011-2025, el rango del AUC total pasa a ir de −0,009 a 0,086, cruzando el cero: no se distinguen.

La nota recuerda que esta pestaña usa el grupo y el periodo elegidos arriba, pero con todos los estados del grupo: no aplica el filtro de estados individuales, porque los remuestreos están precalculados.

### 6.8 Pestaña 6: Por estado

Una gráfica de puntos con una fila por estado y tres puntos por fila, uno por disparador, ordenada de menor a mayor acierto del modelo. Una línea punteada marca el azar. Al pasar el mouse se ve el AUC y el número de pérdidas de cada estado.

Con los siete estados y 1991-2025, el modelo va desde Ohio, con 0,866, pasando por Kansas (0,828), Missouri (0,807), South Dakota (0,764), Nebraska (0,707) y Wisconsin (0,703), hasta Minnesota, con 0,560. La nota recuerda que Minnesota es el caso débil conocido: allí la sequía es la parte más baja de lo que paga el seguro real y el exceso de humedad la más alta. En Minnesota, más calor va con menos pérdida, al revés que en el resto.

### 6.9 Pestaña 7: Los diez modelos

Muestra la comparación con que se escogió el modelo final: cinco tipos de modelo (regresión logística, logística con splines, bosque aleatorio, boosting de gradiente y boosting monótono), cada uno con dos conjuntos de variables (solo clima mensual, o clima mensual más grados-día de calor diario). Siempre se miden en los siete estados nuevos, sin importar el grupo elegido arriba.

Un selector permite ver el periodo de selección (1991-2010), el de confirmación (2011-2025, por omisión) o todo el periodo. La gráfica pone un punto por modelo con su rango de 95 %, ordenados por AUC. El modelo elegido va en azul, el índice de calor en naranja, la regla en verde, las demás referencias en gris oscuro y los demás modelos en gris claro. Debajo, una tabla con el AUC, su rango, el AUC sin 2012, el AUC dentro del año, el Heidke y el puntaje de elección.

La lección de esta pestaña es que **el orden entre modelos cambia según el periodo**. En 1991-2010, donde se escogió, ganó la logística con splines con clima mensual. En 2011-2025, los árboles con grados-día quedan arriba: LightGBM 0,880 y bosque aleatorio 0,872, frente a 0,856 del modelo elegido. Y los rangos de todos se superponen. Por eso el proyecto no afirma que tenga el mejor modelo posible.

---

## 7. Un recorrido sugerido para la presentación

Este es un recorrido de unos cuatro minutos para mostrar la app al jurado:

1. **Resumen, siete estados, 2011-2025.** Leer los cuatro indicadores y los dos recuadros del veredicto: el modelo supera a la regla, pero no se distingue del índice de calor.
2. **Resumen, la gráfica de rangos.** Mostrar cómo las líneas azul y naranja se superponen en todos los periodos.
3. **Contrato, diez estados.** Leer los $31,7, $32,4 y $25,8 de cada $100 y el 60,5 % de pérdida cubierta. Mostrar la barra gigante de 2012 en la gráfica año por año.
4. **Contrato, apagar 2012.** Ver cómo caen las cifras: el desempeño depende de un año extremo.
5. **Laboratorio, matrices de confusión.** Mostrar que el modelo paga en la mitad de las pérdidas y que dos de cada tres pagos van a condados sin pérdida.
6. **Laboratorio, por estado.** Mostrar Minnesota al fondo.

Para las preguntas del jurado conviene tener abierto el laboratorio: responde en vivo sobre calibración, años malos, estados difíciles y la comparación de modelos.

---

## 8. Lo que la app no dice

La app está diseñada para no exagerar. Estas son las cosas que **no** afirma:

- Que el modelo sea mejor que el índice de calor. En el periodo limpio y dentro de cada año no se distinguen, y en dólares el índice queda igual o por encima.
- Que los siete estados sean una prueba del todo a ciegas. No se usaron para entrenar, pero sus años 1991-2010 se usaron para escoger el modelo.
- Que el índice dirija la plata igual o mejor que el seguro real. El seguro real paga por finca y por otras causas, como el precio, así que no se pueden medir con la misma vara.
- Que el índice sea un producto para Estados Unidos. Allá ya existe un seguro que paga por el rendimiento del condado. El proyecto mide el método.
- Que el índice funcione en cualquier zona. Funciona donde la pérdida viene del calor y la sequía, y falla donde viene del frío o del exceso de agua.
- Que el modelo funcione en Colombia. Allá no hay datos para comprobarlo.

---

## 9. Los supuestos y límites que hay que conocer

- **Área asegurada igual al área cosechada.** En sequías fuertes, los agricultores abandonan lotes y no los cosechan; eso puede esconder parte de la pérdida. No se verificó porque falta el área sembrada.
- **Precio nacional.** El precio del maíz es el promedio nacional de cada campaña, no el de cada estado.
- **Monto por condado no optimizado.** Es el valor esperado por el tamaño medio de las pérdidas previas. Un contrato real podría pagar en proporción a la intensidad del índice.
- **Pocos años malos.** Cinco años reúnen la mitad de las pérdidas. Por eso los rangos son anchos y las diferencias pequeñas no se pueden afirmar.
- **Clima de todo el verano.** El modelo usa el clima hasta septiembre: sirve para decidir pagos al final de la temporada, no para pronosticar a mitad de verano.
- **Lo normal incluye los primeros años evaluados.** Lo normal del clima se calcula con 1981-1994, que se cruza con 1991-1994. Sin esos años, el modelo da 0,829 en los siete estados y las conclusiones no cambian.

---

## 10. Cómo se mantiene la app correcta

El proyecto tiene pruebas automáticas que verifican la app cada vez que se corren con `python -m pytest tests`:
- Que el AUC del modelo, el índice de calor y la regla en la app coincida con el de la comparación final del script 50: 0,762, 0,710 y 0,659 en los siete estados.
- Que los dólares de la página del contrato coincidan con los del script 53: $31,7, $32,4, $25,8 y $8,4 en los diez estados.
- Que los tres disparadores paguen siempre el mismo número de veces, con cualquier frecuencia.
- Que el veredicto diga "supera" solo cuando el rango de la diferencia no incluye el cero.
- Que cada página cargue sin errores.

Si se recalculan las tablas, el orden es: script 53 (predicciones y dólares), script 54 (tablas de la app) y, si se quiere, script 55 (validación dejando un estado afuera). Después basta con volver a abrir la app.

---

## 11. Glosario rápido

- **Condado-año:** un condado en un año. Es la unidad de análisis: hay un solo ciclo de maíz al año.
- **Disparador:** la regla que decide cuándo paga el seguro: el modelo, el índice de calor o la regla de lluvia.
- **Riesgo de base:** pagar sin pérdida o no pagar con pérdida.
- **Fuera de muestra:** una predicción hecha con un modelo que no vio ese dato al entrenarse.
- **Validación hacia adelante:** para predecir un año, se entrena solo con los años anteriores.
- **Prima pura:** el pago promedio por año; lo mínimo que debería cobrar el seguro.
- **Splines:** curvas suaves que dejan que cada variable afecte el riesgo de forma no lineal. Por ejemplo, que el riesgo suba rápido con mucho calor, o que tanto la falta como el exceso de agua aumenten el riesgo.
- **Índice de Palmer:** un índice de sequía de la agencia del clima de Estados Unidos (NOAA) que combina lluvia, temperatura y humedad del suelo.
- **Grados-día:** el calor acumulado por encima de un umbral; por encima de 29 °C, el calor daña el maíz.
- **RMA:** la agencia de riesgo agrícola del Departamento de Agricultura de Estados Unidos, que administra el seguro de cosechas.

---

## 12. En una frase

La app muestra, con cifras que cualquiera puede revisar, que el clima del verano sí anticipa en qué condados se pierde la cosecha de maíz y mejor que una regla de lluvia; que un índice simple de calor de julio y agosto hace prácticamente lo mismo que el modelo; y que, con cualquiera de los dos, unos dos de cada tres dólares irían a condados sin pérdida, lo que muestra que la lección para Colombia no es el algoritmo sino tener datos confiables.
