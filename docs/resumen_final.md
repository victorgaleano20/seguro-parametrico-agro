# Resumen final: seguro de sequía para el maíz de EE. UU.

**El problema.** Un seguro por índice paga solo, mirando un dato público (lluvia, calor). Su debilidad es el **riesgo de base**: puede pagar a quien no perdió y no pagar a quien sí. Con plata pública de por medio, importa que llegue a quien perdió.

**Por qué EE. UU.** En Colombia el dato de cosecha municipal no permite medir la pérdida (23,5 % de cifras de maíz repetidas) y no hay pagos públicos de seguros. EE. UU. sirve de laboratorio: 45 años de rendimiento por condado, clima por condado y pagos reales del seguro. Allá ya existe un seguro que paga por el rendimiento del condado, así que el índice de clima no es un producto nuevo para EE. UU.: se mide el método y se aprende qué necesita Colombia.

**Qué hicimos.**
1. **Análisis exploratorio** de 33.411 condado-años en 10 estados (`docs/eda.html`).
2. **Cinco modelos** (logística, logística con splines, bosque aleatorio, boosting y boosting monótono), con y sin grados-día de calor diario, entrenados con 3 estados y **probados a ciegas en 7**, con el criterio de elección fijado antes de correr.
3. **Impacto en dólares de 2025** y un **simulador**.

Todo está en `notebooks/proyecto_final.ipynb` (sin código: `docs/proyecto_final.html`).

## Los resultados principales
1. **El modelo final** es una logística con curvas suaves sobre el clima del verano medido frente a lo normal de cada condado, sin ubicación. En 7 estados que no usó para entrenar, ordena el riesgo con **AUC 0,762** (azar 0,50; sin 2012, 0,738), frente a **0,659 de la regla de lluvia**. Sus años 1991-2010 se usaron para escoger el modelo; en 2011-2025, el periodo limpio, da **0,856** frente a 0,786 de la regla.
2. **Frente a un índice simple de calor de julio y agosto, no se distinguen:** en 2011-2025, +0,021 de AUC con rango de 95 % de −0,009 a +0,086, y dentro de cada año −0,017. Entrenando con 9 estados en lugar de 3 el resultado no cambia (0,858 frente a 0,856).
3. **El modelo más simple generalizó mejor:** las curvas suaves superaron al bosque, al boosting y al LightGBM original (0,739). Casi toda la señal está en el calor y la falta de agua de julio y agosto.
4. **Probabilidades:** sin calibrar son mejores que la tasa media incluso en estados nuevos (Brier 0,086 frente a 0,092), aunque exageran en el riesgo más alto. La calibración con 3 años que usaba el proyecto las empeoraba.
5. **En dólares (diez estados, 1991-2025):** de cada $100 que pagaría el índice, llegan a condados con pérdida **$31,7 con el modelo y $32,4 con el índice de calor**, frente a $25,8 con la regla y $8,4 al azar. El modelo no supera al índice simple en dólares, y unos $2 de cada $3 van a condados sin pérdida.

## Lo que se puede decir
- Con buenos datos, un modelo sencillo de clima ordena el riesgo de pérdida en estados que no usó para entrenar mejor que una regla de lluvia, y un índice simple de calor hace prácticamente lo mismo.
- El índice funciona donde la pérdida viene del calor y la sequía (Illinois 0,91 fuera de su estado; Ohio, Kansas, Missouri) y falla donde viene del frío o del exceso de agua (Minnesota 0,40).
- Lo que se traslada entre estados es el clima medido frente a lo normal de cada condado, no la ubicación ni el calor en valor absoluto.
- Los grados-día de calor medidos frente a lo normal mejoran el acierto dentro de cada año (0,721 frente a 0,700), pero es un resultado exploratorio que hay que confirmar con datos nuevos.

## Lo que no se puede decir
- Que el modelo sea mejor que un índice simple de calor: no se distingue en el periodo limpio ni dentro de cada año, y en dólares queda igual o por debajo.
- Que el semáforo funcione, que el modelo sirva en Minnesota (0,56) o que el contrato Palmer con topes sea vendible.
- Que el índice dirija la plata igual o mejor que el seguro real: no se midieron con la misma vara.
- Que el índice reemplace al seguro real, que cubre más riesgos (precio, exceso de lluvia) y paga por finca.
- Que el modelo funcione en Colombia: allá no hay datos para comprobarlo.

## Tres recomendaciones para Colombia
Detalle: `docs/requisitos_datos.md`.
1. **UPRA y Ministerio de Agricultura:** publicar el método y la fuente del rendimiento municipal de la EVA (23,5 % de maíz repetido frente a 0,3 % en EE. UU.) y dejar de empalmar series sin avisar.
2. **Finagro y las aseguradoras:** publicar por municipio, año, cultivo y causa las indemnizaciones del seguro agropecuario, sin datos personales.
3. **Finagro y UPRA:** empezar con un piloto de contrato simple, con un índice público de calor y sequía frente a lo normal, en una zona con buenos datos, y medirlo contra pagos reales antes de ampliarlo.
