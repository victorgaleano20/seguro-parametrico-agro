# Bitácora del proyecto

Qué se hizo en cada sesión del seguro de sequía para el maíz de EE. UU., con su plan (escrito antes de correr) y sus resultados.
Las sesiones anteriores al 2026-11-04 (Colombia, México y café) se retiraron del proyecto; siguen en el historial de git.

## 2026-11-04: nuevo objetivo, seguro paramétrico de sequía para el maíz de EE. UU. (plan, escrito antes de correr)

**Pedido:** el proyecto pasa a ser un seguro paramétrico de sequía para el maíz de Estados Unidos. Se entregan un modelo mejorado de probabilidad y tamaño de la pérdida por condado, un semáforo de condados, el impacto en dólares y un simulador. Colombia y el café quedan como antecedente: no se borra nada. Todo se trabaja de corrido, sin esperar aprobación. Scripts nuevos `27` a `32`, sin emojis.

**Antes de empezar:** `git pull` trajo la fusión del café (`3ea0d2b`), sin conflictos ni cambios locales.

**Honestidad (fijada de antemano):** el control de EE. UU. ya se miró, así que esto no es una prueba a ciegas. Variables, hiperparámetros, umbrales y cortes del semáforo se deciden solo con años de entrenamiento y validación. No se usan meses posteriores a septiembre del año de cosecha ni el rendimiento de años anteriores.

### Fase 0: inventario y descargas

**Ya está en `datos/crudos/`:**
- NASS por condado de Iowa, Illinois e Indiana: producción, área cosechada y rendimiento, 1981–2025.
- RMA de todo el país, 1989–2025: Cause of Loss (`colsom`) y Summary of Business (`sobcov`).
- CHIRPS mensual del recuadro de los 3 estados, límites de condados de todo el país (Census 2023) y ONI.

**Lo que no se puede bajar, y la decisión:**
- **No hay `NASS_API_KEY` en este equipo,** y la API responde "unauthorized" sin clave.
- El archivo masivo de cultivos de Quick Stats (`qs.crops_20260926.txt.gz`) **pesa 1,05 GB**, más que el límite de 500 MB, y no hay una versión por estado.
- **Decisión:** el análisis se queda en **Iowa, Illinois e Indiana**. No se extiende al cinturón maicero. Si alguien define la clave, el mismo flujo se puede ampliar.
- **Tampoco se tienen:** área sembrada, precio por estado y soya por condado. Ver las fases 3 y 4.

**Se descarga** (unos 270 MB en total) y se anota en `registro_descargas.csv` con `27_adquisicion_eeuu.py`:

| Dato | Fuente | Uso |
|---|---|---|
| Temperatura máxima mensual por condado (`climdiv-tmaxcy`, 41 MB) | NOAA NCEI, nClimDiv | Temperatura de junio a agosto |
| Índice de sequía de Palmer mensual por condado (`climdiv-pdsicy`, 41 MB) | NOAA NCEI, nClimDiv | Sequía de junio a agosto |
| Censos agropecuarios 2002 y 2017 (`qs.census2002`, 47 MB; `qs.census2017`, 132 MB) | NASS, archivos masivos sin clave | Fracción de maíz para grano bajo riego. Se guardan solo las filas de maíz de los 3 estados |
| Precio promedio recibido por los agricultores, maíz, por campaña | USDA ERS, Feed Grains Yearbook (dato de NASS) | Pérdida en dólares. **Es nacional:** el precio por estado viene de NASS y no se puede bajar |
| Índice de precios al consumidor urbano (CPI-U, serie CUUR0000SA0) | BLS, API pública v1. Si falla, FRED (copia de la misma serie) y se dice | Pasar todo a dólares de 2025 |

### Fase 1: modelo mejorado (`28_base_eeuu.py` y `29_modelos_eeuu.py`)

**Unidad:**
- Condado × año, 1981–2025, con los filtros de calidad que ya existen: repetidos, salto de área y condados con al menos 15 años válidos.
- Pérdida = rendimiento ≤ 80 % del esperado por la tendencia lineal del condado.

**Partición fija:** 45 años con `particion()` de `19`:
- Entrenamiento 1981–2011 (31 años), validación 2012–2018 (7) y prueba 2019–2025 (7).
- Corte = 2018.
- La tendencia de la partición fija se ajusta solo con años ≤ 2018, como mínimo 10 años, y se prolonga a 2019–2025.

**Validación hacia adelante (medida principal):**
- Cada año *t* de 1991 a 2025 (35 años) se predice con modelos entrenados solo con años anteriores.
- La tendencia y la pérdida salen de años anteriores a *t*: como mínimo 8 años válidos, igual que en `24`.
- Los hiperparámetros y la calibración también: se ajustan con los 3 años previos a *t*, usando un modelo entrenado con los años anteriores a esos 3.

**Variables, todas conocidas al final de septiembre:**
- **Lluvia:** CHIRPS de mayo a septiembre, cada mes como % de lo normal del condado. Lo normal se calcula con 1981–1994, antes del primer año que se predice. El piso para lo normal es 10 mm y el tope, 300 %.
- **Temperatura:** máxima de junio, julio y agosto, como diferencia en °C frente a lo normal de 1981–1994.
- **Sequía de Palmer:** junio, julio y agosto.
- **Meses secos consecutivos:** la racha más larga de mayo a septiembre con lluvia < 75 % de lo normal. El 75 % se fija aquí.
- **Déficit de floración:** en julio y agosto, max(0, 100 − lluvia de julio y agosto en % de lo normal).
- **Ubicación:** latitud, longitud y estado.
- **Riego:** fracción del área de maíz para grano cosechada con riego.
  - Es el promedio de los censos disponibles en los archivos de 2002 y 2017 (1997, 2002, 2012 y 2017), todos anteriores al corte.
  - Es un atributo fijo del condado. En los primeros años de la validación hacia adelante usa censos posteriores; se declara.

**Modelos, en este orden:**
1. **Regla de lluvia calibrada:** lluvia de junio a agosto bajo el percentil 15 del condado. El percentil sale de entrenamiento en la partición fija y de años anteriores a *t* en la validación hacia adelante. Que la ventana y el percentil se escogieran con 1981–2002 es una ventaja leve para 1991–2002; se declara.
2. **Solo ubicación:** LightGBM con latitud, longitud y estado.
3. **Regresión logística.**
4. **Bosque aleatorio.**
5. **LightGBM.**

Las rejillas son las de `20_modelos.py`. El mejor modelo es el de mayor AUC en la validación de la partición fija.

**Calibración:** regresión isotónica ajustada con las predicciones de los años de validación de un modelo entrenado sin esos años. Se reporta Brier crudo y calibrado, y una curva de calibración por deciles.

**Severidad:**
- Es cuánto se queda corto el rendimiento cuando hay pérdida: 1 − rendimiento relativo, con el relativo limitado a [0, 3].
- Modelo: LightGBM de regresión solo con filas con pérdida, con hiperparámetros fijos de antemano (7 hojas, hoja mínima 20, 200 árboles, tasa 0,03) y sin búsqueda.
- Se compara con la severidad media de las pérdidas de años anteriores.
- **Pérdida esperada** = probabilidad calibrada × severidad prevista. Se compara con el faltante real (Spearman y error absoluto medio) frente a tasa histórica × severidad media.

**Métricas:**
- AUC, % de pérdidas captadas, % de alertas sin pérdida, Heidke y Brier.
- **Corte del modelo:** paga con la misma frecuencia que la regla en esos mismos años.
- **Valor p:** barajando años completos, 1.000 veces.
- **Intervalos de 95 %:** remuestreo de años, 1.000 veces.
- Todo con y sin 1988 y 2012. En la validación hacia adelante, el mejor modelo se corre también sin esos dos años, en entrenamiento y en evaluación. 1988 solo aparece en entrenamiento.

**Aporte de cada grupo (LightGBM y regresión logística, validación hacia adelante):**
- Grupos: ubicación, lluvia (meses, racha y déficit), temperatura, sequía de Palmer y riego.
- Se mide el AUC de:
  - solo ubicación;
  - ubicación más cada grupo por separado;
  - todas las variables;
  - todas menos cada grupo.

**SHAP:** del mejor modelo de la partición fija, en validación y prueba. Peso por mes y por grupo, signo en meses secos frente a lluviosos, y si coincide con junio a agosto.

**MLflow:** experimento `seguro_sequia_maiz_eeuu`, como en `20`. El mejor modelo se registra como `perdida_maiz_eeuu`, con el alias `mejor_en_validacion`.

### Fase 2: semáforo de condados (`30_semaforo_eeuu.py`), solo con años ≤ 2018

1. **Dato bueno:** al menos 25 años válidos hasta 2018, a lo sumo 5 % de repetidos hasta 2018 y sin salto de área. Si falla alguna de las tres, el dato es malo.
2. **Sensibilidad al clima, con información compartida entre condados:**
   - **Índice de estrés del verano:** el promedio de tres valores estandarizados por condado con años ≤ 2018: lluvia de junio a agosto, Palmer de junio a agosto y menos la temperatura máxima de junio a agosto.
   - **Pendiente por condado:** se ajusta el rendimiento relativo (tendencia ≤ 2018) contra ese índice.
   - **Encogimiento empírico de Bayes:** la pendiente se acerca a la media del estado, con peso τ² / (τ² + se²).
   - **Sensibilidad:** la parte de la variación del rendimiento que explica la pendiente encogida (b² · var(índice) / var(relativo)). Requiere al menos 10 años.
3. **Riego:** poco si es < 10 %, alto si es ≥ 25 %. Los dos cortes se fijan aquí.
4. **Color (terciles de la sensibilidad entre los condados con al menos 10 años):**
   - **VERDE:** dato bueno, tercil alto de sensibilidad y poco riego.
   - **ROJO:** dato malo, tercil bajo de sensibilidad o riego alto.
   - **AMARILLO:** el resto, o información insuficiente.

**Prueba (años 2019–2025):**
- **Qué se compara:** AUC, Heidke y % de pérdidas captadas por color. Se usan el modelo de la partición fija y la regla.
- **Intervalos:** remuestreo de años.
- **Se sostiene** si el intervalo de 95 % de la diferencia verde − rojo en AUC del modelo queda por encima de 0 **y** la diferencia en Heidke del modelo es positiva. Si no, se reporta que no se sostiene y no se presenta como herramienta.

**Entrega:** `semaforo_condados.csv` y el mapa.

### Fase 3: impacto económico (`31_impacto_eeuu.py`), en dólares de 2025 con el CPI-U del BLS

1. **Pérdida real:** (rendimiento esperado − observado, en bu/acre) × área cosechada × precio nacional de la campaña, en los condado-años con pérdida.
   - El esperado sale de la tendencia de años anteriores (mínimo 7 años, para incluir 1988).
   - Se reporta por año, estado y fase del clima (ONI medio de junio a agosto, ≥ 0,5 o ≤ −0,5), y se destacan 1988 y 2012.
2. **Lo que pagó el sistema real (RMA, maíz 0041, todos los planes, 1989–2025):**
   - Por condado-año, de `sobcov`: indemnización, prima total, subsidio y prima del agricultor (prima menos subsidios y descuentos).
   - Indemnización por sequía, de `colsom` con la causa 11.
3. **Seguro paramétrico simulado:**
   - **Suma asegurada por acre (SUPUESTO):** 75 % y 100 % del valor esperado (rendimiento esperado × precio).
   - **Área (SUPUESTO):** se usa el área cosechada, porque el área sembrada por condado viene de NASS y no se puede bajar.
   - **Pago:** suma × severidad prevista por el modelo, cuando la regla o el modelo se activan.
   - **Corte del modelo, para que se pueda aplicar:** la probabilidad que, en los años de validación (o en los 3 años previos, en la validación hacia adelante), paga con la misma frecuencia que la regla.
   - **Periodo principal:** prueba 2019–2025. Periodo ampliado: 1991–2025.
   - **Métricas:** dólares a condado-años sin pérdida; pérdida real sin pago; % de la pérdida real cubierta (Σ mín(pago, pérdida) / Σ pérdida); de cada $100, cuántos llegan a condado-años con pérdida, frente al azar. Todo también por color del semáforo.
4. **Prima:**
   - Prima pura = pago medio por año; con recargo de 30 % (SUPUESTO).
   - **Subsidio:** el % real de la RMA para el maíz de los 3 estados, calculado de los datos de 2014–2018. También se reporta 2019–2025.
5. **Sensibilidad:** suma asegurada (75 % y 100 %), recargo (0 %, 30 % y 50 %) y subsidio (0 %, el real y 100 %).
6. **Documento:** `docs/impacto_economico_eeuu.md`, con la tabla de supuestos al inicio y la conclusión en 3 frases.

### Fase 4: soya

**No se puede hacer:** el rendimiento de soya por condado solo sale de NASS, y no hay clave ni un archivo de menos de 500 MB. Se anota y no se fuerza.

### Fase 5: entregables

- `docs/resultados_modelo_eeuu.md` y 8 figuras `pitch_eeuu_*` (`32_figuras_eeuu.py`).
- Pestañas nuevas en `app.py`.
- Documentos actualizados.
- Pruebas, revisión de claves y rutas, commit, `git pull` y push.

### Fase 0: resultado (escrito antes de entrenar)

- **Se bajó:**
  - Temperatura máxima y Palmer por condado (NOAA, 78 MB, con su guía de lectura).
  - Precios del ERS (17 MB). La campaña de septiembre a agosto lleva el año de la cosecha: 2012 es 2012/13, a $6,89 por bushel. El valor de 2025 es la cifra vigente del ERS para 2025/26 y puede cambiar.
  - CPI-U del BLS. La API v1 solo respeta el rango de años por POST; la primera corrida trajo solo los últimos meses y se repitió.
- **Octubre de 2025 no tiene CPI publicado:** el promedio de 2025 se calcula con 11 meses, y se dice.
- **Los censos de NASS no se pudieron bajar:**
  - Las direcciones de la página de NASS responden 404, incluso su Readme. No se insistió con otros métodos.
  - **Decisión:** se sigue sin riego. El grupo de riego sale del modelo, y el semáforo se aplica **sin la condición de riego**.
  - Es un cambio forzado al plan, anotado antes de correr las fases 1 y 2.
  - Se pierde la posibilidad de marcar en rojo a los condados con mucho riego. En estos tres estados la mayor parte del maíz es de secano, pero esa afirmación no se verificó con datos en este proyecto.
- **Base (`28`):** 12.544 condado-años en 293 condados, con 10,1 % de pérdidas.

| Periodo | Años | Filas | Pérdidas |
|---|---|---:|---:|
| Entrenamiento | 1981–2011 | 8.967 | 11,1 % |
| Validación | 2012–2018 | 1.894 | 13,6 % |
| Prueba | 2019–2025 | 1.683 | **0,8 %** |

**Advertencia:**
- En la prueba, con la tendencia de años ≤ 2018, hay **unas 14 pérdidas**. La partición fija y la prueba del semáforo tendrán muy poca potencia.
- No se cambia el plan por esto: se reporta así, y la validación hacia adelante sigue siendo la medida principal.
- NASS publica menos condados en los últimos años (202 en 2025).

### Fase 1: corrección durante la corrida

- **Qué se vio:** en la primera corrida completa, el modelo que solo conoce la ubicación sacó un Heidke de 0,247 hacia adelante, con AUC de 0,549.
- **La causa era un error de código:**
  - El corte "igual frecuencia que la regla" se aplicaba año por año, así que cada modelo pagaba cada año en tantos condados como la regla.
  - Con eso, cualquier modelo heredaba de la regla cuáles años fueron secos.
  - El plan decía "con la misma frecuencia que la regla en esos mismos años", es decir, en el conjunto de años evaluados.
- **Corrección:** ahora se iguala en todo el periodo evaluado. Se detuvo la corrida y se repitió completa.
- **Qué no cambia:**
  - El AUC y el Brier no dependen de este corte.
  - El corte aplicable del impacto (`pago_umbral`, fijado con los años previos) tampoco.
- **Lo que se había visto de la primera corrida:** las métricas de la partición fija y esa línea de "solo ubicación". No se cambió nada más.

- **Segunda corrección, al revisar las figuras:**
  - La validación hacia adelante se saltaba 2024 y 2025. En los 3 años previos (2021–2023) no hubo ninguna pérdida, así que no se podían escoger hiperparámetros ni calibrar.
  - Saltarse años con falsas alarmas hace ver mejor al modelo.
  - **Corrección:** si los 3 años previos no tienen pérdidas, queda la primera opción de la rejilla (fijada de antemano) y la probabilidad sin calibrar. Se repitió la corrida completa de `29` a `32`.
  - En la corrida anterior, LightGBM hacia adelante (1991–2023) dio AUC 0,816 y Heidke 0,446; la regla, 0,690 y 0,306. Se anota para que se vea el efecto de agregar 2024–2025.

### Resultados de las fases 1 a 3

Detalle: `docs/resultados_modelo_eeuu.md` y `docs/impacto_economico_eeuu.md`.

**Fase 1 (validación hacia adelante, 1991–2025, 818 pérdidas):**

| | AUC | Heidke |
|---|---:|---:|
| Regla | 0,690 | 0,304 |
| Solo ubicación | 0,559 | 0,059 |
| Regresión logística | 0,779 | 0,399 |
| Bosque aleatorio | 0,826 | 0,395 |
| **LightGBM** (mejor en validación, AUC 0,970) | **0,816** | **0,445** |

- **Valor p por años completos:** 0,001 para los modelos y 0,005 para la regla.
- **Sin 1988 ni 2012:** LightGBM 0,702 y regla 0,598.
- **Partición fija:** solo hay 14 pérdidas en la prueba 2019–2025, así que tiene muy poca potencia. LightGBM 0,777, regresión logística 0,902 y regla 0,744. El modelo no se cambió por esto.
- **Aporte a la ubicación (LightGBM):**
  - lluvia: +0,19;
  - temperatura: +0,17;
  - Palmer: +0,31;
  - todas: +0,26.
- **Más variables no siempre ayudan:** ubicación más Palmer (0,871) supera a todas juntas (0,816). Se ve después de fijar el modelo, así que no se cambia.
- **SHAP:** pesan más la temperatura máxima de julio y agosto y la lluvia de julio.
- **Severidad:** casi no se anticipa. El error baja de 0,105 a 0,099.
- **Calibración:** mejor que la tasa media (Brier 0,064 frente a 0,078), pero no en todos los tramos.
- **Veranos muy lluviosos:** tienen 16 % de pérdidas y el modelo les da 1,5 %.

**Fase 2:**
- **Colores:** 95 condados verdes, 90 amarillos y 108 rojos.
- **Iowa sale casi todo rojo:** su peor pérdida antes de 2018 fue la inundación de 1993, que borra la relación lineal con la sequía. Es una lectura posterior, y la regla no se cambió.
- **Prueba 2019–2025:** los verdes no tuvieron ninguna pérdida, así que la diferencia en AUC no se puede calcular y la de Heidke es negativa.
- **El semáforo no se sostiene,** y no se presenta como herramienta.

**Fase 3 (dólares de 2025):**
- **Pérdida real:** $35.400 millones en 1988–2025, de ellos $15.130 millones en 2012 y $8.990 millones en 1988.
- **RMA en 1989–2025:**
  - indemnizó $29.570 millones, 41,6 % de ellos por sequía;
  - la prima fue de $41.080 millones;
  - el subsidio, de $21.670 millones;
  - el subsidio real fue de 54,4 % en 2014–2018.
- **Simulación 1991–2025, suma del 100 %:**
  - el modelo paga $31.710 millones, y $43 de cada $100 llegan a quien perdió (regla $39, azar $12);
  - cubre 45 % de la pérdida real (regla 55 %);
  - de cada $100 de subsidio, $33 llegan a quien perdió (regla $30).
- **Prueba 2019–2025:** casi no hubo pérdidas, y se pagan $3 de cada $100 a quien perdió.

**Fase 4 (soya):** no se hizo. No hay dato de soya por condado sin la clave de NASS.

**Fase 5:** 8 figuras `pitch_eeuu_*` y tres pestañas nuevas en `app.py`. Se probaron con `AppTest` (disparador, umbral, estado y filtro del semáforo) y con `streamlit run`. Las pestañas anteriores quedan al final como "Antecedente".

**Entorno:** el entorno de este equipo no tenía `scikit-learn`, LightGBM, MLflow, SHAP ni `pytest`. Se instalaron de `requirements.txt` con `uv`, con las versiones fijas.

### 2026-11-05: prueba a ciegas con siete estados nuevos (plan congelado, escrito antes de descargar o mirar sus datos)

**Fecha:** 2026-11-05. **Estado:** escrito y subido a git ANTES de descargar o mirar cualquier dato de los estados nuevos (Nebraska, Minnesota, Ohio, Missouri, Kansas, South Dakota y Wisconsin). El commit "Plan congelado de la prueba a ciegas" es la prueba de ese orden.

**Qué no se ha visto:** rendimientos, pérdidas, lluvia, temperatura, Palmer, riego ni siniestros de los estados nuevos. Solo se comprobó que la clave de NASS funciona, con una consulta de conteo (sin valores).

**Qué sí se ha visto, y se declara:** Iowa, Illinois e Indiana se miraron varias veces. Por eso la prueba a ciegas usa estados que nunca se han mirado.

**Objetivo:** probar mejor lo que ya existe, sin modelos ni variables nuevas. Todo lo de abajo queda congelado. Si algo se cambia después de ver resultados, se anota como cambio y se reporta aparte, no como parte de la prueba.

### 1. Lo que queda fijo (no se toca)

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

### 2. Datos de los estados nuevos (Fase 1)

- **Estados, en orden de prioridad si algo no cabe:** Nebraska, Minnesota, Ohio, Missouri, Kansas, South Dakota, Wisconsin. Cualquier descarga de más de 500 MB no se hace: se usan menos estados y se anota.
- **NASS (API, con clave en la variable de entorno, nunca en archivos):** rendimiento, producción, área cosechada y área sembrada de maíz para grano por condado, 1981 a 2025. Área de maíz con riego por condado de los censos 1997, 2002, 2007, 2012, 2017 y 2022, para los estados nuevos y los tres originales.
- **Lluvia CHIRPS por condado:** el mismo método de `27`/`08` (recorte CHIRPS mensual de la IRI Data Library, promedio por polígono de condado con `04_lluvia_municipios.lluvia_mensual`), con un recuadro que cubra los siete estados.
- **Temperatura máxima y Palmer:** los archivos nClimDiv de NOAA que ya están (cubren todo el país).
- **RMA:** Cause of Loss y Summary of Business que ya están en `datos/crudos`; se verifica que incluyan estos estados.
- **Mismos filtros de calidad y misma definición de pérdida** de la sección 1.
- Todo se anota en `datos/crudos/registro_descargas.csv`, sin la clave.

### 3. Prueba a ciegas del modelo (Fase 2, resultado principal)

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

### 4. Dos pruebas del semáforo, con pérdidas (Fase 3A)

**Regla del color:** la de `30` (sección 1), que corrió sin dato de riego. **Variante fijada:** la misma regla, más "rojo si más de 25 % del área de maíz tiene riego" (riego con solo censos anteriores al año de los colores en la prueba 1, y censos hasta 2017 en la prueba 2). Los terciles de sensibilidad se calculan entre los condados con al menos 10 años de datos.

- **Prueba 1 (hacia adelante):** cada año t se recalculan los colores con la regla congelada usando **solo años anteriores a t**, en los diez estados juntos (terciles y encogimiento con los condados de los diez estados, por estado). Se evalúa en todos los años t en que hay al menos 25 años previos para colorear (de 2006 a 2025). Las predicciones del modelo y de la regla son las de la validación hacia adelante (tres estados originales) y las de la prueba a ciegas principal (siete nuevos).
- **Prueba 2 (geográfica):** colores de los **estados nuevos** con sus años hasta 2018 (terciles y encogimiento entre los siete estados nuevos), evaluados en 2019-2025.

**Qué se mide por color:** AUC, Heidke, % de pérdidas captadas y "de cada $100 que paga el seguro, cuántos llegan a quien perdió" (pago = suma asegurada de 100 % × valor esperado × severidad prevista, cuando el disparador se activa; mismo cálculo de `31_impacto_eeuu.py`, con el corte aplicable). Con el modelo y con la regla.

**Criterio de éxito (se evalúa con el modelo, en cada prueba):** los verdes superan a los rojos en Heidke, en % de pérdidas captadas y en "de cada $100 que llegan a quien perdió", **y** el intervalo de 95 % de la diferencia verde − rojo (remuestreando años completos, 1.000 veces) **no incluye el cero** en las tres métricas. Se reporta por separado la regla base y la variante con riego.

**Se reporta además** que la primera prueba (2026-11-04, partición fija 2019-2025) falló, y por qué: los condados verdes no tuvieron ni una pérdida en un periodo con solo 14 pérdidas, así que no había con qué comparar, y Iowa quedó casi todo rojo por la inundación de 1993.

### 5. Contrato simple con el índice de Palmer (Fase 3B)

- **Índice:** promedio del Palmer (PDSI de NOAA) de julio y agosto del condado en el año t.
- **Disparador y pago proporcional:** paga cuando ese promedio queda **por debajo del percentil 15** de los valores de los años anteriores a t de ese condado (mínimo 10 años). El pago es **0 en el percentil 15 y 100 % de la suma asegurada en el percentil 2**, en línea recta; por debajo del percentil 2 paga el 100 %. Los percentiles se calculan con la interpolación lineal de `numpy.quantile` sobre los años anteriores.
- **Misma fórmula para la regla de lluvia:** lluvia de junio a agosto, mismos percentiles 15 y 2 del condado, con años anteriores.
- **Comparación en igualdad:** Palmer, regla de lluvia y modelo con la **misma frecuencia de pago** (la del contrato Palmer en el conjunto evaluado; regla y modelo se igualan por puntaje). El pago en dólares del Palmer y de la regla es el proporcional de arriba; el del modelo es suma × severidad prevista cuando se activa.
- **Métricas, en los estados nuevos y en los originales:** AUC (puntaje del Palmer: su distancia estandarizada bajo la media de años anteriores del condado, cambiada de signo), Heidke, % de la pérdida en dólares cubierta y "de cada $100, cuántos llegan a quien perdió".
- **Interpretación fijada:** si el AUC del Palmer queda a **0,03 o menos** del AUC del modelo, se puede proponer como contrato simple. Si no, el modelo aporta algo que el contrato no captura.

### 6. Impacto económico (Fase 4)

- Se repiten los cálculos de `31_impacto_eeuu.py` para los siete estados nuevos y para los diez juntos: dólares de 2025 (CPI-U), pérdida real, indemnización de la RMA (por sequía y en total), subsidio real, y seguro simulado con modelo, regla y Palmer. Suma asegurada de 100 % (y 75 % como sensibilidad), recargo de 30 % (supuesto).
- **Costo de operar el seguro real:** se buscan en fuentes oficiales (RMA, USDA, GAO, CBO) los reembolsos a las aseguradoras por gastos de administración y operación (A&O) y el tiempo medio de pago de una indemnización, con cada fuente citada. Si no hay cifras de maíz, se usan las del programa completo y se dice.
- **De cada $100 que llegan a quien perdió, cuánto cuesta administrarlo.** Seguro real: A&O reembolsado sobre la prima de los condado-años, dividido entre las indemnizaciones que llegan a condado-años con pérdida. Índice: el costo de operar es un **SUPUESTO**; se prueban 5 %, 10 % y 20 % de la prima pura, marcados como supuesto.
- No se dirá que el índice reemplaza al seguro real: el seguro real cubre más riesgos (precio, exceso de lluvia) y paga por finca.

### 7. Entregables (Fases 5 y 6)

`docs/requisitos_datos.md`, `docs/resultados_prueba_ciegas.md`, `docs/impacto_economico_eeuu.md` actualizado, ocho figuras `docs/figuras/pitch_ciegas_*.png`, estados nuevos y "Contrato Palmer" en `app.py`, registro en MLflow, documentos actualizados, pruebas, commit y push, y el zip de contexto.

**Opcional, solo si todo lo demás terminó:** soya en los diez estados con el mismo código congelado.

### 8. Reglas de decisión si algo falla

- Un dato que no existe o una descarga que falla se anota, se toma la decisión más razonable, se explica y se sigue.
- Un estado sin datos suficientes sale de la prueba y se anota. No se reemplaza por otro fuera de la lista sin decirlo.
- Los criterios de éxito de arriba no se modifican después de ver los resultados. Si no se cumplen, se reporta tal cual.

**Antes de empezar:** git pull dijo 'Already up to date'; sin cambios sin guardar. La clave de NASS no estaba en el entorno; la usuaria la entregó en el chat y se usa solo como variable de entorno, nunca en archivos. Copia del plan en docs/plan_prueba_ciegas.md.

### Resultados de la prueba a ciegas (2026-11-05)

Detalle: `docs/resultados_prueba_ciegas.md` y `docs/impacto_economico_eeuu.md`. Scripts `33` a `39`.

**Datos (Fase 1):** se bajaron los siete estados nuevos con la clave de NASS (variable de entorno, nunca en archivos): 506 condados y 20.867 condado-años en la base, más los tres originales (33.411 condado-años, 799 condados). CHIRPS 280 MB, bajo el límite de 500 MB; no se recortó ningún estado. Los censos de riego (1997-2022) sí bajaron por la API. Kansas pierde la mitad de sus condados por el filtro de salto de área (51 de 105). El código nuevo, aplicado a los tres originales, reproduce la base y las predicciones anteriores con diferencia 0.

**Fase 2 (modelo, siete estados que nunca vio, 1991-2025, 15.838 condado-años y 1.622 pérdidas):**

| | AUC | Heidke | Valor p |
|---|---:|---:|---:|
| Modelo | 0,739 | 0,318 | 0,001 |
| Regla de lluvia | 0,659 | 0,218 | 0,001 |
| Historia de pérdidas del condado | 0,589 | 0,057 | 1,000 |
| Azar | 0,504 | 0,001 | 0,249 |

- **Criterio fijado: se cumplen los tres** (AUC +0,080 frente a la regla, Heidke mayor, valor p de 0,001). El modelo pasa.
- Sin 2012: 0,709 frente a 0,620. Sin condados con más de 25 % de riego: 0,769 frente a 0,677. 1995-2025: 0,824 frente a 0,762. Variante secundaria: 0,745.
- Por estado, gana en AUC en 6 de 7. **Minnesota: 0,46 (azar).** Wisconsin: el modelo pierde en AUC contra la regla.
- **Calibración:** en la prueba principal el Brier calibrado (0,094) es peor que la tasa media (0,092); en la variante secundaria es mejor (0,084).

**Fase 3A (semáforo):** **no se cumple el criterio** en ninguna prueba. Prueba 1 (año por año, 2006-2025, diez estados): verde menos rojo en Heidke +0,03 (−0,24 a +0,25), en pérdidas captadas +9,6 (−15,8 a +24,3), en "de cada $100" +$18 (−$6 a +$37). Prueba 2 (nuevos hasta 2018, 2019-2025): +0,01, −13,1 y +$10, todos con intervalo que incluye el cero. La variante con riego tampoco. Los verdes salen mejor en la estimación, pero falta poder estadístico.

**Fase 3B (Palmer):** AUC Palmer 0,658, regla 0,659, modelo 0,739 en los estados nuevos. Diferencia Palmer menos modelo −0,081 (mayor que 0,03): **el modelo aporta algo que el contrato simple no captura.** El Palmer iguala a la regla de lluvia. Con pago proporcional al 100 %, en 2012 pagaría $68.600 millones frente a una pérdida real de $22.200 millones.

**Fase 4 (dólares de 2025, diez estados, 1991-2025):** pérdida real $46.341 millones (1988-2025: $60.431 millones). De cada $100, a quien perdió: seguro real $34, modelo $34, Palmer $38, regla $31-32, azar $10. Costo de operar el seguro real con cifras del programa completo (GAO-17-501): A&O de $1.400 millones al año, 12,8 % de la prima (cálculo propio) y 18,5 % (ejemplo del GAO): $51-$74 por cada $100 que llegan a quien perdió; el índice, con costo de operar supuesto de 5-20 %: $15-$58. Es un supuesto. No hay un mensaje positivo claro sobre el costo.

**Decisiones y problemas durante la corrida:**
- Los procesos en paralelo se quedaron sin memoria (OpenBLAS). Se limitó a 1 hilo por proceso y 6 procesos, y se repitió. Sin efecto en resultados.
- En el semáforo hacia adelante, el salto de área se recalcula con años anteriores (más estricto que el original).
- La historia de pérdidas del condado se desempata al azar con semilla fija.
- El modelo usa latitud y longitud, fuera del rango de entrenamiento en los estados nuevos. Congelado por el plan; queda como debilidad.
- Se agregó la segunda forma de medir el costo (por cada $100 pagados), porque "que llegan a quien perdió" es muy dura con el seguro real, que paga por finca.
- Una orden de terminar todos los procesos de Python fue bloqueada por seguridad; se terminaron solo los propios.


---

## 2026-11-05: cierre del proyecto (partes A y B)

**Antes de empezar:** el árbol estaba limpio en el commit 9c77248, pero `git pull` NO se pudo hacer: GitHub pidió usuario y la sesión no es interactiva (sin credenciales guardadas ni `gh`). Se sigue con el estado local, que coincidía con origin/main en el último dato conocido. Los commits quedan locales; el push puede fallar por lo mismo y se anotará.

### Plan congelado del cierre (copia de docs/plan_cierre.md)



**Fecha:** 2026-11-05. **Estado:** escrito y subido a git ANTES de correr ninguna de las cuatro fases. El commit "Plan congelado del cierre" es la prueba de ese orden.

**Objetivo de la parte A:** cerrar cuatro preguntas que dejó abierta la prueba a ciegas (`docs/resultados_prueba_ciegas.md`). Todo es adicional: no se cambia el modelo principal ni sus resultados. Los datos y las predicciones de la prueba a ciegas (`ciegas_predicciones_principal.csv`) se leen tal cual.

**Qué se declara antes de empezar:**
- Los resultados de la prueba a ciegas ya se conocen. Lo único que no se ha visto es: el modelo sin ubicación, la recalibración con años locales, el contrato Palmer con topes, las causas de siniestros por estado y el semáforo por causa.
- Los criterios de abajo no se cambian después de ver resultados. Si no se cumplen, se dice.
- Si un dato falta o algo falla, se anota, se decide lo más razonable, se explica y se sigue.

#### Fase 1. ¿El modelo aprende clima o geografía?

**Qué se hace.** Se repite la prueba a ciegas principal: cada año *t* de 1991 a 2025, el modelo se entrena solo con Iowa, Illinois e Indiana en años anteriores a *t* y predice los siete estados nuevos. Todo igual a `35_prueba_ciegas.py` (mismo LightGBM, misma rejilla de hiperparámetros escogida por AUC en los 3 años previos, misma calibración isotónica, mismo corte de pago, misma regla de lluvia, mismas semillas), con **un solo cambio**: se quitan latitud, longitud y la variable de estado (`grupo`). No queda ninguna variable que identifique el estado ni el condado. Quedan: lluvia de mayo a septiembre (% de lo normal), meses secos seguidos, falta de lluvia de julio y agosto, temperatura máxima de junio a agosto y Palmer de junio a agosto.

**Qué se compara.** Modelo sin ubicación, modelo original (el de la prueba a ciegas) y regla de lluvia, todos con la misma frecuencia de pago (la de la regla en los siete estados nuevos). Medidas: AUC, Heidke, % de pérdidas captadas, valor p barajando años completos (1.000 veces) e intervalos de 95 % remuestreando años completos (1.000 veces, semilla 2026). Todo con todos los años, sin 2012 y por estado (también 1995-2025 y sin condados con más de 25 % de riego, como contexto). Se reporta además la diferencia de AUC original menos sin ubicación con su intervalo (remuestreo de años pareado).

**Interpretación fijada.** Se mide con los siete estados nuevos juntos, todos los años 1991-2025:
- Si el AUC del modelo sin ubicación queda a **0,02 o menos** por debajo del original, el modelo aprende sobre todo clima.
- Si baja **más de 0,02**, parte de lo que aprende es geografía, y se dice.

#### Fase 2. ¿Cuántos años locales hacen falta para entrar a un estado nuevo?

**Qué se hace.** En cada uno de los siete estados nuevos, con las probabilidades del modelo original (prueba principal, entrenado solo en los tres estados), se recalibra con regresión isotónica (la misma de `29`, límites 0 y 1) usando **solo los primeros K años disponibles de ese estado**, con K = 0, 3, 5, 10 y 15.
- Los años disponibles de predicción empiezan en 1991. Con K = 15 se usan 1991-2005.
- **K = 0:** no hay datos locales. Se usa la probabilidad calibrada de la prueba principal (calibrada con los tres estados originales).
- **K de 3 a 15:** la isotónica se ajusta, por estado, con la probabilidad sin calibrar (`prob`) y la pérdida real de los primeros K años de ese estado, y se aplica a los años posteriores.
- **Años de evaluación, iguales para todos los K: 2006-2025** (los años posteriores a los 15 de calibración más largos). Así todos los K son comparables.

**Qué se reporta.** Para cada K y cada estado, el Brier de la probabilidad recalibrada frente al Brier de la tasa media de pérdida de ese estado en los años de evaluación (la misma referencia de los resultados anteriores). Curva de calibración (diez grupos de igual tamaño por probabilidad, con los siete estados juntos) para cada K.

**Conclusión fijada.** El menor K con el que el Brier queda mejor que la tasa media en **al menos 5 de los 7 estados**. Si ningún K lo logra, se dice.

#### Fase 3. Contrato Palmer con topes

**Disparador.** El de `37_palmer_ciegas.py`: promedio del Palmer de julio y agosto del condado bajo el percentil 15 de los años anteriores del condado (mínimo 10), con pago en línea recta hasta el 100 % en el percentil 2. Diez estados, 1991-2025 (las mismas filas de `ciegas_impacto_detalle.csv`).

**Dos cambios:**
1. **Suma asegurada** de 50 % y 75 % del valor esperado (más 100 % como referencia sin topes).
2. **Tope de pago total por año**, en los diez estados juntos, igual a **2 veces la prima pura anual** del mismo contrato y la misma suma asegurada. La prima pura anual es el pago total promedio por año de ese contrato sin tope, 1991-2025. Si un año se pasa del tope, todos los pagos de ese año se reducen en la misma proporción.

**Comparaciones.** Contrato Palmer con y sin tope, regla de lluvia (misma fórmula proporcional, con la misma regla de tope calculada con su propia prima) y modelo (pago = suma × severidad prevista cuando se activa el corte aplicable, también con y sin la misma regla de tope). Medidas: pagos totales, pago en 2012 frente a la pérdida real de 2012, % de la pérdida en dólares cubierta, de cada $100 cuántos llegan a quien perdió (condado-años con pérdida) y prima pura como % de la suma asegurada. Dólares de 2025.

**Interpretación fijada.** El contrato con topes es **"vendible"** si se cumplen las dos condiciones, en cada una de las sumas aseguradas (50 % y 75 %):
1. En **ningún año** de 1991-2025 el pago total de los diez estados supera **1,5 veces** la pérdida real de ese año (suma de los diez estados).
2. De cada $100 que paga, llegan a quien perdió **al menos lo mismo** que con la regla de lluvia con tope (misma suma y misma regla de tope). Se reporta también frente a la regla de lluvia sin tope.

Si no, se dice cuál condición falla y en qué años.

#### Fase 4. Minnesota y un semáforo por causa de los siniestros

##### A. Diagnóstico de Minnesota (descriptivo; no se afirman causas que los datos no muestren)
- **Fuente:** Cause of Loss de la RMA (`colsom_*.zip`, ya en `datos/crudos/eeuu/rma`), maíz (cultivo 0041), 1989-2025, diez estados, indemnización en dólares de 2025 (CPI-U, como `31`).
- **Grupos de causa (se fijan aquí):**
  - **Sequía:** código 11 (Drought). Es la misma definición que ya usa `31` para "indemnización por sequía". Calor (12) y viento caliente (62) quedan en "otras" y se muestran aparte en la tabla de detalle.
  - **Exceso de humedad:** 31 (Excess Moisture/Precipitation/Rain) y 51 (Flood).
  - **Heladas o frío:** 41 (Frost), 42 (Freeze), 43 (Cold Winter), 44 (Cold Wet Weather), 45 (Insufficient Chilling Hours).
  - **Granizo:** 21.
  - **Precio:** 01 (Decline in Price).
  - **Otras:** todo lo demás (calor, vientos, insectos, enfermedades, fauna, incendio, otras).
- **Qué se calcula:** por estado, la parte de las indemnizaciones por cada grupo; Minnesota frente a los otros nueve estados; y Minnesota en los **años de falla del modelo**, definidos como los años en que al menos 10 % de los condados de Minnesota con dato tuvieron pérdida y el modelo (prueba principal, mismo corte de pago de 35) captó menos de la mitad de esas pérdidas. Se compara la mezcla de causas en esos años contra los demás años de Minnesota y contra los otros estados en los mismos años.

##### B. Semáforo por causa (alternativa al semáforo de `30` y `36`)
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

#### Fase 5. Entregables del análisis

`docs/resultados_cierre.md` (plan, resultado de cada fase, si cada criterio se cumplió y qué significa, con "qué se puede decir y qué no"); figuras `docs/figuras/pitch_cierre_*.png` (modelo con y sin ubicación, calibración según años locales, Palmer con y sin topes año por año, causas de los siniestros por estado, semáforo por causa en años de prueba y mapa del semáforo por causa); `docs/requisitos_datos.md` actualizado si un resultado cambia una recomendación; scripts `40` a `44`; commit y push.

#### Parte B (sin análisis nuevos y sin cambiar cifras)

Cuaderno final `notebooks/proyecto_final.ipynb` con su HTML sin código; resumen de una página; simulador listo para publicar; limpieza y actualización de CLAUDE.md, README, bitácora, metodología e historia del proyecto; pruebas; zip de contexto.

#### Reglas de decisión si algo falla

- Un dato que no existe se anota, se decide lo más razonable, se explica y se sigue.
- Los criterios de arriba no se modifican después de ver resultados.
- Nunca se escriben claves en archivos.


### Resultados del cierre (2026-11-05)

Detalle: `docs/resultados_cierre.md`. Scripts `40` a `46`. El plan se subió antes de correr nada (commit "Plan congelado del cierre"). **Corrección a la nota de arriba:** `git pull` falló desde PowerShell, pero desde Bash funcionó ("Already up to date"), igual que el push. No hubo conflictos.

- **Fase 1 (sin ubicación):** AUC 0,734 frente a 0,739 del original y 0,659 de la regla (siete estados nuevos). Diferencia 0,005 (−0,021 a 0,030). Se cumple la regla fijada (0,02 o menos): el modelo aprende sobre todo clima. El Heidke baja de 0,318 a 0,284. Sin 2012: 0,705 frente a 0,709.
- **Fase 2 (años locales):** estados con mejor Brier que la tasa media (2006-2025): K=0: 4; K=3: 0; K=5: 1; K=10: 3; K=15: 5. **El menor K que cumple es 15.** Ohio y Minnesota no mejoran con ningún K.
- **Fase 3 (Palmer con topes):** no es vendible. Con tope, pago anual máximo frente a pérdida de ese año: 28,2 veces (suma 50 %) y 42,3 veces (suma 75 %), en 2025; pagos mayores de 1,5 veces la pérdida en 18 y 23 de 35 años. La condición 2 (de cada $100 igual o mejor que la regla de lluvia con tope) sí se cumple ($23 frente a $20). El tope solo se activa en 4 años (2012, 2021, 2022 y 2023).
- **Fase 4A (Minnesota):** sequía 26 % de lo pagado (la más baja de los diez estados), exceso de humedad 41 %. En los 4 años de falla (1992, 1993, 2007, 2014), sequía 12,6 %. Descriptivo.
- **Fase 4B (semáforo por causa):** no cumple (1999-2025: diferencias +0,10, +6,0 y +$8,1, todas con intervalo que incluye el cero; 2006-2025: solo "de cada $100" excluye el cero). **Decisión de diseño que se anota:** el filtro de calidad exige 25 años de datos, así que en 1999-2005 todo queda en rojo; no se cambió el filtro (estaba fijado).

**Decisiones y problemas:**
- Definición de sequía = código 11 (como en `31`); calor y viento caliente quedaron en "otras". Fijado en el plan antes de correr.
- Una figura salió con textos superpuestos y con los signos de dólar leídos como fórmulas; se corrigió en `45`.

### Parte B: proyecto terminado (2026-11-05)

- **Cuaderno final** `notebooks/proyecto_final.ipynb` (13 secciones; solo lee tablas y figuras, las cifras del texto salen de las tablas) y `docs/proyecto_final.html` sin código. Se construye con `scripts/46_construir_cuaderno.py`; corrió completo sin errores.
- **Resumen de una página:** `docs/resumen_final.md`.
- **Simulador (`app.py`):** pestañas de EE. UU. primero (riesgo por condado, semáforo, simular el seguro con regla, modelo, Palmer y **Palmer con topes**) y antecedentes al final; las tablas opcionales pueden faltar sin romper la app (probado quitando cuatro); solo lee archivos calculados, sin MLflow; rutas relativas. En el semáforo, nota visible de que no está probado, con las dos opciones. Probado con `streamlit run app.py` (responde 200) y con la herramienta de pruebas de Streamlit (sin excepciones). Archivos que usa: unos 27 MB (menos de 100 MB): lista para Streamlit Community Cloud; pasos en el README. Se agregó `requirements-app.txt` (solo lo que necesita la app).
- **Revisión de cifras:** se compararon los documentos finales con `ciegas_impacto_simulacion.csv` y `ciegas_impacto_resumen.json`. Diferencia encontrada: la pérdida real de 1991-2025 es $46.340,6 millones y la de 1988-2025 es $60.431,3 millones; los textos decían $46.340 y $60.430 (truncados). **Se corrigieron a $46.341 y $60.431** en `CLAUDE.md`, `docs/impacto_economico_eeuu.md` y esta bitácora. Los demás datos revisados (pagos del modelo $65.000 millones, Palmer $154.000 millones, de cada $100: $34 / $34 / $38 / $10, costos $51-$74 y $15-$58) coinciden.
- **Limpieza:** `docs/historia_del_proyecto.md` ya no cita la cifra de productores del piloto del PNUD (no se verificó); `CLAUDE.md` quitó de "Pendiente" el renombrado del repositorio y la verificación de fuentes del café.

## 2026-11-08: depuración del proyecto (solo el seguro de sequía para el maíz de EE. UU.)

**Pedido:** dejar en el proyecto solo el seguro de sequía para el maíz de EE. UU. y retirar los antecedentes (maíz en Colombia, EE. UU. y México con la regla de lluvia, y café en Colombia), incluida la parte de recomendaciones para Colombia. Trabajo en la rama `depuracion-eeuu`, sin commits y sin descargar datos.

**Plan (escrito antes de borrar):**
1. Pasar a `scripts/comun.py` las funciones que los scripts finales (`27` a `46`) usaban de los scripts viejos (`04`, `05`, `07`, `09`, `11`, `19`, `20` y `24`), copiadas sin cambiar la lógica, y comprobar que son idénticas a las originales.
2. Dejar `01` solo con las descargas de EE. UU. y `08` usando `comun.py`.
3. Borrar los scripts `02`–`07` y `09`–`26`, los documentos, cuadernos, figuras y tablas que solo servían a los antecedentes.
4. Quitar Colombia, café y México del simulador, del cuaderno final, del resumen y de los documentos que quedan. Los planes congelados (`plan_prueba_ciegas.md` y `plan_cierre.md`) no se tocan, y las entradas de esta bitácora desde el 2026-11-04 se conservan tal como se escribieron.

**Resultado:**
- `scripts/comun.py`: 13 funciones y sus constantes. Comparadas con las originales del commit `2789634` (árbol de sintaxis, sin docstrings ni mensajes): todas iguales; la única diferencia es el valor por defecto de dos argumentos de `lluvia_mensual()`, que los scripts siempre pasan. `crear()` arma el mismo pipeline que `24_evaluacion_robusta.crear()`. lightgbm, scikit-learn, xarray y shapely se importan dentro de las funciones que los usan.
- La figura `pitch_serie_tiempo_eeuu.png` (antes de `17`) pasó a `32_figuras_eeuu.py`; regenerada, sale igual a la original.
- `tests/test_funciones.py` usa `comun.py`; se quitó la prueba de la partición del café y se agregaron dos (salto de nivel y tendencia con todos los años). Las 10 pruebas de `comun.py` pasan. Las dos de `29` y `31` no se pudieron correr en este equipo porque faltan lightgbm, mlflow y shap (no se instaló nada).
- Simulador: quedan tres pestañas (riesgo por condado, semáforo y simular el seguro). Probado con la herramienta de pruebas de Streamlit: sin excepciones, con los cuatro disparadores.
- Cuaderno final: 11 secciones (se quitaron "El intento en Colombia" y "Lo que aprendimos para Colombia"); se ejecutó sin errores y se exportó a `docs/proyecto_final.html`.
- Borrados: 24 scripts, 15 documentos, 2 cuadernos, 28 figuras y 79 tablas procesadas. Todo sigue en el historial de git.
- No se corrieron los scripts de análisis: en este equipo no están los datos crudos ni `mlflow.db`.

## 2026-11-08 (segunda parte): auditoría crítica y nuevo relato (plan, escrito antes de editar)

**Hallazgos de la auditoría** (con las tablas ya calculadas; la etiqueta es `perdida_previa`, la misma de la prueba a ciegas):
1. **La comparación "de cada $100" con el seguro real no es válida.** En `38_impacto_ciegas.py` el seguro real se mide con la misma vara que el modelo: sus indemnizaciones (todas las causas, por finca, incluido el precio) que caen en condado-años cuyo promedio bajó del 80 %. El seguro real está hecho para pagar fincas que pierden aunque el condado no, y para pagar caídas de precio: esos pagos no son errores. La frase "el modelo dirige la plata igual que el seguro real" se retira.
2. **En EE. UU. la etiqueta del modelo (rendimiento del condado bajo el 80 %) ya la cubre un producto existente:** el seguro por rendimiento del condado (Area Risk Protection, RMA), que frente a esa etiqueta no tiene riesgo de base. Un índice de clima solo aporta rapidez (se conoce en septiembre) o servir donde no hay buen dato de rendimiento. Por eso el valor del proyecto está en el método y en lo que le falta a Colombia, no en un seguro para EE. UU.
3. **Gran parte del acierto es saber qué años son malos.** Siete estados nuevos: AUC del modelo 0,739; si a todos los condados de un año se les da el mismo puntaje (el promedio del modelo en ese año), 0,723. Dentro de cada año (27 años con 10 o más pérdidas, ponderado por pérdidas), el modelo 0,708 y la regla 0,650: el modelo sí distingue condados, pero poco. Descriptivo, calculado después de ver los resultados; no cambia ninguna decisión.
4. **LightGBM no es claramente el mejor:** año por año, el bosque aleatorio tiene AUC 0,826 frente a 0,816, con rangos que se superponen; en la prueba 2019-2025 la regresión logística da 0,902 frente a 0,777. Se mantiene porque así lo fijó el procedimiento, pero no se dice que sea el mejor.

**Plan:**
1. Recuperar del commit `2789634` solo lo que necesita el relato de Colombia, sin los scripts: `docs/requisitos_datos.md` (corrigiendo las referencias a documentos retirados), `datos/procesados/comparacion_paises_resumen.csv` y `docs/figuras/pitch_barras_paises.png`.
2. Cuaderno final: volver a poner la sección de Colombia (por qué EE. UU. es el laboratorio) y la de requisitos y recomendaciones; quitar la comparación de "de cada $100" y de costos con el seguro real; agregar una sección "Lo que la auditoría encontró" con los hallazgos 1 a 4, calculando el 3 desde `ciegas_predicciones_principal.csv`.
3. Corregir la frase del seguro real en `resumen_final.md`, `historia_del_proyecto.md`, `impacto_economico_eeuu.md`, `resultados_prueba_ciegas.md`, `metodologia.md`, `README.md` y `CLAUDE.md`. Los planes congelados no se tocan; las cifras de los scripts no cambian.
4. No se corre ningún modelo ni se descarga nada.

**Resultado de la segunda parte:**
- Recuperados del commit `2789634`: `docs/requisitos_datos.md` (con las referencias a documentos retirados corregidas y la razón de ser del proyecto al inicio), `datos/procesados/comparacion_paises_resumen.csv` y `docs/figuras/pitch_barras_paises.png`. Los scripts de Colombia no se recuperaron.
- Cuaderno final: 13 secciones. Vuelven "Por qué Colombia, y por qué el laboratorio es EE. UU." (5) y "Lo que esto significa para Colombia" (12); nueva "Lo que encontró la auditoría" (11); la sección de dólares (10) ya no compara con el seguro real ni sus costos. Ejecutado sin errores; cifras de la auditoría: 0,739 (modelo), 0,723 (promedio del año), 0,708 y 0,650 (dentro del año, modelo y regla; 27 años). Años con el modelo bajo 0,6 dentro del año: 1992, 1993, 1998 y 2007.
- Frase del seguro real corregida en `resumen_final.md`, `historia_del_proyecto.md` (nueva sección 7 con la frase de la presentación), `impacto_economico_eeuu.md`, `resultados_prueba_ciegas.md`, `metodologia.md`, `README.md` y `CLAUDE.md`. Las tablas y scripts no cambian: la fila del seguro real sigue en `ciegas_impacto_simulacion.csv`, pero no se presenta como comparación.

## 2026-11-08 (tercera parte): auditoría técnica del modelo y de los datos

**Qué se corrió** (exploratorio, después de ver los resultados; no cambia ninguna decisión; script en el área temporal de la sesión, no en el repositorio): con `eeuu_sequia_base.csv` (Iowa, Illinois e Indiana), validación hacia adelante 1991-2025 con la misma etiqueta de `29` (pérdida con tendencia de años anteriores; coincide en el 100 % de las 9.614 filas). Como lightgbm no está instalado en este equipo, se usó `HistGradientBoostingClassifier` de scikit-learn con hiperparámetros parecidos; su orden coincide con el LightGBM original (Spearman 0,90).

**Resultados (AUC; rango de 95 % remuestreando años; sin 2012; dentro de cada año, 13 años con 10 o más pérdidas):**

| Puntaje | AUC | Rango 95 % | Sin 2012 | Dentro del año |
|---|---:|---:|---:|---:|
| Bosque aleatorio, todas las variables | 0,834 | 0,69-0,93 | 0,784 | 0,705 |
| LightGBM original (29) | 0,816 | 0,59-0,94 | 0,757 | 0,704 |
| Boosting de scikit-learn, todas | 0,799 | 0,54-0,92 | 0,732 | 0,704 |
| **Índice simple: calor de julio y agosto (sin entrenar)** | **0,780** | 0,57-0,92 | 0,701 | 0,631 |
| Logística, todas | 0,770 | 0,49-0,91 | 0,700 | 0,649 |
| Logística con 4 variables (calor y Palmer de julio y agosto) | 0,753 | 0,47-0,91 | 0,669 | 0,632 |
| Regla de lluvia de junio a agosto | 0,690 | 0,43-0,84 | 0,598 | **0,480** |
| Índice de Palmer de julio y agosto | 0,683 | 0,44-0,86 | 0,573 | 0,534 |
| Tasa previa de pérdida del condado | 0,559 | 0,47-0,67 | 0,616 | 0,566 |

**Otros hallazgos:**
- Los resultados del modelo se reproducen de forma independiente; no se encontró fuga de información.
- Los resultados casi no cambian con umbral de pérdida de 70 % o 90 %.
- Cinco años (2012, 1991, 1993, 1995 y 2002) concentran el 74 % de las pérdidas de 1991-2025; 1993 fue inundación, no sequía.
- **El modelo del tamaño de la pérdida casi no aporta:** correlación 0,24 con el faltante real; error medio 0,099 frente a 0,105 de usar el promedio previo.
- Datos: 0,3 % de cifras repetidas, ningún condado con salto de área, sin faltantes salvo el riego (vacío en los tres estados originales). No se pudo verificar el efecto del abandono de lotes (falta el área sembrada) ni repetir la prueba en los siete estados nuevos con índices simples (su base no está en este equipo).

## 2026-11-08 (cuarta parte): cinco modelos y elección del mejor (plan, escrito y congelado antes de correr)

**Pedido:** con toda la información disponible, entrenar 5 modelos y escoger el mejor para predecir.

**Datos:** `datos/procesados/eeuu_sequia_base.csv` (Iowa, Illinois e Indiana; 293 condados; 1981-2025). La base de los siete estados nuevos no está en este equipo y regenerarla exige descargas, así que la prueba a ciegas del modelo elegido queda como paso siguiente. Etiqueta: la misma de `29` (pérdida = rendimiento de 80 % o menos de la tendencia ajustada solo con años anteriores).

**Variables (todas las disponibles):** lluvia de mayo a septiembre (% de lo normal), racha de meses secos, déficit de julio y agosto, temperatura máxima de junio a agosto (diferencia con lo normal), Palmer de junio a agosto, latitud, longitud y estado. El riego está vacío en estos tres estados.

**Los 5 modelos** (scikit-learn; lightgbm no está instalado):
1. Regresión logística regularizada (C en 0,01, 0,1 y 1).
2. Logística con curvas suaves (splines de 4 nodos por variable; C en 0,01, 0,1 y 1).
3. Bosque aleatorio (300 árboles; profundidad 6 o 10; hoja mínima 20 o 50).
4. Boosting de gradiente (`HistGradientBoostingClassifier`, equivalente a LightGBM; 300 iteraciones, tasa 0,03; hojas 15 o 31; hoja mínima 20 o 50).
5. Boosting monótono (como el 4, con la restricción de que más calor, más déficit o más meses secos nunca bajan el riesgo, y más lluvia de junio a agosto o más Palmer nunca lo suben; hojas 7 o 15; hoja mínima 50).

**Referencias (no compiten):** azar, regla de lluvia de junio a agosto (percentil 15), índice simple de calor de julio y agosto y tasa previa de pérdida del condado.

**Validación:** año por año, de 1991 a 2025, igual que `29`. Para predecir el año t se entrena solo con años anteriores; los hiperparámetros se escogen por AUC en los 3 últimos años de entrenamiento (si no tienen pérdidas, la primera opción) y la probabilidad se calibra con regresión isotónica en esos mismos 3 años.

**Criterio de elección (congelado):**
- Se escoge solo con el **periodo de desarrollo: predicciones de 1991 a 2010**. El **periodo de prueba, 2011 a 2025 (incluye 2012)**, no se mira para escoger.
- Puntaje de elección = promedio de (AUC global) y (AUC dentro de cada año, ponderado por pérdidas, en años con 10 o más pérdidas), en desarrollo.
- Si la diferencia con el siguiente es menor que 0,01, gana el más simple, en el orden logística < splines < monótono < bosque < boosting.
- En prueba se reportan, para los 5 modelos y las referencias: AUC, AUC sin 2012, AUC dentro del año, Brier calibrado frente a la tasa media, Heidke pagando con la misma frecuencia que la regla y rangos de 95 % remuestreando años. **El resultado en prueba no cambia la elección.**
- **Lectura honesta fijada de antemano:** si el modelo elegido no supera al índice simple de calor en más de 0,02 de AUC en prueba, se dirá que el aprendizaje automático no aporta lo suficiente frente a un índice simple.

**Modelo final:** el elegido se reentrena con todos los años (1981-2025) y se guarda en `modelos/` con sus metadatos, junto con un script para predecir. Script: `scripts/47_cinco_modelos.py`.

## 2026-11-08 (quinta parte): datos adicionales para un trabajo completo (plan, escrito antes de descargar)

**Autorización:** la usuaria autorizó descargar los datos que hagan falta.

**Plan:**
1. **Reconstruir los datos crudos** con los scripts existentes, sin cambiarlos: `01` (condados, calendario, ONI, CHIRPS y RMA de los tres estados; NASS si hay clave), `27` (NOAA nClimDiv, precios, CPI y censos) y `33` (CHIRPS de los siete estados; NASS y riego de los siete estados, **requiere `NASS_API_KEY`**). Luego `34` para la base de los diez estados.
2. **Temperatura diaria nueva:** NOAA nClimGrid-Daily, promedios por condado ya calculados por NOAA (`https://www.ncei.noaa.gov/data/nclimgrid-daily/access/averages/`), temperatura máxima y mínima diarias, mayo a septiembre de 1981 a 2025, para los diez estados (unos 450 archivos de ~1 MB; solo se guardan las filas de los diez estados). Script nuevo `49_temperatura_diaria.py`.
3. **Grados-día** (método del seno simple, como Schlenker y Roberts, 2009): grados-día de 10 a 29 °C (calor útil) y **grados-día por encima de 29 °C** (calor dañino), por condado y año, para junio, julio, agosto y el total de junio a agosto.
4. **Librerías:** se instalan `geopandas`, `xarray`, `shapely` y `lightgbm` en el Python de este equipo para correr `34` y comparar con el LightGBM real.
5. Después de esto, un plan nuevo (congelado antes de correr) para repetir la comparación de los cinco modelos con las variables de grados-día y la prueba a ciegas en los siete estados. **Las variables nuevas no se agregan al análisis de la cuarta parte, que ya está corriendo con su plan.**

**Resultado de la cuarta parte (cinco modelos, tres estados originales; `scripts/47_cinco_modelos.py`):**

| Modelo | Desarrollo 1991-2010: AUC / dentro del año / puntaje | Prueba 2011-2025: AUC / sin 2012 / dentro del año | Brier calibrado en prueba (tasa 0,072) |
|---|---|---|---|
| Regresión logística | 0,699 / 0,632 / 0,666 | 0,905 / 0,721 / 0,682 | 0,069 |
| Logística con splines | 0,753 / 0,704 / 0,729 | 0,933 / 0,770 / **0,795** | **0,040** |
| Boosting monótono | 0,693 / 0,616 / 0,654 | 0,933 / 0,775 / 0,763 | 0,056 |
| **Bosque aleatorio (elegido)** | **0,755 / 0,733 / 0,744** | 0,940 / 0,824 / 0,684 | 0,055 |
| Boosting (equivalente a LightGBM) | 0,712 / 0,659 / 0,686 | **0,943 / 0,841** / 0,774 | 0,047 |
| Índice de calor jul-ago (referencia) | 0,700 / 0,565 / 0,632 | 0,912 / 0,678 / 0,747 | – |
| Regla de lluvia (referencia) | 0,615 / 0,518 / 0,566 | 0,821 / 0,533 / 0,415 | – |

- **Elegido con el criterio congelado: bosque aleatorio** (puntaje de desarrollo 0,744; el segundo, splines, 0,729, a más de 0,01). Hiperparámetros del modelo final: profundidad 10, hoja mínima 20; calibrado con isotónica. Guardado en `modelos/modelo_final.joblib`.
- En prueba supera al índice de calor en AUC por 0,028 (pasa el umbral de 0,02 fijado) y sin 2012 por 0,146.
- **Advertencias:** la prueba es casi solo 2012 (225 de las 302 pérdidas; solo 4 años tienen 10 o más pérdidas); **dentro de cada año, en prueba, el bosque (0,684) queda por debajo del índice de calor (0,747), de los splines (0,795) y del boosting (0,774)**; en desarrollo, su Brier calibrado (0,091) es peor que la tasa media (0,082). La elección no cambia (así se fijó), pero no es concluyente: hace falta la prueba a ciegas en los siete estados (quinta parte).

## 2026-11-08 (sexta parte): comparación final a ciegas con grados-día (plan, escrito y congelado antes de ver los datos nuevos)

**Datos:** base de los diez estados que arma `34` (`eeuu_ciegas_base.csv`) más los grados-día de `49` (`eeuu_grados_dia.csv`). La clave de NASS la dio la usuaria por el chat; se usó solo como variable de entorno en el comando, no quedó en ningún archivo.

**Esquema (igual que la prueba a ciegas de `35`, modo principal):** para cada año t de 1991 a 2025, cada modelo se entrena **solo con Iowa, Illinois e Indiana** y años anteriores a t, y predice el año t en los **siete estados nuevos**, que nunca se usan para entrenar, escoger hiperparámetros ni calibrar. Etiqueta: pérdida = rendimiento de 80 % o menos de la tendencia del condado con años anteriores (como `35`). Hiperparámetros por AUC en los 3 últimos años de entrenamiento, con las mismas rejillas de `47`.

**Dos conjuntos de variables, sin ubicación ni estado** (el cierre mostró que la ubicación casi no aporta y en estados nuevos queda fuera de rango):
- **A (clima mensual):** lluvia de mayo a septiembre, racha de meses secos, déficit de julio y agosto, temperatura máxima de junio a agosto y Palmer de junio a agosto.
- **B (A + calor diario):** A más grados-día de 10 a 29 °C y grados-día por encima de 29 °C de junio, julio, agosto y el total de junio a agosto, y días con máxima de 35 °C o más de junio a agosto.

**Modelos:** los mismos 5 de `47` (logística, splines, bosque, boosting de gradiente y boosting monótono; en el monótono, los grados-día por encima de 29 °C y los días de 35 °C solo pueden subir el riesgo, y los de 10 a 29 °C quedan libres), con A y con B: 10 combinaciones. Además, LightGBM real con B como referencia de comparación con el proyecto original.

**Referencias:** azar, regla de lluvia de junio a agosto, índice de calor de julio y agosto (temperatura máxima), **índice de grados-día por encima de 29 °C de junio a agosto** y tasa previa de pérdida del condado.

**Criterio de elección (congelado):**
- Se escoge con los **siete estados nuevos, años 1991-2010**. Los **años 2011-2025** de esos estados son la confirmación y no se miran para escoger.
- Puntaje = promedio de (AUC global) y (AUC dentro de cada año, ponderado por pérdidas, en años con 10 o más pérdidas).
- Empate si la diferencia es menor que 0,01: gana el más simple (logística < splines < monótono < bosque < boosting) y, entre conjuntos, A sobre B.
- En confirmación se reportan para todos: AUC, AUC sin 2012, dentro del año, Heidke con la frecuencia de la regla, Brier calibrado frente a la tasa media, AUC por estado y rangos de 95 % remuestreando años. **No cambian la elección.**
- **Lectura honesta fijada de antemano:** si en confirmación el elegido no supera en más de 0,02 de AUC al mejor índice simple (calor o grados-día por encima de 29 °C), se dirá que el aprendizaje automático no aporta lo suficiente frente a un índice simple, y que para un contrato conviene el índice simple.

**Modelo final:** la combinación elegida se reentrena con los diez estados, 1981-2025, y reemplaza a `modelos/modelo_final.joblib` (el de la cuarta parte queda documentado aquí). Script: `scripts/50_comparacion_final.py`.
