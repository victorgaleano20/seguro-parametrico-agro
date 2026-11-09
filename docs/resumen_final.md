# Resumen final: seguro de sequía para el maíz de EE. UU.

**El problema.** Un seguro por índice paga solo, mirando un dato público (lluvia, calor). Su debilidad es el riesgo de base: puede pagar a quien no perdió y no pagar a quien sí. Con plata pública de por medio, importa que llegue a quien perdió. El maíz de EE. UU. permite probarlo: hay 45 años de rendimiento por condado, clima por condado y lo que de verdad pagó el seguro.

**Por qué EE. UU.** Allá se puede medir el método: hay rendimiento por condado de 45 años y pagos reales del seguro. En EE. UU. ya existe un seguro que paga por el rendimiento del condado, así que el índice de clima no es un producto nuevo para allá; sirve para medir el método y para decir qué necesita un país como Colombia, donde ese dato no es confiable.

**Qué hicimos.** Un modelo (LightGBM) que estima la probabilidad y el tamaño de la pérdida por condado, con clima del verano. Se evaluó año por año sin mirar el futuro; se probó a ciegas en siete estados que nunca vio (plan congelado antes de ver los datos); se cerraron cuatro preguntas abiertas; se midió el impacto en dólares de 2025 y se dejó un simulador. Todo está en `notebooks/proyecto_final.ipynb` (versión sin código: `docs/proyecto_final.html`).

## Los 5 resultados principales

1. **El modelo pasa la prueba a ciegas.** En siete estados nuevos, acierto al ordenar 0,739 frente a 0,659 de la regla de lluvia (azar: 0,5); valor p 0,001. Gana en 6 de 7 estados.
2. **Aprende sobre todo clima, no geografía.** Sin latitud, longitud ni estado, el acierto es 0,734 (baja 0,005).
3. **Sus probabilidades necesitan unos 15 años locales.** Con 15 años de historia propia, 5 de 7 estados superan a la tasa media; con 10, solo 3; con 3 o 5, recalibrar empeora.
4. **En dólares (diez estados, 1991-2025, dólares de 2025):** pérdida real de $46.341 millones. De cada $100 que pagaría el índice con el modelo, $34 llegan a condados que perdieron y $66 a condados sin pérdida; pagando al azar serían $10. No se compara con el seguro real: este paga por finca y por otras causas (precio, exceso de lluvia), así que medirlo con la pérdida del condado no es justo.
5. **El contrato Palmer con topes no es vendible** (paga más de 1,5 veces la pérdida real en 18 a 23 de 35 años) y **ningún semáforo se sostiene** (los verdes salen mejor, pero el margen de error incluye el cero).

## Lo que se puede decir
- Un modelo entrenado en tres estados distingue las pérdidas en otros siete mejor que una regla de lluvia, también sin 2012 y sin los condados con mucho riego.
- Lo que se traslada entre estados es la relación entre clima y pérdida.
- En Minnesota la sequía pesa menos entre las causas de los siniestros (26 % frente a 36-56 % en los demás estados), lo que encaja con que allí el modelo no acierte; es una coincidencia, no una causa demostrada.

## Lo que encontró la auditoría (2026-11-08)
- **Buena parte del acierto es saber qué años fueron malos:** dando a todos los condados de un año el mismo puntaje, el acierto es 0,723 (el modelo, 0,739). Dentro de un mismo año, el modelo distingue condados con 0,708 frente a 0,650 de la regla: mejor, pero poco.
- **LightGBM no es claramente el mejor:** el bosque aleatorio y la regresión logística quedaron muy cerca.
- **Falta lo que recomienda la literatura:** horas de calor por encima de 29 °C y vegetación o humedad del suelo desde satélite.

## Lo que no se puede decir
- Que el semáforo funcione, que el modelo sirva en Minnesota o en cualquier estado sin recalibrar, ni que el contrato Palmer con topes sea vendible.
- Que el índice dirija la plata igual o mejor que el seguro real: no se midieron con la misma vara.
- Que el índice reemplace al seguro real: este cubre más riesgos (precio, exceso de lluvia) y paga por finca.
- Que el modelo funcione en Colombia: allá no hay datos para comprobarlo.

## Tres recomendaciones para Colombia
Detalle: `docs/requisitos_datos.md`.
1. **UPRA y Ministerio de Agricultura:** publicar el método y la fuente del rendimiento municipal de la EVA (23,5 % de maíz repetido frente a 0,3 % en EE. UU.) y dejar de empalmar series sin avisar.
2. **Finagro y las aseguradoras:** publicar por municipio, año, cultivo y causa las indemnizaciones del seguro agropecuario, sin datos personales.
3. **Finagro y UPRA:** empezar con un piloto de contrato simple, con índice público, en una zona con buenos datos, y medirlo contra pagos reales antes de ampliarlo. Rediseñar el pago antes: un Palmer con tope no es vendible tal cual.
