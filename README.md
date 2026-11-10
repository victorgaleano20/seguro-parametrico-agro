# Seguro paramétrico de sequía para el maíz de EE. UU.

Proyecto de la materia Proyecto 2 (Especialización en Ciencia de Datos e IA).

Un seguro por índice paga solo, mirando un dato público (lluvia, calor), sin visitar la finca. Su debilidad es el **riesgo de base**: puede pagar a quien no perdió y no pagar a quien sí. Este proyecto mide, con datos públicos de diez estados de EE. UU. (1991-2025), si un modelo con el clima del verano dirige la plata a quien de verdad perdió la cosecha de maíz.

**Por qué EE. UU.:** el proyecto empezó en Colombia, pero allá el dato de cosecha municipal no permite medir la pérdida y no hay pagos públicos de seguros para comprobar nada. EE. UU. sirve de laboratorio: tiene 45 años de rendimiento por condado y los pagos reales del seguro. Allá ya existe un seguro que paga por el rendimiento del condado, así que el índice de clima no es un producto nuevo para EE. UU.; lo que se mide es el método, y lo que se aprende es qué necesita Colombia (`docs/requisitos_datos.md`).

Se entregan:
- un análisis exploratorio de los datos (`notebooks/eda.ipynb`);
- una comparación de cinco modelos de aprendizaje automático y la elección del modelo final, que estima la probabilidad de pérdida de cosecha por condado (`modelos/modelo_final.joblib`);
- una prueba en siete estados que el modelo no usó para entrenar (sus años 1991-2010 sí se usaron para escoger el modelo), y una validación dejando un estado afuera;
- un semáforo de condados (que no se sostuvo);
- el impacto en dólares con datos reales (NASS, RMA, ERS y BLS);
- una app en Streamlit para el jurado y para especialistas (`streamlit run app.py`).

**Empieza aquí:** el resumen de una página está en `docs/resumen_final.md`, y el proyecto contado de principio a fin en `notebooks/proyecto_final.ipynb` (versión sin código: `docs/proyecto_final.html`).

## Resultados principales

**Modelo final:** logística con curvas suaves (splines) sobre el clima del verano medido frente a lo normal de cada condado (lluvia, meses secos, déficit, temperatura máxima e índice de Palmer), sin ubicación. Ganó una comparación de cinco modelos con criterio fijado antes de correr, entrenando solo con Iowa, Illinois e Indiana y probando en siete estados que no se usaron para entrenar.

| Pregunta | Resultado (siete estados nuevos, 1991-2025, salvo que se diga otra cosa) |
|---|---|
| ¿Predice en estados que no usó para entrenar? | **Sí:** acierto al ordenar (AUC) 0,762 (rango 95 %: 0,64-0,85), sin 2012 0,738; en 2011-2025, el periodo que no se usó para escoger, 0,856 (0,73-0,89); azar 0,50 |
| ¿Mejor que una regla de lluvia? | **Sí, con claridad:** la regla saca 0,659; dentro de cada año, 0,700 frente a 0,650 |
| ¿Mejor que un índice simple de calor de julio y agosto? | **No se distinguen:** en 2011-2025, +0,021 de AUC con rango de 95 % de −0,009 a +0,086; dentro de cada año, −0,017. La validación dejando un estado afuera lo confirma |
| ¿Cuál de los 5 modelos? | El más simple de los que aprenden (splines) generalizó mejor que bosque, boosting, LightGBM y boosting monótono |
| ¿Sus probabilidades sirven? | Sin calibrar, sí (Brier 0,086 frente a 0,092 de la tasa media), aunque exageran en el riesgo más alto. La calibración con 3 años las empeoraba |
| ¿A dónde va la plata? (diez estados) | De cada $100 que pagaría el índice, llegan a condados con pérdida: modelo $31,7, índice de calor $32,4, regla $25,8, azar $8,4. **En dólares, el modelo no supera al índice de calor** |
| ¿Grados-día de calor (> 29 °C)? | En valor absoluto no se trasladan a estados nuevos; frente a lo normal mejoran el acierto dentro del año (0,721), pero es exploratorio |
| ¿Más estados de entrenamiento ayudan? | **No:** entrenando con 9 estados, en 2011-2025, 0,858 frente a 0,856 con 3 |
| ¿Funciona en todos los estados? | **No:** fuera de su estado, bien en Illinois (0,91), Indiana, Ohio, Kansas, South Dakota y Missouri; débil en Nebraska, Wisconsin e Iowa (0,57); falla en Minnesota (0,40), donde la pérdida viene del frío y del exceso de agua |
| ¿Algún semáforo se sostiene? | **No** (el margen de error incluye el cero) |
| ¿Contrato Palmer con topes vendible? | **No:** paga más de 1,5 veces la pérdida real en 18 a 23 de 35 años |

**En una frase:** con buenos datos, un modelo sencillo de clima ordena el riesgo de pérdida mejor que una regla de lluvia en estados que no usó para entrenar, pero un índice simple de calor hace prácticamente lo mismo, ninguno de los dos sirve donde la pérdida viene del frío o del exceso de agua, y el riesgo de base es grande (unos $2 de cada $3 irían a condados sin pérdida).

## Documentos

| Documento | Qué contiene |
|---|---|
| `docs/resumen_final.md` | Resumen de una página |
| `docs/eda.html` | Análisis exploratorio de los datos, sin código (cuaderno: `notebooks/eda.ipynb`) |
| `docs/proyecto_final.html` | El proyecto de principio a fin, sin código |
| `docs/requisitos_datos.md` | Qué necesita un seguro por índice: EE. UU. frente a Colombia, y 3 recomendaciones |
| `docs/historia_del_proyecto.md` | Decisiones, razones y qué NO decir (secciones 7 y 8: auditoría y modelo final) |
| `docs/metodologia.md` | El modelo y las métricas, explicados sin tecnicismos |
| `modelos/modelo_final.json` | El modelo final: variables, hiperparámetros, cómo se eligió y advertencias |
| `docs/resultados_modelo_eeuu.md` | El primer modelo (LightGBM) en los tres estados originales, aporte del clima, SHAP y semáforo |
| `docs/impacto_economico_eeuu.md` | Supuestos, pérdida real, lo que pagó la RMA y el seguro simulado |
| `docs/plan_prueba_ciegas.md` y `docs/resultados_prueba_ciegas.md` | Prueba a ciegas en siete estados: plan congelado antes de ver los datos y resultados |
| `docs/plan_cierre.md` y `docs/resultados_cierre.md` | Cierre: plan congelado y resultados |
| `docs/bitacora.md` | Qué se hizo en cada sesión, con su plan y sus resultados |

## Estructura de carpetas

| Carpeta | Qué contiene |
|---|---|
| `datos/crudos/` | Archivos tal como se descargaron, sin modificar (no están en el repositorio). Cada descarga queda anotada en `datos/crudos/registro_descargas.csv` (fuente, URL, archivo, fecha, tamaño). |
| `datos/procesados/` | Tablas generadas por los scripts. Las de más de 10 MB no se suben al repositorio y se regeneran con los scripts. |
| `notebooks/` | `proyecto_final.ipynb`: el proyecto de principio a fin; `eda.ipynb`: el análisis exploratorio. Solo leen tablas de `datos/procesados/` y figuras de `docs/figuras/`; no entrenan modelos. |
| `modelos/` | El modelo final (`modelo_final.joblib`) y su descripción (`modelo_final.json`). |
| `scripts/` | Scripts de Python numerados, que se corren en orden. `comun.py` tiene las funciones que comparten. La numeración tiene saltos porque se conserva la del proyecto original. |
| `docs/` | Documentos y figuras (`docs/figuras/`). |
| `tests/` | Pruebas de las funciones clave (`python -m pytest tests`). |
| `app.py`, `app_comun.py`, `paginas/` | App en Streamlit (varias páginas, Plotly): Resumen, Contrato y riesgo de base y Laboratorio de desempeño. Lee las tablas de `50`, `53` y `54`. |
| `CLAUDE.md` | Resumen corto para el asistente de cada integrante: estado, qué leer y reglas de trabajo. |

## Para el equipo: cómo empezar

Estos pasos funcionan en cualquier computador con Windows, Mac o Linux.

1. **Clonar el repositorio** (es público):
   ```
   git clone https://github.com/victorgaleano20/seguro-parametrico-agro.git
   cd seguro-parametrico-agro
   ```
2. **Instalar Python 3.12** desde [python.org](https://www.python.org/downloads/).
3. **Crear un entorno virtual** e instalar las librerías. Si tu carpeta está en OneDrive, Dropbox o Google Drive, crea el entorno **fuera** de ella para que no se sincronice. **En Windows, usa una ruta corta**: con el límite de 260 caracteres activo, un entorno muy profundo deja a `scikit-learn` sin poder cargar sus archivos. Un entorno en `~/.venvs/` funciona bien.
   ```
   # Windows (PowerShell)
   python -m venv $HOME\.venvs\seguro_parametrico
   & $HOME\.venvs\seguro_parametrico\Scripts\Activate.ps1
   # Mac / Linux
   python3 -m venv ~/.venvs/seguro_parametrico
   source ~/.venvs/seguro_parametrico/bin/activate

   pip install -r requirements.txt
   ```
4. **Pedir tu propia API key de NASS**, gratis. Cada persona usa la suya y **nunca se escribe en un archivo**.
   - Entra a [quickstats.nass.usda.gov/api](https://quickstats.nass.usda.gov/api), haz clic en **Request API Key**, escribe tu correo y la key te llega por email.
   - Defínela como variable de entorno **antes** de correr los scripts de descarga:
     ```
     # Windows (PowerShell), solo para esa terminal
     $env:NASS_API_KEY = "tu_clave"
     # Mac / Linux
     export NASS_API_KEY="tu_clave"
     ```
5. **Descargar los datos** (solo si vas a recalcular; las tablas procesadas pequeñas y las figuras ya vienen en el repositorio): scripts `01`, `27` y `33`. Si una descarga se corta, vuelve a correr el script: no repite lo que ya bajó.
6. **Abrir la app:** `streamlit run app.py`.
7. **Antes de trabajar**, lee `docs/historia_del_proyecto.md`, `docs/metodologia.md` y `docs/bitacora.md`. Las reglas de trabajo están en `CLAUDE.md`.

## Cómo correr

Desde la carpeta del proyecto, con el entorno activado:

```
# 1. Tres estados originales (Iowa, Illinois e Indiana)
python scripts/01_descargar_datos.py    # condados, calendario, CHIRPS, RMA, NASS (requiere NASS_API_KEY) y ONI
python scripts/08_base_eeuu.py          # base de NASS: rendimiento, filtros de calidad, tendencia y lluvia por condado
python scripts/27_adquisicion_eeuu.py   # temperatura y sequía de Palmer (NOAA), precios (ERS), CPI-U (BLS) y censos; unos 100 MB
python scripts/28_base_eeuu.py          # base condado x año con lluvia, temperatura, Palmer y ubicación
python scripts/29_modelos_eeuu.py       # regla, solo ubicación, logística, bosque y LightGBM; año por año y partición fija; MLflow (unos 60 minutos)
python scripts/30_semaforo_eeuu.py      # semáforo de condados y su prueba en 2019-2025
python scripts/31_impacto_eeuu.py       # pérdida real, RMA y seguro simulado en dólares de 2025
python scripts/32_figuras_eeuu.py       # figuras docs/figuras/pitch_eeuu_*.png y pitch_serie_tiempo_eeuu.png

# 2. Prueba a ciegas en siete estados nuevos
python scripts/33_adquisicion_ciegas.py # NASS por API (rendimiento, áreas y riego de los censos) y CHIRPS de los siete estados (unos 280 MB)
python scripts/34_base_ciegas.py        # base de los diez estados; valida que el código reproduce la de los tres originales
python scripts/35_prueba_ciegas.py      # prueba a ciegas del modelo, con y sin 2012, por estado y sin riego alto (unos 35 minutos)
python scripts/36_semaforo_ciegas.py    # semáforo: hacia adelante y geográfico
python scripts/37_palmer_ciegas.py      # contrato simple con el índice de Palmer
python scripts/38_impacto_ciegas.py     # dólares de 2025 en los diez estados y costo de operar
python scripts/39_figuras_ciegas.py     # figuras docs/figuras/pitch_ciegas_*.png

# 3. Cierre
python scripts/40_sin_ubicacion.py      # el modelo sin latitud, longitud ni estado (unos 35 minutos)
python scripts/41_calibracion_local.py  # recalibrar con 0, 3, 5, 10 y 15 años locales
python scripts/42_palmer_topes.py       # contrato Palmer con topes (suma de 50 % y 75 %)
python scripts/43_causas_siniestros.py  # causas de los siniestros por estado y diagnóstico de Minnesota
python scripts/44_semaforo_causa.py     # semáforo por causa de los siniestros
python scripts/45_figuras_cierre.py     # figuras docs/figuras/pitch_cierre_*.png

# 4. Comparación de modelos, modelo final y EDA (2026-11-08)
python scripts/47_cinco_modelos.py      # 5 modelos en los tres estados originales (unos 20 minutos)
python scripts/49_temperatura_diaria.py # temperatura diaria por condado (NOAA nClimGrid-Daily) y grados-día
python scripts/50_comparacion_final.py  # 5 modelos x 2 conjuntos, a ciegas en siete estados; guarda el modelo final (unos 50 minutos)
python scripts/52_grados_dia_anomalia.py # exploratorio: grados-día frente a lo normal
python scripts/53_dolares_modelo_final.py # predicciones del modelo final y dólares
python scripts/54_tablas_app.py         # tablas de la app: AUC con rangos de 95 % y diferencias pareadas
python scripts/55_validacion_por_estado.py # validación dejando un estado afuera (unos 7 minutos)
python scripts/48_predecir.py archivo.csv # predecir con el modelo final
python scripts/51_construir_eda.py      # arma notebooks/eda.ipynb (luego nbconvert, como el cuaderno final)

# 5. Cuaderno final: armarlo, ejecutarlo y exportar la versión sin código
python scripts/46_construir_cuaderno.py
python -m nbconvert --to notebook --execute --inplace notebooks/proyecto_final.ipynb
python -m nbconvert --to html --no-input --output-dir docs --output proyecto_final notebooks/proyecto_final.ipynb

python -m pytest tests                  # pruebas de las funciones clave
streamlit run app.py                    # app
mlflow ui --backend-store-uri sqlite:///mlflow.db   # corridas y versiones del modelo
python scripts/empaquetar_contexto.py   # al final de cada sesión: zip liviano para el chat asesor
```

`mlflow.db` y `mlruns/` quedan fuera de git y se regeneran con `29_modelos_eeuu.py` y `35_prueba_ciegas.py`. El modelo queda registrado como `perdida_maiz_eeuu`, alias `mejor_en_validacion`.

Nota para Windows: la librería C de NetCDF falla con rutas que tienen tildes. Por eso los scripts leen los NetCDF con `engine="scipy"`.

## La app

Se abre en local: `streamlit run app.py`. Solo lee tablas ya calculadas en `datos/procesados/` (scripts `50`, `53`, `54`); no entrena nada ni usa MLflow. Tiene tres páginas:
- **Resumen:** AUC del modelo, el índice de calor y la regla, con rangos de 95 %, y el veredicto calculado (dice "supera" solo si el rango de la diferencia excluye el cero).
- **Contrato y riesgo de base:** los tres disparadores pagan en el mismo número de condado-años; de cada $100, pérdida cubierta, errores y peor año.
- **Laboratorio de desempeño:** curvas ROC y de precisión, matrices de confusión, AUC año por año, calibración, modelo frente a calor, por estado y los diez modelos.

Necesita lo de `requirements-app.txt` (pandas, numpy, scikit-learn, plotly y streamlit). Si se quisiera publicar en Streamlit Community Cloud, el archivo principal es `app.py` y no hace falta ninguna clave.

## Fuentes de datos (`datos/crudos/`)

La fecha exacta de cada archivo está en `datos/crudos/registro_descargas.csv`.

| Archivo | Fuente | Enlace | Cobertura | Script |
|---|---|---|---|---|
| `eeuu/nass/nass_maiz_grano_{IA,IL,IN}_*.csv` | NASS Quick Stats, USDA (API; requiere una key gratuita en `NASS_API_KEY`) | [quickstats.nass.usda.gov/api](https://quickstats.nass.usda.gov/api) | Maíz para grano por condado (producción, área cosechada, rendimiento), 1981–2025 | `01` |
| `eeuu/nass_nuevos/` y `eeuu/censo_api/` | NASS Quick Stats, USDA (API) | Igual | Maíz de los siete estados nuevos, 1981–2025; área cosechada total y con riego de los censos 1997–2022 | `33` |
| `eeuu/rma/colsom_AAAA.zip` | RMA, USDA: Cause of Loss, *Summary of Business with Month* | [cause_of_loss](https://pubfs-rma.fpac.usda.gov/pub/Web_Data_Files/Summary_of_Business/cause_of_loss/) | Indemnización por condado, cultivo, causa y mes, 1989–2025 | `01` |
| `eeuu/rma/sobcov_AAAA.zip` | RMA, USDA: Summary of Business por estado, condado y cultivo, con nivel de cobertura | [state_county_crop](https://pubfs-rma.fpac.usda.gov/pub/Web_Data_Files/Summary_of_Business/state_county_crop/) | Responsabilidad (liability), primas e indemnizaciones totales, 1989–2025 | `01` |
| `eeuu/condados/cb_2023_us_county_500k.zip` | US Census Bureau, límites cartográficos de condados 2023 (1:500k) | [cb_2023_us_county_500k.zip](https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_500k.zip) | Polígonos con código FIPS (GEOID) | `01` |
| `eeuu/calendario/planting-10-29-2010.txt` | USDA NASS, *Usual Planting and Harvesting Dates for U.S. Field Crops* (oct-2010) | [esmis.nal.usda.gov](https://esmis.nal.usda.gov/concern/publications/vm40xr56k) | Fechas de siembra y cosecha por estado | `01` |
| `eeuu/chirps/chirps_mensual_eeuu_AAAA.nc` | CHIRPS v2.0 mensual (Climate Hazards Center, UCSB), recortado por la IRI Data Library | [IRI: UCSB CHIRPS v2p0 monthly](https://iridl.ldeo.columbia.edu/SOURCES/.UCSB/.CHIRPS/.v2p0/.monthly/.global/precipitation/) | Recuadro lon −97 a −84, lat 36,5 a 44, desde 1981; mm/mes a 0,05° (~5 km) | `01` (los siete estados nuevos, `33`) |
| `eeuu/nclimgrid_diario/{tmax,tmin}_AAAAMM.csv` | NOAA NCEI, nClimGrid-Daily: temperatura máxima y mínima diarias, promedio por condado (solo los diez estados) | [nclimgrid-daily/access/averages](https://www.ncei.noaa.gov/data/nclimgrid-daily/access/averages/) | Mayo a septiembre, 1981–2025. Ojo: el código de estado es el de NOAA, no el FIPS | `49` |
| `eeuu/noaa/climdiv-{tmaxcy,pdsicy}-*` | NOAA NCEI, nClimDiv: temperatura máxima e índice de sequía de Palmer mensuales por condado | [climdiv/monthly/current](https://www.ncei.noaa.gov/monitoring-content/data/us/climdiv/monthly/current/) | Todos los condados, 1895–2026 | `27` |
| `eeuu/precios/ers_feed_grains_yearbook.csv` | USDA ERS, Feed Grains Yearbook Tables (precio promedio recibido por los agricultores) | [feed-grains-yearbook-tables](https://www.ers.usda.gov/data-products/feed-grains-database/feed-grains-yearbook-tables) | Nacional, por campaña de septiembre a agosto | `27` |
| `eeuu/precios/cpi_u_bls.csv` | BLS, CPI-U de todos los artículos (CUUR0000SA0), API pública v1 | [api.bls.gov](https://api.bls.gov/publicAPI/v1/timeseries/data/) | Mensual, 1981–2025 | `27` |
| `oni/oni.ascii.txt` | Índice Oceánico El Niño (ONI), NOAA Climate Prediction Center | [oni.ascii.txt](https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt) | Trimestres móviles desde DJF 1950 | `01` |

**CHIRPS** no se bajó del servidor del CHC porque allí solo está el archivo global (7,8 GB en un NetCDF, o 163 MB por año). La IRI Data Library sirve el mismo producto recortado a un recuadro. La URL de cada año está en `registro_descargas.csv`.

## Datos procesados (`datos/procesados/`)

| Archivos | Script | Contenido |
|---|---|---|
| `chirps_mensual_condados_eeuu.csv`, `eeuu_ventanas_ciclo.csv`, `eeuu_lluvia_ciclo.csv`, `eeuu_calidad_condados.csv`, `eeuu_base_ciclos.csv` | 08 | Lluvia mensual de los 293 condados de IA, IL e IN; ciclo, filtros de calidad, tendencia y pérdida por condado y año |
| `eeuu_sequia_*` | 28 y 29 | Base del modelo, resultados, predicciones, calibración, SHAP y aporte del clima |
| `semaforo_condados.csv`, `eeuu_semaforo_*` | 30 | Semáforo de los tres estados y su prueba |
| `eeuu_impacto_*` | 31 | Pérdida real, RMA y seguro simulado en dólares de 2025 |
| `chirps_mensual_condados_nuevos.csv`, `eeuu_ciegas_*`, `eeuu_riego_censos.csv` | 34 | Base de los diez estados y riego de los censos (`eeuu_ciegas_base.csv` pesa más de 10 MB y no se sube; `eeuu_ciegas_app.csv` es la versión liviana del simulador) |
| `ciegas_resultados_*`, `ciegas_predicciones_*`, `ciegas_validacion_*`, `ciegas_criterio.json` | 35 | Prueba a ciegas del modelo |
| `ciegas_semaforo_*` | 36 | Semáforo en los diez estados |
| `ciegas_palmer_*` | 37 | Contrato Palmer |
| `ciegas_impacto_*` | 38 | Dólares en los diez estados y costo de operar |
| `cierre_ubicacion_*`, `cierre_calibracion_*`, `cierre_palmer_topes_*`, `cierre_causas_*`, `cierre_semaforo_*` | 40 a 44 | Resultados del cierre |
| `cinco_modelos_*` | 47 | Cinco modelos en los tres estados originales |
| `eeuu_grados_dia.csv` | 49 | Grados-día de 10 a 29 °C y por encima de 29 °C, y días de 35 °C, por condado y año |
| `final_*` | 50 | Comparación final a ciegas y elección del modelo |
| `exploratorio_c_*` | 52 | Grados-día frente a lo normal (exploratorio) |
| `modelo_final_predicciones.csv`, `modelo_final_dolares.csv`, `modelo_final_metricas.csv` | 53 | Predicciones del modelo final y dólares |
