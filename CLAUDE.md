# CLAUDE.md: seguro paramétrico de sequía para el maíz de EE. UU.

## Prioridad de trabajo (desde el 2026-11-08): primero lo técnico
**La prioridad es la parte técnica y de ciencia de datos: si los datos están bien, si el modelo predice y si es el adecuado.** Cómo se explica o se presenta va después, y solo con lo que la parte técnica sostenga.
- **Ser sincero, no complaciente.** Si algo no sirve o no se sostiene, decirlo claro, con la cifra. No suavizar resultados para que el proyecto se vea mejor.
- **Toda afirmación sobre el modelo se respalda con una comprobación**: contra el azar, contra la regla de lluvia y **contra el índice simple de calor de julio y agosto** (la comparación justa; ver abajo). Reportar siempre el AUC global, sin 2012 y **dentro de cada año**, con rangos de 95 % remuestreando años.
- Antes de proponer cómo contar algo, verificar que el número existe en las tablas y que mide lo que dice medir.

**Auditoría técnica (2026-11-08; detalle en `docs/bitacora.md`, tercera parte), tres estados originales, año por año 1991-2025:**
- **El modelo predice y no tiene fugas:** se reprodujo de forma independiente (misma etiqueta en el 100 % de las filas). Datos limpios: 0,3 % de repetidos, sin faltantes salvo el riego.
- **Casi toda la señal es el calor:** el índice simple de calor de julio y agosto, sin entrenar, da AUC 0,780 (dentro del año 0,631); LightGBM 0,816 (0,704); bosque aleatorio 0,834 (0,705). El aprendizaje automático agrega poco.
- **La regla de lluvia es una comparación débil:** dentro de cada año, 0,480 (azar). Palmer, 0,534.
- **El modelo del tamaño de la pérdida casi no aporta** (correlación 0,24; error 0,099 frente a 0,105 del promedio), y de él dependen los dólares que paga el índice.
- **Muestra efectiva pequeña:** cinco años (2012, 1991, 1993, 1995 y 2002) concentran el 74 % de las pérdidas; los rangos de 95 % del AUC van de unos 0,5-0,6 a 0,9.
- **Pendiente técnico:** repetir la comparación con el índice de calor en los siete estados nuevos (falta su base en este equipo); horas por encima de 29 °C (requiere temperatura diaria); pago ligado al índice en lugar del modelo de tamaño; efecto del abandono de lotes (falta área sembrada).

## Estado final (2026-11-05): proyecto terminado
**Seguro de sequía para el maíz de EE. UU.** (diez estados, 1991-2025). Entregables finales: `notebooks/proyecto_final.ipynb` (versión sin código: `docs/proyecto_final.html`), `docs/resumen_final.md` (una página), `docs/resultados_cierre.md`, `docs/resultados_prueba_ciegas.md` y el simulador `app.py` (listo para Streamlit Community Cloud; pasos en el README).

**Relato vigente (desde el 2026-11-08):** EE. UU. es el laboratorio donde se mide el método; Colombia es donde hace falta. En Colombia el dato de cosecha no permite medir la pérdida (23,5 % de maíz repetido) y no hay pagos públicos de seguros; en EE. UU. sí, pero allá ya existe un seguro que paga por el rendimiento del condado (seguro por rendimiento del área de la RMA), así que el índice de clima no es un producto nuevo para EE. UU. Requisitos y 3 recomendaciones para Colombia: `docs/requisitos_datos.md`.

**Repositorio (desde el 2026-11-08):** `github.com/victorgaleano20/seguro-parametrico-agro` (público), con historial limpio. El historial anterior (Colombia, México y café) está en el repositorio original `paulina0428/seguro-parametrico-maiz` (privado), commit `2789634`. **Al ser público: nunca subir claves, datos personales ni archivos de más de 10 MB.**

**Depuración (2026-11-08):** se retiraron los scripts y análisis de Colombia (maíz y café) y México: scripts `02`–`07` y `09`–`26`, sus documentos, cuadernos, figuras y tablas. Las funciones que el proyecto final usaba de esos scripts pasaron, sin cambios de lógica, a `scripts/comun.py`. Del análisis de Colombia solo se conservan, como evidencia, `docs/requisitos_datos.md`, `datos/procesados/comparacion_paises_resumen.csv` y `docs/figuras/pitch_barras_paises.png`. Todo lo retirado sigue en el repositorio original (commit `2789634`).

**Auditoría (2026-11-08), lo que cambia cómo se cuenta:**
- **La comparación "de cada $100" con el seguro real NO es válida** (el seguro real paga por finca y por otras causas). No decir que el índice dirige la plata igual o mejor que el seguro real.
- **Buena parte del acierto es saber qué años son malos:** el promedio del año solo da AUC 0,723 frente a 0,739 del modelo (siete estados nuevos). Dentro de cada año, modelo 0,708 y regla 0,650.
- **LightGBM no es claramente el mejor:** año por año, bosque 0,826 y LightGBM 0,816 con rangos que se superponen; en la prueba 2019-2025, la logística 0,902. No decir que es el mejor modelo posible.
- **Falta lo que recomienda la literatura:** horas de calor por encima de 29 °C (Schlenker y Roberts, 2009) y vegetación o humedad del suelo desde satélite.

**Cierre (plan congelado antes de correr: `docs/plan_cierre.md`; scripts `40` a `46`; figuras `docs/figuras/pitch_cierre_*.png`):**
- **¿Clima o geografía?** Sobre todo clima: sin latitud, longitud ni estado, AUC 0,734 frente a 0,739 (regla fijada: 0,02 o menos). El Heidke baja de 0,318 a 0,284.
- **Años locales:** 15. Es el menor K con el que 5 de 7 estados superan a la tasa media (2006-2025); con 10, 3 de 7; con 3 y 5, recalibrar empeora.
- **Contrato Palmer con topes (suma de 50 % y 75 %, tope de 2 veces la prima pura): NO es vendible.** El tope arregla 2012 pero paga más de 1,5 veces la pérdida real en 18 a 23 de 35 años (2025: $688 millones frente a una pérdida de $16 millones).
- **Minnesota:** la sequía es 26 % de lo pagado (la parte más baja de los diez estados) y el exceso de humedad 41 %; en los cuatro años de falla del modelo, la sequía fue 13 %. Descriptivo: coincidencia, no causa demostrada.
- **Semáforos:** ninguno se sostiene (ni el de `36` ni el de causa, `44`); los verdes salen mejor, pero el intervalo incluye el cero. El de causa tiene todo en rojo en 1999-2005 porque el filtro de calidad exige 25 años.

**Prueba a ciegas (2026-11-05), la medida más sólida** (plan congelado y subido a git antes de ver los datos: `docs/plan_prueba_ciegas.md`; resultados: `docs/resultados_prueba_ciegas.md`; scripts `33` a `39`):
- **Modelo congelado, entrenado solo con Iowa, Illinois e Indiana, aplicado año por año a Nebraska, Minnesota, Ohio, Missouri, Kansas, South Dakota y Wisconsin (506 condados, 1991–2025): PASA.** AUC 0,739 frente a 0,659 de la regla (+0,080), Heidke 0,318 frente a 0,218, valor p 0,001. Sin 2012: 0,709 frente a 0,620; sin condados con más de 25 % de riego: 0,769 frente a 0,677.
- **No en todos los estados:** Minnesota 0,46 (azar); en Wisconsin el modelo pierde en AUC contra la regla. **Sus probabilidades no están calibradas allá** (Brier 0,094 frente a 0,092 de la tasa media); con la variante secundaria sí (0,084).
- **Contrato Palmer (Palmer de julio y agosto bajo el percentil 15, pago proporcional hasta el percentil 2):** AUC 0,658 frente a 0,739 del modelo (diferencia 0,08 > 0,03): el modelo aporta algo más. Iguala a la regla de lluvia. En 2012 pagaría el triple de la pérdida real con suma de 100 %.
- **Dólares de 2025, diez estados, 1991–2025:** pérdida real $46.341 millones; de cada $100 que pagaría el índice, llegan a condados que perdieron: modelo $34, Palmer $38, azar $10 (en los siete estados nuevos solos, modelo $26). Las cifras del seguro real ($34; costo $51–$74 por cada $100 que llegan) están en las tablas, pero **no se comparan** con el índice. No decir que el índice reemplaza al seguro real.

**Modelo en los tres estados originales (detalle en `docs/resultados_modelo_eeuu.md` y `docs/impacto_economico_eeuu.md`):**
- LightGBM, el mejor en validación, registrado en MLflow como `perdida_maiz_eeuu`, alias `mejor_en_validacion`.
- Año por año, 1991–2025, AUC de 0,82 frente a 0,69 de la regla y 0,56 de solo ubicación. Sin 1988 ni 2012, 0,70 frente a 0,60.
- Pesan más el calor de julio y agosto y la lluvia de julio.
- La partición fija (prueba 2019–2025) tiene solo 14 pérdidas; no decide nada.

## Leer primero
1. `docs/historia_del_proyecto.md`: decisiones, razones y qué NO decir.
2. `docs/metodologia.md`: el modelo y las métricas, explicados sin tecnicismos.
3. `docs/bitacora.md`: qué se hizo en cada sesión, con su plan y sus resultados.

## Cómo correr
- Entorno con Python 3.12 y `pip install -r requirements.txt`, mejor fuera de carpetas sincronizadas como OneDrive y en una ruta corta. Los pasos están en el README.
- **Flujo:** `01` (descargas; requiere `NASS_API_KEY`), `08` (base de NASS), `27` a `32` (tres estados originales; `29` tarda unos 60 minutos), `33` a `39` (prueba a ciegas; `35` tarda unos 35 minutos), `40` a `45` (cierre) y `46` (cuaderno final; luego nbconvert, ver README).
- Funciones compartidas: `scripts/comun.py`. Pruebas: `python -m pytest tests`.
- Simulador: `streamlit run app.py`. MLflow: `mlflow ui --backend-store-uri sqlite:///mlflow.db`.
- Al cerrar cada sesión: `python scripts/empaquetar_contexto.py` (zip liviano para el chat asesor).
- **En Windows:** la librería C de NetCDF falla con rutas con tildes, por eso los NetCDF se leen con `engine="scipy"`.

## Reglas de trabajo
- **Escribir el plan en `docs/bitacora.md` ANTES de correr**, y no agregar variantes fuera del plan.
- **Comparar siempre contra el azar:** aciertos esperados, Heidke y valor p barajando años completos. No presentar unidades como "buenas" si no se sostienen.
- Python simple y legible, sin arquitectura de más. Reutilizar las funciones de `scripts/comun.py` para que la metodología sea idéntica.
- Comentarios y mensajes en español, sin emojis.
- **Honestidad:** el control de los tres estados originales ya se miró, así que todas las decisiones se toman con años hasta 2018; la medida principal es la validación año por año; los valores p se calculan barajando años completos, y siempre se reporta con y sin 1988 y 2012.
- **No inventar datos.** Si algo no existe o no se encuentra, se dice.
- Nunca escribir claves en archivos: la de NASS va solo en `NASS_API_KEY`.
- No descargar nada de más de 500 MB sin preguntar.
- Los planes congelados (`docs/plan_prueba_ciegas.md` y `docs/plan_cierre.md`) no se editan.

## Pendiente
El proyecto está terminado. Lo que sigue abierto son **limitaciones**, no tareas:
- **Soya** en los diez estados: no se hizo (era opcional).
- **Costo de operar el índice:** es un supuesto (5 %, 10 % y 20 % de lo que paga); para el seguro real se usó el reembolso de A&O del programa completo (GAO-17-501). Falta verificar si el A&O del maíz tiene una cifra propia.
- **Área asegurada** = área cosechada y **precio** nacional (ERS), no por estado.
- **Semáforo:** no se sostiene. Haría falta más años de prueba o un diseño nuevo, con plan previo.
- **Probabilidades en estados nuevos:** necesitan unos 15 años locales; Ohio y Minnesota no mejoran con ningún K.
- **Contrato Palmer:** rediseñar el pago (no solo ponerle tope) antes de pensar en venderlo.
- **Veranos muy lluviosos (1993):** el modelo de sequía no los ve; solo se midió sequía.
- **Minnesota:** la causa de que el modelo falle allí sigue sin probarse.
- **Presentación final (10 + 5 minutos):** la frase vigente está en `docs/historia_del_proyecto.md`, sección 7.
- **Mejoras posibles del modelo (no hechas):** horas de calor por encima de 29 °C, vegetación o humedad del suelo desde satélite, un modelo simple y monótono, y comparar contra un contrato por rendimiento del condado.
- **Área cosechada:** en sequías fuertes, los lotes abandonados pueden esconder parte de la pérdida; no se verificó.
