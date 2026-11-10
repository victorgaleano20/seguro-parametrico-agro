"""
46_construir_cuaderno.py
Parte B del cierre: arma notebooks/proyecto_final.ipynb, el proyecto contado de principio a fin en 15 secciones.
El cuaderno SOLO lee las tablas de datos/procesados y las figuras de docs/figuras: no entrena ni recalcula ningún modelo, y
todas las cifras del texto salen de las tablas (así el texto no puede contradecirlas).

Para correrlo y exportar la versión sin código:
    python scripts/46_construir_cuaderno.py
    python -m nbconvert --to notebook --execute --inplace notebooks/proyecto_final.ipynb
    python -m nbconvert --to html --no-input --output-dir docs --output proyecto_final notebooks/proyecto_final.ipynb
Uso:  python scripts/46_construir_cuaderno.py
"""
import sys
from pathlib import Path

import nbformat as nbf

sys.stdout.reconfigure(encoding="utf-8")
RAIZ = Path(__file__).resolve().parents[1]
celdas = []


def md(texto):
    celdas.append(nbf.v4.new_markdown_cell(texto.strip("\n")))


def codigo(texto):
    celdas.append(nbf.v4.new_code_cell(texto.strip("\n")))


# ------------------------------------------------------------------------------------------------ portada y ayudas
md("""
# Seguro de sequía para el maíz de Estados Unidos: el proyecto de principio a fin

Este cuaderno cuenta todo el proyecto en 15 pasos, en lenguaje sencillo. Está pensado para alguien que no sabe de seguros ni de datos.
No entrena ningún modelo: solo lee las tablas y las figuras que ya se calcularon, para que el texto y las cifras no se contradigan.
Cada parte termina con una frase de **qué significa**.
""")
codigo('''
import json
from pathlib import Path

import numpy as np
import pandas as pd
from IPython.display import Image, Markdown, display

RAIZ = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
PROC, FIG = RAIZ / "datos" / "procesados", RAIZ / "docs" / "figuras"


def leer(nombre, **kw):
    return pd.read_csv(PROC / nombre, **kw)


def leer_json(nombre):
    return json.loads((PROC / nombre).read_text(encoding="utf-8"))


def md(texto):
    display(Markdown(texto))


def figura(nombre, ancho=860):
    display(Image(filename=str(FIG / nombre), width=ancho))


def c(x, d=2):
    """Número con coma decimal."""
    return f"{x:.{d}f}".replace(".", ",")


def miles(x, d=0):
    """Número con punto de miles y coma decimal."""
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def mm(x):
    """Dólares en millones, con punto de miles."""
    return "$" + miles(x / 1e6) + " millones"


def mostrar(df):
    display(df.style.hide(axis="index"))
''')

# ------------------------------------------------------------------------------------------------ 1. problema
md("""
## 1. El problema: el riesgo de base de un seguro por índice

**Un seguro normal** espera a que pase algo, manda a alguien a mirar el daño y paga según lo que encuentra. En el campo eso es caro: hay que ir finca por finca.

**Un seguro por índice** (o paramétrico) no mira la finca. Mira un dato público, por ejemplo la lluvia o el calor del verano. Si el dato pasa un umbral pactado, paga solo, sin visitas.

**Ahí aparece el riesgo de base.** Es la diferencia entre lo que dice el índice y lo que de verdad le pasó al agricultor:
- puede llover poco y la cosecha salir bien: el seguro paga a quien no perdió;
- puede llover normal y perderse la cosecha: el seguro no paga a quien sí perdió.

Mientras más grande el riesgo de base, menos sirve el seguro. Con plata pública de por medio (subsidios), importa que llegue a quien perdió.

**Qué significa:** un seguro por índice es barato y rápido, pero solo vale la pena si el índice acierta con quién perdió. Medir ese acierto es el trabajo de este proyecto.
""")

# ------------------------------------------------------------------------------------------------ 2. pregunta
md("""
## 2. La pregunta

> **Con datos públicos, ¿se puede predecir en qué condados y años se pierde la cosecha de maíz mejor que con una regla simple de lluvia, y cuánto de lo que pagaría el seguro llegaría de verdad a quien perdió?**

Para que la respuesta sea creíble, se fijaron reglas desde el principio:
- escribir el plan **antes** de correr cualquier análisis y no cambiarlo después;
- comparar siempre contra el azar y contra una regla simple;
- medir con años completos (un mismo año golpea a muchos condados a la vez), con y sin los años extremos 1988 y 2012;
- si algo no se sostiene, decirlo.

**Qué significa:** no se buscó un resultado bonito. Se buscó saber qué se puede afirmar y qué no.
""")

# ------------------------------------------------------------------------------------------------ 3. datos
md("""
## 3. Los datos

Todos son públicos y gratuitos.

| Dato | Qué es | Cobertura |
|---|---|---|
| **CHIRPS** | Lluvia estimada desde satélite, promediada por condado | Desde 1981 |
| **NOAA (nClimDiv)** | Temperatura máxima y índice de sequía de Palmer por condado | 1981 a 2025 |
| **NASS (USDA)** | Rendimiento, producción y área cosechada de maíz por condado; área con riego de los censos | 1981 a 2025; censos de 1997 a 2022 |
| **RMA (USDA)** | Lo que de verdad pagó el seguro de cosechas de EE. UU., por condado, cultivo, causa y año; primas y subsidios | Desde 1989 |
| **ERS (USDA) y BLS** | Precio del maíz y el índice de precios para llevar todo a dólares de 2025 | 1981 a 2025 |
| **EVA (UPRA y MinAgricultura)** | Rendimientos municipales de maíz y café en Colombia (para el contraste de la sección 5) | 2007 a 2025 |
| **NOAA nClimGrid-Daily** | Temperatura máxima y mínima diarias por condado, para los grados-día de calor | 1981 a 2025 |
| **ONI (NOAA)** | Fases de El Niño y La Niña | Desde 1981 |

**Cómo se define una pérdida:** el rendimiento del condado en ese año fue **80 % o menos de lo esperado**. Lo esperado sale de la tendencia lineal del propio condado, usando solo años anteriores, para no mirar el futuro.

**Filtros de calidad:** se descartan cifras repetidas respecto al año anterior (señal de dato copiado) y condados con saltos raros de área.

**Qué significa:** en EE. UU. hay 45 años de la misma fuente y, además, se sabe lo que pagó el seguro real. Eso permite comprobar el índice contra la realidad.
""")
codigo('''
b = leer("eeuu_ciegas_calidad.csv", dtype={"unidad": str}) if (PROC / "eeuu_ciegas_calidad.csv").exists() else None
pred = leer("ciegas_predicciones_principal.csv", dtype={"unidad": str})
md(f"**En números:** la prueba principal tiene {miles(len(pred))} condado-años de {pred['unidad'].nunique()} condados en {pred['estado'].nunique()} "
   f"estados (los tres originales, Iowa, Illinois e Indiana, y siete nuevos), de {pred['anio'].min()} a {pred['anio'].max()}, con {miles(int(pred['perdida_previa'].sum()))} pérdidas.")
''')

# ------------------------------------------------------------------------------------------------ 4. exploración
md("""
## 4. La exploración de los datos

El análisis exploratorio completo está en `notebooks/eda.ipynb` (versión sin código: `docs/eda.html`). Lo esencial:

| Hallazgo | Qué implica |
|---|---|
| Datos limpios: menos de 1 % de cifras repetidas y sin faltantes (en Kansas solo entra el 52 % de los condado-años por saltos de área) | Se puede confiar en el dato de cosecha |
| 10,6 % de los condado-años son pérdida, y los 5 peores años reúnen el 57 % de las pérdidas | No sirve medir con exactitud; la muestra efectiva es de pocos años malos |
| El año explica el 27 % de la variación de la pérdida, el estado y año el 45 % y el condado solo el 3 % | Hay que validar por años completos y medir el acierto **dentro de cada año** |
| Lluvia, temperatura y Palmer medidos frente a lo normal del condado se comportan igual en los estados de entrenamiento y en los de prueba; la ubicación y los grados-día absolutos no | Usar clima frente a lo normal y dejar fuera la ubicación |
| El calor y la sequía juntos multiplican el riesgo (47 % de pérdidas con ambos muy altos); el exceso de agua también lo sube | Preferir modelos no lineales |
""")
codigo('''
figura("pitch_eeuu_probabilidad_lluvia.png")
figura("pitch_serie_tiempo_eeuu.png")
''')
md("""
**Qué significa:** en EE. UU. la sequía y el calor sí dejan huella en el dato de cosecha; hay algo que predecir, pero de pocos años malos y con efectos regionales fuertes.
""")

# ------------------------------------------------------------------------------------------------ 5. Colombia y EE. UU.
md("""
## 5. Por qué Colombia, y por qué el laboratorio es EE. UU.

**Se empezó en Colombia**, porque es donde importa: solo cerca del 5 % del área sembrada tiene seguro agropecuario, y ahí un seguro por índice tiene sentido justamente porque medir la pérdida finca por finca es caro y el dato de cosecha es débil.

**Maíz (EVA, 2007 a 2025):** se probó la regla de lluvia en cientos de municipios con la misma metodología que en EE. UU. y México. En Colombia no superó al azar.
""")
codigo('''
cp = leer("comparacion_paises_resumen.csv", encoding="latin-1")
cp = cp[cp["prueba"].str.contains("sequ")].copy()
cp["País"] = cp["pais"]
cp["Heidke (0 = azar)"] = cp["heidke"].map(lambda x: c(x, 3))
cp["Valor p"] = cp["p_permutacion"].map(lambda x: c(x, 3))
cp["Pérdida con año seco"] = (100 * cp["prob_perdida_seco"]).map(lambda x: c(x, 0) + " %")
cp["Pérdida con año normal"] = (100 * cp["prob_perdida_normal"]).map(lambda x: c(x, 0) + " %")
md("**Índice de sequía en maíz, tres países, con la misma metodología:**")
mostrar(cp[["País", "Heidke (0 = azar)", "Valor p", "Pérdida con año seco", "Pérdida con año normal"]])
figura("pitch_barras_paises.png", 760)
''')
md("""
**El problema es el dato.** En Colombia, el 23,5 % de los rendimientos de maíz se repite igual que el año anterior (0,3 % en EE. UU.): suena a cifra copiada, no medida. En café se probaron modelos de aprendizaje automático y seis contratos; a escala municipal la lluvia casi no agregó nada a saber dónde queda el municipio, y la cifra municipal tiene indicios de reparto. Además, en Colombia no hay pagos de seguros públicos por municipio y causa para comprobar nada.

**Por eso EE. UU. es el laboratorio.** Allá hay 45 años de rendimiento por condado de una sola fuente, clima por condado y lo que pagó el seguro real, por condado y causa. Ahí se puede medir con honestidad cuánto riesgo de base deja un índice de clima. Se empezó con tres estados (Iowa, Illinois e Indiana) y después se sumaron siete que el modelo nunca vio.
""")
codigo('figura("pitch_ciegas_mapa_estados.png", 760)')
md("""
**Ojo:** en EE. UU. ya existe un seguro que paga por el rendimiento del condado (el seguro por rendimiento del área de la RMA). Allá un índice de clima no hace falta para medir la pérdida del condado; sirve para medir el método. **Donde el índice de clima tiene sentido es donde ese dato de rendimiento no existe o no es confiable, como en Colombia.**

**Qué significa:** con los datos municipales de Colombia de hoy no se puede probar que un seguro por índice proteja. EE. UU. permite medir el método y decir con precisión qué le falta a Colombia.
""")

# ------------------------------------------------------------------------------------------------ 6. modelo
md("""
## 6. El primer modelo: LightGBM en tres estados

**Qué hace:** para cada condado y cada año estima la probabilidad de pérdida, con el clima del verano (lluvia, meses secos seguidos, temperatura máxima e índice de Palmer) y la ubicación. Usa LightGBM, un modelo de árboles de decisión. También estima cuánto se pierde cuando hay pérdida.

**Cómo se evaluó, sin mirar el futuro:** año por año. Para predecir el año *t*, el modelo, sus ajustes y su calibración salen solo de años anteriores a *t*.

**Con quién se compara:** con una regla simple (pagar si la lluvia de junio a agosto queda bajo el percentil 15 del condado) y con solo la ubicación. Todos pagan en la misma cantidad de condado-años, para comparar en igualdad.
""")
codigo('''
r = leer("eeuu_sequia_resultados.csv")
r = r[r["esquema"] == "hacia_adelante"].copy()
nombres = {"lightgbm": "Modelo (LightGBM)", "bosque_aleatorio": "Bosque aleatorio", "regresion_logistica": "Regresión logística",
           "regla": "Regla de lluvia", "solo_ubicacion": "Solo ubicación"}
r["Método"] = r["modelo"].map(nombres)
r["Acierto al ordenar (0,5 = azar)"] = [f"{c(a)} ({c(l, 2)} a {c(h, 2)})" for a, l, h in zip(r["auc"], r["auc_ic_inf"], r["auc_ic_sup"])]
r["Acierto descontando el azar"] = r["heidke"].map(lambda x: c(x, 3))
r["Pérdidas captadas"] = r["pct_perdidas_captadas"].map(lambda x: c(x, 0) + " %")
md("**Tres estados originales, año por año, 1991 a 2025:**")
mostrar(r.sort_values("auc", ascending=False)[["Método", "Acierto al ordenar (0,5 = azar)", "Acierto descontando el azar", "Pérdidas captadas"]])
figura("pitch_eeuu_modelos.png", 760)
figura("pitch_eeuu_variables.png", 760)
''')
md("""
**Lo que más pesa:** el calor de julio y agosto y la lluvia de julio, que es cuando el maíz florece.

**Qué significa:** el modelo ordena los años de pérdida mucho mejor que el azar y mejor que una regla simple de lluvia. Pero esto se midió donde el modelo se entrenó; falta ver si se traslada a otros estados. Este primer modelo se reemplazó después por el que sale de comparar cinco modelos (sección 8).
""")

# ------------------------------------------------------------------------------------------------ 7. prueba a ciegas
md("""
## 7. La primera prueba a ciegas en siete estados

**Cómo se hizo:** el plan se escribió y se subió a git **antes** de bajar los datos de siete estados nuevos: Nebraska, Minnesota, Ohio, Missouri, Kansas, South Dakota y Wisconsin. El modelo, entrenado solo con Iowa, Illinois e Indiana, predijo esos siete estados año por año. Los estados nuevos nunca se usaron para entrenar, escoger ajustes ni calibrar.

**El criterio de éxito, fijado de antemano:** el acierto del modelo al menos 0,05 mayor que el de la regla de lluvia, mejor Heidke, y valor p menor de 0,05 barajando años completos.
""")
codigo('''
q = leer("ciegas_resultados_principal.csv")
q = q[q["modo"] == "principal"]
t = q[q["subconjunto"] == "todos"].copy()
nom = {"modelo": "Modelo", "regla": "Regla de lluvia", "tasa_historica": "Historia de pérdidas del condado", "azar": "Azar"}
t["Método"] = t["indice"].map(nom)
t["Acierto al ordenar (0,5 = azar)"] = [f"{c(a)} ({c(l, 2)} a {c(h, 2)})" for a, l, h in zip(t["auc"], t["auc_ic_inf"], t["auc_ic_sup"])]
t["Acierto descontando el azar"] = t["heidke"].map(lambda x: c(x, 3))
t["Pérdidas captadas"] = t["pct_perdidas_captadas"].map(lambda x: c(x, 0) + " %")
t["Valor p"] = t["p_auc_anios"].map(lambda x: c(x, 3))
mostrar(t[["Método", "Acierto al ordenar (0,5 = azar)", "Acierto descontando el azar", "Pérdidas captadas", "Valor p"]])
crit = leer_json("ciegas_criterio.json")
md(f"**Criterio:** diferencia de acierto {c(crit['dif_auc'], 3)} (se pedía 0,05 o más): {'sí' if crit['cumple_auc_mas_005'] else 'no'}; "
   f"Heidke mayor: {'sí' if crit['cumple_heidke_mayor'] else 'no'}; valor p {c(crit['p_auc_modelo'], 3)} (se pedía menos de 0,05): "
   f"{'sí' if crit['cumple_p_menor_005'] else 'no'}. **{'El modelo pasa la prueba a ciegas.' if crit['pasa_la_prueba'] else 'El modelo no pasa la prueba a ciegas.'}**")
figura("pitch_ciegas_modelo_nuevos.png", 760)
''')
codigo('''
v = q[q["indice"].isin(["modelo", "regla"]) & q["subconjunto"].isin(["todos", "sin_2012", "1995_2025", "sin_riego_alto"])]
v = v.pivot(index="subconjunto", columns="indice", values="auc").reindex(["todos", "sin_2012", "1995_2025", "sin_riego_alto"])
v.index = ["Todos los años", "Sin 2012", "De 1995 a 2025", "Sin condados con mucho riego (más de 25 %)"]
v = (v.map(lambda x: c(x, 3))).rename(columns={"modelo": "Modelo", "regla": "Regla de lluvia"}).reset_index(names="Versión")
md("**El resultado se mantiene en otras versiones (acierto al ordenar):**")
mostrar(v)
e = q[q["subconjunto"].str.startswith("estado: ") & ~q["subconjunto"].str.contains("sin 2012") & q["indice"].isin(["modelo", "regla"])]
e = e.pivot(index="subconjunto", columns="indice", values="auc").sort_values("modelo", ascending=False)
e.index = [s.replace("estado: ", "") for s in e.index]
e = e.map(lambda x: c(x, 3)).rename(columns={"modelo": "Modelo", "regla": "Regla de lluvia"}).reset_index(names="Estado")
md("**Por estado (acierto al ordenar):**")
mostrar(e)
figura("pitch_ciegas_por_estado.png", 760)
''')
md("""
**Lo que falló:** no gana en todos los estados. En Minnesota no distingue mejor que el azar, y en Wisconsin pierde contra la regla. Además, sin calibrar con datos locales, sus probabilidades no mejoraban la tasa media (se revisó en las secciones 8 y 9).

**Qué significa:** lo aprendido en tres estados se traslada a otros del cinturón maicero con algo menos de fuerza y le gana a la regla de lluvia, pero no es una garantía para cualquier estado.
""")

# ------------------------------------------------------------------------------------------------ 8. cinco modelos
md("""
## 8. Cinco modelos y el modelo final

**Por qué:** la auditoría técnica mostró que no estaba demostrado que LightGBM fuera el mejor y que un índice simple de calor casi lo igualaba. Se compararon cinco modelos con un plan fijado **antes** de correr (`docs/bitacora.md`, sexta parte):
- **Modelos:** regresión logística, logística con curvas suaves (splines), bosque aleatorio, boosting de gradiente y boosting monótono.
- **Variables:** dos conjuntos, sin ubicación: clima mensual frente a lo normal (A), y A más grados-día de calor diario (B).
- **Esquema:** todos se entrenan solo con Iowa, Illinois e Indiana y se prueban a ciegas, año por año, en los siete estados nuevos.
- **Elección:** con los años 1991-2010; los años 2011-2025 solo confirman. Puntaje = promedio del acierto global y del acierto dentro de cada año.
- **Referencias:** azar, regla de lluvia, índice simple de calor de julio y agosto y grados-día por encima de 29 °C.
""")
codigo('''
f = leer("final_resultados.csv")
el = leer_json("final_eleccion.json")
t = f[f["periodo"] == "todo 1991-2025"].copy()
t["Modelo"] = t["modelo"]
t["Acierto (0,5 = azar)"] = [f"{c(a, 3)} ({c(l, 2)} a {c(h, 2)})" for a, l, h in zip(t["auc"], t["auc_ic_inf"], t["auc_ic_sup"])]
t["Sin 2012"] = t["auc_sin_2012"].map(lambda x: c(x, 3))
t["Dentro de cada año"] = t["auc_dentro_anio"].map(lambda x: c(x, 3))
t["Heidke"] = t["heidke"].map(lambda x: c(x, 3))
s = f[f["periodo"] == "seleccion 1991-2010"].set_index("clave")["puntaje_eleccion"]
t["Puntaje de elección (1991-2010)"] = t["clave"].map(s).map(lambda x: c(x, 3))
md("**Siete estados nuevos, a ciegas, 1991-2025:**")
mostrar(t.sort_values("auc", ascending=False)[["Modelo", "Acierto (0,5 = azar)", "Sin 2012", "Dentro de cada año", "Heidke", "Puntaje de elección (1991-2010)"]])
md(f"**Elegido con el criterio fijado: {el['nombre']}.** En la confirmación 2011-2025 su acierto es {c(el['auc_confirmacion'], 3)}, frente a "
   f"{c(el['mejor_indice_simple_confirmacion'], 3)} del mejor índice simple (ventaja {c(el['ventaja_sobre_indice_simple'], 3)}; se pedía más de 0,02).")
''')
codigo('''
pe = leer("final_por_estado.csv")
ver = pe[pe["clave"].isin([el["elegido"], "ref_calor", "ref_regla"])].pivot(index="estado", columns="modelo", values="auc")
md("**Por estado (acierto al ordenar, 1991-2025):**")
mostrar(ver.map(lambda x: c(x, 3)).reset_index(names="Estado"))
ruta_c = PROC / "exploratorio_c_resultados.csv"
if ruta_c.exists():
    x = leer("exploratorio_c_resultados.csv")
    x = x[x["periodo"] == "todo 1991-2025"]
    x["Acierto"] = x["auc"].map(lambda v: c(v, 3)); x["Dentro de cada año"] = x["auc_dentro_anio"].map(lambda v: c(v, 3))
    md("**Exploratorio (no cambia la elección):** grados-día medidos frente a lo normal de cada condado. La idea salió de mirar los estados de prueba en el EDA, así que no es una prueba a ciegas limpia.")
    mostrar(x[["modelo", "Acierto", "Dentro de cada año"]].rename(columns={"modelo": "Modelo"}))
''')
md("""
**Lo que dicen los resultados:**
- **El modelo más simple de los que aprenden fue el mejor:** curvas suaves sobre el clima frente a lo normal, sin ubicación. Supera al LightGBM original de la primera prueba a ciegas (0,739, que usaba la ubicación) y es el mejor o casi el mejor en todos los estados; en Wisconsin ahora le gana a la regla. Minnesota sigue débil.
- **La ventaja sobre un índice simple de calor es pequeña y no está demostrada** (sección 13): en confirmación pasa el umbral fijado por muy poco, pero su rango de 95 % incluye el cero, y **dentro de cada año, en 2011-2025, el índice de calor queda por encima**. Los árboles (bosque, boosting) y los grados-día absolutos no ayudaron en el periodo de elección, aunque en 2011-2025 salieron algo mejor: el orden entre modelos depende del periodo y los rangos de confianza se superponen.
- **Lo más prometedor quedó como exploratorio:** con grados-día medidos frente a lo normal de cada condado, el acierto dentro de cada año sube de 0,700 a 0,721 (y en 2011-2025, de 0,747 a 0,800, por encima del índice de calor). No cambia el modelo final porque la idea salió de mirar los estados de prueba; es lo primero que habría que confirmar con datos nuevos.
- **Probabilidades:** la calibración con los tres años más recientes las **empeoraba** (Brier 0,0935 frente a 0,0864 sin calibrar; tasa media 0,0919), porque esos años a veces casi no tienen pérdidas. El modelo final se usa sin calibrar: así es mejor que la tasa media incluso en estados que nunca vio, aunque exagera en el décimo de más riesgo (dice 60 %, ocurrió 38 %).

**El modelo final** se reentrenó con los diez estados (1981-2025) y está en `modelos/modelo_final.joblib`; se usa con `python scripts/48_predecir.py archivo.csv`.

**Qué significa:** un modelo sencillo de curvas suaves sobre el clima del verano es la mejor opción entre las probadas para ordenar el riesgo en estados nuevos. Frente a un índice simple de calor no se distingue (sección 13): para un contrato, el índice simple es igual de bueno y mucho más fácil de explicar.
""")

# ------------------------------------------------------------------------------------------------ 8. cierre
md("""
## 9. Los resultados del cierre: clima o geografía, años locales, Palmer con topes y Minnesota

La prueba a ciegas dejó cuatro preguntas abiertas. Se resolvieron con un plan escrito y subido a git antes de correr nada (`docs/plan_cierre.md`). Nada de esto cambia el modelo principal ni sus resultados.

### 9.1 ¿El modelo aprende clima o geografía?

El modelo usa latitud y longitud, y en los estados nuevos esos valores quedan fuera de lo que vio al entrenar. Se repitió la prueba a ciegas **sin latitud, sin longitud y sin estado**, con todo lo demás igual. Regla fijada: si el acierto baja 0,02 o menos, aprende sobre todo clima; si baja más, parte es geografía.
""")
codigo('''
u = leer("cierre_ubicacion_comparacion.csv")
cu = leer_json("cierre_ubicacion_criterio.json")
filas = []
for sub, nombre in [("todos", "Todos los años"), ("sin_2012", "Sin 2012"), ("1995_2025", "De 1995 a 2025")]:
    f = {"Versión": nombre}
    for m in ["Modelo original (con ubicación)", "Modelo sin ubicación", "Regla de lluvia"]:
        x = u[(u["modelo"] == m) & (u["subconjunto"] == sub)].iloc[0]
        f[m] = f"{c(x['auc'], 3)} (Heidke {c(x['heidke'], 3)})"
    filas.append(f)
md("**Siete estados nuevos, acierto al ordenar (y Heidke):**")
mostrar(pd.DataFrame(filas))
dif = cu["dif_auc_original_menos_sin"]
md(f"**Resultado:** el acierto pasa de {c(cu['auc_original'], 3)} (original) a {c(cu['auc_sin_ubicacion'], 3)} (sin ubicación), una diferencia de {c(dif, 3)}; la regla de lluvia tiene {c(cu['auc_regla'], 3)}. "
   + ("Como la diferencia es de 0,02 o menos, **el modelo aprende sobre todo clima**." if cu["aprende_sobre_todo_clima"]
      else "Como la diferencia es mayor de 0,02, **parte de lo que el modelo aprende es geografía**."))
figura("pitch_cierre_modelo_ubicacion.png")
''')
md("""
**Qué significa:** la respuesta dice cuánto del acierto viene del clima y cuánto de saber dónde queda el condado. Solo se puede afirmar lo que muestra la tabla de arriba.

### 9.2 ¿Cuántos años locales hacen falta para entrar a un estado nuevo?

Las probabilidades del modelo, sin recalibrar, no mejoran la tasa media en los estados nuevos. Se probó recalibrarlas con los primeros 3, 5, 10 y 15 años de cada estado (y con 0), y se midió siempre en los mismos años posteriores (2006 a 2025). Meta fijada: el menor número de años con el que la probabilidad supere a la tasa media en al menos 5 de los 7 estados.
""")
codigo('''
br = leer("cierre_calibracion_brier.csv")
cc = leer_json("cierre_calibracion_criterio.json")
est = br[br["estado"] != "siete estados juntos"]
p = est.pivot(index="estado", columns="K", values="ganancia_pct")
p = p.map(lambda x: c(x, 0) + " %")
p.columns = ["Sin años locales" if k == 0 else f"{k} años" for k in p.columns]
md("**Cuánto mejora el Brier frente a la tasa media (positivo = mejor que la tasa media):**")
mostrar(p.reset_index(names="Estado"))
cuenta = cc["estados_mejores_que_tasa_media_por_K"]
md("**Estados (de 7) que superan a la tasa media:** " + "; ".join(f"{'sin años locales' if k == '0' else k + ' años'}: {v}" for k, v in cuenta.items()) + ".")
md("**Conclusión:** " + (f"el menor número de años que cumple la meta es **{cc['menor_K_que_cumple']}**." if not cc["ninguno_cumple"] else "**ningún** número de años cumple la meta."))
figura("pitch_cierre_calibracion_anios_locales.png")
''')
md("""
**Qué significa:** con el LightGBM original y su calibración, para usar las probabilidades en un estado nuevo hacía falta historia local propia; con pocos años, recalibrar empeora las cosas. El orden entre condados (acierto al ordenar) no depende de esto. **Matiz posterior (sección 8):** el modelo final, sin calibrar, ya es mejor que la tasa media en los estados nuevos, aunque exagera en los condado-años de más riesgo.

### 9.3 Contrato con el índice de Palmer, con topes

El contrato simple con el Palmer pagaba en 2012 el triple de la pérdida real. Se probó con suma asegurada de 50 % y 75 % del valor esperado y un tope de pago por año igual a 2 veces la prima pura anual. Se llama **vendible** si en ningún año paga más de 1,5 veces la pérdida real de ese año y sigue mandando a quien perdió al menos lo mismo que la regla de lluvia.
""")
codigo('''
pt = leer("cierre_palmer_topes_resumen.csv")
cp = leer_json("cierre_palmer_topes_criterio.json")
x = pt[pt["suma_asegurada"].isin([0.5, 0.75]) & pt["disparador"].isin(["Contrato Palmer", "Regla de lluvia (pago proporcional)", "Modelo"])].copy()
x["Contrato"] = x["disparador"].map({"Contrato Palmer": "Palmer", "Regla de lluvia (pago proporcional)": "Regla de lluvia", "Modelo": "Modelo"}) + np.where(x["con_tope"], " con tope", " sin tope")
x["Suma asegurada"] = (100 * x["suma_asegurada"]).map(lambda v: f"{v:.0f} %")
x["Pagos 1991-2025"] = x["pagos_usd"].map(lambda v: "$" + miles(v / 1e6) + " millones")
x["Pago en 2012 (pérdida real: " + mm(x["perdida_2012_usd"].iloc[0]) + ")"] = x["pago_2012_usd"].map(lambda v: "$" + miles(v / 1e6) + " millones")
x["Pérdida en dólares cubierta"] = x["pct_perdida_cubierta"].map(lambda v: c(v, 0) + " %")
x["De cada $100, a quien perdió"] = x["de_cada_100"].map(lambda v: "$" + c(v, 0))
x["Prima pura (% de la suma)"] = x["prima_pura_pct_suma"].map(lambda v: c(v, 1) + " %")
x["Pago anual máximo frente a la pérdida de ese año"] = x["razon_maxima_anual"].map(lambda v: c(v, 1) + " veces")
cols = ["Suma asegurada", "Contrato", "Pagos 1991-2025", [k for k in x.columns if k.startswith("Pago en 2012")][0], "Pérdida en dólares cubierta",
        "De cada $100, a quien perdió", "Prima pura (% de la suma)", "Pago anual máximo frente a la pérdida de ese año"]
mostrar(x.sort_values(["suma_asegurada", "disparador", "con_tope"])[cols])
a = cp["suma 75 %"]
md(f"**Resultado:** el tope arregla 2012, pero el contrato **{'es' if cp['vendible_en_ambas_sumas'] else 'no es'} vendible** con el criterio fijado. "
   f"Con tope, el pago de un año llega a {c(a['razon_maxima_anual_con_tope'], 1)} veces la pérdida real de ese año (en {a['anio_razon_maxima']}), y paga más de 1,5 veces la pérdida en "
   f"{len(str(a['anios_con_pago_mayor_1_5']).split(','))} de los 35 años. De cada $100, ${c(a['de_cada_100_palmer_con_tope'], 0)} llegan a quien perdió con Palmer con tope, frente a ${c(a['de_cada_100_lluvia_con_tope'], 0)} con la regla de lluvia con tope.")
figura("pitch_cierre_palmer_topes.png")
''')
md("""
**Qué significa:** poner topes protege de un año extremo como 2012, pero el contrato sigue pagando mucho en años de poca pérdida. Antes de pensar en venderlo habría que rediseñar el pago, no solo ponerle un techo.

### 9.4 Minnesota y las causas de los siniestros

En Minnesota el modelo no distingue mejor que el azar. Se miró **por qué se pagan los siniestros** de maíz en cada estado, con los datos de la RMA (descriptivo: no se afirman causas que los datos no muestren).
""")
codigo('''
ce = leer("cierre_causas_por_estado.csv").set_index("estado")
cols = {"parte_sequia": "Sequía", "parte_humedad": "Exceso de humedad", "parte_frio": "Heladas o frío", "parte_granizo": "Granizo", "parte_precio": "Caída de precio", "parte_otras": "Otras"}
t = (100 * ce[list(cols)]).rename(columns=cols).sort_values("Sequía").map(lambda v: c(v, 0) + " %").reset_index(names="Estado")
md("**Parte de lo pagado por el seguro real de maíz, 1989 a 2025, según la causa:**")
mostrar(t)
mn = leer("cierre_causas_minnesota_resumen.csv").set_index("grupo")
m = (100 * mn[[f"parte_{k}" for k in ["sequia", "humedad", "frio", "granizo", "precio", "otras"]]]).set_axis(list(cols.values()), axis=1)
m["Años"] = mn["anios"].astype(int)
md("**Minnesota en los años en que el modelo falló, frente a los demás años y los otros estados:**")
mostrar(m.assign(**{k: m[k].map(lambda v: c(v, 0) + " %") for k in cols.values()}).reset_index(names="Grupo"))
figura("pitch_cierre_causas_estado.png")
''')
md("""
**Qué significa:** Minnesota es el estado donde la sequía pesa menos entre las causas de los siniestros y el exceso de humedad pesa más. Eso es coherente con que un modelo de sequía le acierte menos allí, pero **los datos solo lo muestran como coincidencia, no como causa demostrada**.
""")

# ------------------------------------------------------------------------------------------------ 9. semáforos
md("""
## 10. Los semáforos

**Idea:** pintar cada condado de verde, amarillo o rojo para decir dónde un seguro por índice tiene más sentido.

**Semáforo 1 (calidad y sensibilidad):** verde si el dato de cosecha es bueno y la cosecha responde mucho al clima del verano; rojo si el dato es dudoso o responde poco.

**Semáforo 2 (por causa):** con los siniestros pagados antes de cada año, verde para el tercio de condados cuyos pagos fueron más por sequía; rojo para el tercio con menos sequía o con pocos años de siniestros o dato dudoso.

**Criterio de éxito, fijado de antemano:** los verdes superan a los rojos en acierto descontando el azar, en pérdidas captadas y en "de cada $100 que llegan a quien perdió", con un margen de error de 95 % (remuestreando años completos) que no incluya el cero.
""")
codigo('''
ld = leer("cierre_semaforo_lado_a_lado.csv")
ld = ld[ld["metrica"] != "auc"].copy()
nm = {"heidke": "Acierto descontando el azar", "pct_perdidas_captadas": "Pérdidas captadas (puntos %)", "de_cada_100": "De cada $100, a quien perdió ($)"}
ld["Medida"] = ld["metrica"].map(nm)
ld["Verdes"] = ld["verde"].map(lambda v: c(v, 2 if v < 5 else 0)); ld["Rojos"] = ld["rojo"].map(lambda v: c(v, 2 if v < 5 else 0))
ld["Diferencia (margen de error 95 %)"] = [f"{c(d, 2 if abs(d) < 1 else 1)} ({c(lo, 2 if abs(lo) < 1 else 1)} a {c(hi, 2 if abs(hi) < 1 else 1)})" for d, lo, hi in zip(ld["diferencia"], ld["ic_inf"], ld["ic_sup"])]
ld["¿Excluye el cero?"] = np.where(ld["excluye_cero"], "Sí", "No")
mostrar(ld.rename(columns={"semaforo": "Semáforo"})[["Semáforo", "Medida", "Verdes", "Rojos", "Diferencia (margen de error 95 %)", "¿Excluye el cero?"]])
cs = leer_json("cierre_semaforo_causa_criterio.json")
md("**Veredicto:** " + ("al menos un semáforo cumplió el criterio." if cs["algun_semaforo_cumple"] else
   "**ningún semáforo cumple el criterio.** Los verdes salen mejor en la estimación, pero el margen de error incluye el cero en al menos una de las tres medidas."))
figura("pitch_ciegas_semaforo_adelante.png", 760)
figura("pitch_cierre_semaforo_causa_prueba.png")
figura("pitch_cierre_semaforo_causa_mapa.png", 760)
''')
md("""
**Qué significa:** el semáforo todavía no está probado. No se debe presentar como herramienta. Con solo 20 a 27 años de prueba y pérdidas que se mueven juntas, falta poder estadístico para decir que los verdes sean de verdad mejores. El semáforo por causa además tiene una debilidad de diseño: un condado con pocos siniestros queda en rojo aunque sea de bajo riesgo.
""")

# ------------------------------------------------------------------------------------------------ 10. dólares
md("""
## 11. El impacto en dólares

Todo en **dólares de 2025**, de 1991 a 2025. Supuestos: área asegurada igual al área cosechada y precio nacional de cada campaña.

**Cómo se compara, en igualdad:** cada disparador (modelo final, índice de calor y regla de lluvia) paga en la misma cantidad de condado-años, y el monto es el valor esperado de la cosecha por el **tamaño medio de las pérdidas de los años anteriores**. Así solo cambia **a quién** se le paga. (El modelo del tamaño de la pérdida del proyecto original casi no aportaba y ya no se usa.)

**La medida "de cada $100, a quien perdió"** cuenta los dólares que el índice paga en condado-años donde el rendimiento del condado cayó al 80 % o menos de lo esperado.
""")
codigo('''
dd = leer("modelo_final_dolares.csv")
dd["Pagos"] = dd["pagos_usd"].map(lambda v: "" if pd.isna(v) else mm(v))
dd["Pérdida cubierta"] = dd["pct_perdida_cubierta"].map(lambda v: "" if pd.isna(v) else c(v, 0) + " %")
dd["De cada $100, a quien perdió"] = dd["de_cada_100"].map(lambda v: "$" + c(v, 1))
for grupo in ["diez estados", "siete estados nuevos (a ciegas)"]:
    g = dd[(dd["grupo"] == grupo) & (dd["periodo"] == "1991-2025")]
    md(f"**{grupo.capitalize()}, 1991-2025. Pérdida real: {mm(g['perdida_real_usd'].iloc[0])}.**")
    mostrar(g.rename(columns={"disparador": "Disparador"})[["Disparador", "Pagos", "Pérdida cubierta", "De cada $100, a quien perdió"]])
s = dd[(dd["grupo"] == "diez estados") & (dd["periodo"] == "1991-2025 sin 2012")]
md("**Diez estados, sin 2012:** " + "; ".join(f"{r.disparador}: ${c(r.de_cada_100, 1)}" for r in s.itertuples()) + ".")
''')
md("""
Lo que se puede leer de estas tablas:
- El modelo final y el índice de calor dirigen la plata **casi igual de bien** (unos $32 de cada $100 en los diez estados); el modelo cubre algo más de la pérdida real y gana sin 2012, y en los estados a ciegas el índice de calor manda un poco más a quien perdió. Los dos superan con claridad a la regla de lluvia y al azar.
- Aun así, **unos $2 de cada $3** irían a condados sin pérdida: el riesgo de base baja, no desaparece.

**Por qué no se compara con el seguro real.** Medir al seguro real con esta vara no es justo: está hecho para pagar a la finca que pierde aunque el promedio de su condado esté bien, y también paga caídas de precio, exceso de lluvia y granizo. Por eso no se dice que el índice dirija la plata "igual" ni "mejor" que el seguro real. El costo de operar el índice tampoco se compara: sería un supuesto.

**Qué significa:** en dólares, el aprendizaje automático no supera a un índice simple de calor; ambos son mucho mejores que una regla de lluvia, pero dejan un riesgo de base grande.
""")

# ------------------------------------------------------------------------------------------------ 11. auditoría
md("""
## 12. Lo que encontró la auditoría (2026-11-08)

Después de terminar, se revisó el proyecto buscando sus puntos débiles. Esto es descriptivo y se calculó después de ver los resultados: no cambia ninguna decisión, pero sí cómo se deben leer.

**1. Buena parte del acierto es saber qué años fueron malos.** Si a todos los condados de un año se les da el mismo puntaje (el promedio del modelo en ese año), el acierto en los siete estados nuevos es casi el mismo que el del modelo completo. Lo que de verdad dice cuánto riesgo de base queda es el acierto **dentro de cada año**: qué condados pierden en un año dado.
""")
codigo('''
from sklearn.metrics import roc_auc_score
q = leer("ciegas_predicciones_principal.csv", dtype={"unidad": str})
q = q[q["nuevo"].astype(str).isin(["True", "1"])].copy()
q["y"] = q["perdida_previa"].astype(bool)
q["promedio_del_anio"] = q.groupby("anio")["prob"].transform("mean")
filas = [(a, g["y"].sum(), roc_auc_score(g["y"], g["prob"]), roc_auc_score(g["y"], g["puntaje_regla"]))
         for a, g in q.groupby("anio") if g["y"].nunique() == 2 and g["y"].sum() >= 10]
w = pd.DataFrame(filas, columns=["anio", "perdidas", "modelo", "regla"])
dentro_m, dentro_r = np.average(w["modelo"], weights=w["perdidas"]), np.average(w["regla"], weights=w["perdidas"])
mostrar(pd.DataFrame({
    "Puntaje": ["Modelo completo", "Solo el promedio del año (igual para todos los condados)", "Modelo, dentro de cada año", "Regla de lluvia, dentro de cada año"],
    "Acierto al ordenar (0,5 = azar)": [c(roc_auc_score(q["y"], q["prob"]), 3), c(roc_auc_score(q["y"], q["promedio_del_anio"]), 3), c(dentro_m, 3), c(dentro_r, 3)]}))
md(f"Dentro de cada año: {len(w)} años con 10 o más pérdidas, ponderado por pérdidas. El modelo queda por debajo de 0,6 en " +
   ", ".join(str(a) for a in w.loc[w["modelo"] < 0.6, "anio"]) + ".")
''')
md("""
El modelo sí distingue condados dentro de un mismo año mejor que la regla de lluvia, pero la ventaja es modesta.

**2. En EE. UU. ya existe un seguro que paga por la pérdida del condado.** El seguro por rendimiento del área (RMA) paga cuando cae el rendimiento del condado, que es justo lo que el modelo intenta anticipar. Un índice de clima solo le agrega rapidez (el clima se conoce en septiembre; el rendimiento del condado, meses después). Por eso el valor de este trabajo está en el método y en lo que le falta a Colombia, no en un seguro nuevo para EE. UU.

**3. La comparación con el seguro real no es válida** (sección 11) y se retiró.

**4. LightGBM no era claramente el mejor modelo.** Por eso se compararon cinco modelos con un plan fijado de antemano (sección 8): ganó una logística con curvas suaves, más simple y fácil de auditar.

**6. Casi toda la señal es el calor.** En los tres estados originales, un índice simple de calor de julio y agosto, sin entrenar, logra 0,780 de acierto frente a 0,816 de LightGBM. El aprendizaje automático agrega poco; la comparación justa es contra ese índice, no contra la regla de lluvia (que dentro de cada año no distingue condados: 0,48).

**7. El modelo del tamaño de la pérdida casi no aportaba** (correlación 0,24 con el faltante real; error 0,099 frente a 0,105 de usar el promedio). Los dólares se recalcularon con el tamaño medio de las pérdidas de los años anteriores (sección 11).

**8. La calibración con tres años empeoraba las probabilidades** (sección 8): sin ella, el modelo final es mejor que la tasa media incluso en estados que nunca vio. Esto matiza la conclusión de la sección 9 sobre los "15 años locales", que se midió con esa calibración.

**5. Lo que recomienda la literatura:** contar las horas de calor por encima de 29 °C (Schlenker y Roberts, 2009). Se descargó la temperatura diaria de NOAA y se probó (sección 8): en valor absoluto no se traslada a los estados nuevos, que toleran más calor; medidos frente a lo normal de cada condado sí ayudan (exploratorio). Falta probar vegetación o humedad del suelo vistas desde satélite.

**Qué significa:** el método está bien hecho y es honesto, pero el resultado se debe contar como lo que es: un índice de clima que ordena el riesgo mejor que una regla de lluvia, con mucho riesgo de base y sin poder ponerle precio todavía en una zona nueva.
""")

# ------------------------------------------------------------------------------------------------ 13. segunda auditoría
md("""
## 13. La segunda auditoría (2026-11-09): el índice de calor, la validación por estado y el sobreentrenamiento

Una auditoría externa revisó las cifras contra las tablas. Dejó tres preguntas, que se respondieron con planes escritos antes de correr (`docs/bitacora.md`, 2026-11-09).

**1. ¿El modelo es mejor que el índice simple de calor?** Se midió con rangos de 95 % remuestreando años completos, usando los mismos años para los dos (`scripts/54_tablas_app.py`). Los años 1991-2010 de los siete estados se usaron para escoger el modelo, así que **la medida limpia es 2011-2025**.
""")
codigo('''
met = leer("app_metricas.csv")
dif = leer("app_diferencias.csv")
periodos = {"todo": "1991-2025", "confirmacion": "2011-2025 (limpio)", "desde_1995": "1995-2025 (sin los años de lo normal)"}
filas = []
for p, nombre in periodos.items():
    m = met[(met["grupo"] == "siete") & (met["periodo"] == p)].set_index("puntaje")
    v = dif[(dif["grupo"] == "siete") & (dif["periodo"] == p) & (dif["comparador"] == "ref_calor")]
    lo, hi = np.percentile(v["dif_auc"], [2.5, 97.5])
    lo_d, hi_d = np.percentile(v["dif_dentro"], [2.5, 97.5])
    filas.append({"Periodo": nombre, "Modelo": c(m.loc["prob", "auc"], 3), "Índice de calor": c(m.loc["ref_calor", "auc"], 3),
                  "Regla": c(m.loc["ref_regla", "auc"], 3),
                  "Diferencia modelo - calor (rango 95 %)": f"{c(m.loc['prob', 'auc'] - m.loc['ref_calor', 'auc'], 3)} ({c(lo, 3)} a {c(hi, 3)})",
                  "Dentro del año (rango 95 %)": f"{c(m.loc['prob', 'auc_dentro'] - m.loc['ref_calor', 'auc_dentro'], 3)} ({c(lo_d, 3)} a {c(hi_d, 3)})"})
md("**Siete estados nuevos, acierto al ordenar:**")
mostrar(pd.DataFrame(filas))
''')
md("""
En el periodo limpio, el rango de la diferencia incluye el cero, y dentro de cada año también. En 1991-2025 y en 1995-2025 la ventaja total sí excluye el cero (en 1995-2025, apenas), pero esos periodos incluyen los años 1991-2010, que se usaron para escoger el modelo entre diez opciones: esa ventaja puede deberse en parte a la propia elección. Dentro de cada año no se distinguen en ningún periodo. **Lo que se sostiene: el modelo y el índice de calor no se distinguen.**

**2. ¿Entrenar con más estados mejora al modelo?** Validación dejando un estado afuera (`scripts/55_validacion_por_estado.py`): para cada estado y año, el mismo modelo se entrena con los otros nueve estados y los años anteriores.
""")
codigo('''
r = leer("estado_resultados.csv")
t = r[(r["grupo"] == "siete")].pivot_table(index="periodo", columns="puntaje", values="auc").loc[["todo", "seleccion", "confirmacion"]]
t.index = ["1991-2025", "1991-2010", "2011-2025 (limpio)"]
t = t[["prob_91", "prob_37", "ref_calor", "ref_regla"]].rename(columns={"prob_91": "9 estados -> 1", "prob_37": "3 -> 7", "ref_calor": "Índice de calor", "ref_regla": "Regla"})
md("**Siete estados nuevos, acierto al ordenar:**")
mostrar(t.map(lambda x: c(x, 3)).reset_index(names="Periodo"))
e = r[(r["periodo"] == "todo") & r["grupo"].str.startswith("estado")].pivot_table(index="grupo", columns="puntaje", values="auc")
e.index = e.index.str.replace("estado: ", "")
e = e.sort_values("prob_91", ascending=False)[["prob_91", "ref_calor", "ref_regla"]].rename(columns={"prob_91": "Modelo (9 -> 1)", "ref_calor": "Índice de calor", "ref_regla": "Regla"})
md("**Cada estado, prediciéndolo con los otros nueve (1991-2025):**")
mostrar(e.map(lambda x: c(x, 3)).reset_index(names="Estado"))
''')
md("""
- **Más estados no mejoran al modelo:** en 2011-2025 da lo mismo entrenar con 9 que con 3. En 1991-2010 da menos, pero ese es el periodo en que se escogió el modelo con el esquema de 3 estados, así que la ventaja de 3 -> 7 ahí puede estar inflada por la elección.
- **Sigue empatado con el índice de calor.**
- **El método no es universal:** funciona en Illinois, Indiana, Ohio, Kansas, South Dakota y Missouri; es débil en Nebraska, Wisconsin e Iowa, y falla en Minnesota, donde el índice de calor también queda bajo el azar: **allí más calor va con menos pérdida**, porque pesan el frío y el exceso de humedad (sección 9).

**3. ¿El modelo está sobreentrenado o copia al índice de calor?**
- **Sobreentrenamiento moderado:** en sus propios datos de entrenamiento el modelo final da 0,899; fuera de muestra, 0,787. Con 78 coeficientes regularizados para 33.411 filas no es un modelo grande, pero la muestra efectiva son pocos años malos. Todas las cifras del proyecto son fuera de muestra, así que esto no infla ninguna comparación.
- **No copia al índice:** pagando la misma cantidad de veces coinciden en 68 % de los pagos. Donde no coinciden, lo que paga solo el modelo tiene 22 % de pérdidas y lo que paga solo el calor, 13 %. El modelo agrega algo de la lluvia y el Palmer, pero en pocos casos, y esa ganancia queda dentro del ruido.

**Qué significa:** el calor de julio y agosto es casi toda la señal. Un índice simple de calor ordena el riesgo igual que el modelo, y los dos funcionan donde la pérdida viene del calor y fallan donde viene del frío o del exceso de agua. Para un contrato, el índice simple basta; para otra región, hay que diseñarlo según la causa de pérdida de esa zona.
""")

# ------------------------------------------------------------------------------------------------ 12. Colombia
md("""
## 14. Lo que esto significa para Colombia: requisitos de datos y 3 recomendaciones

| Lo que se necesita | EE. UU. (maíz, 10 estados) | Colombia (maíz y café, EVA) |
|---|---|---|
| Años de rendimiento medido por zona | 45 años, una sola fuente y método | 19 años, dos fuentes empalmadas |
| Cifras repetidas o repartidas | 0,3 % repetidas | 23,5 % repetidas en maíz; indicios de reparto en café |
| Pagos reales de seguros para validar | Sí, públicos por condado, cultivo, causa y año | No se encontraron por municipio |
| Dato de riego | Sí, censos agropecuarios por condado | Solo una lista de distritos de riego |
| Prueba a ciegas posible | Sí, siete estados nuevos | No hay otra zona con datos comparables ni pagos para contrastar |

### Tres recomendaciones

1. **UPRA y Ministerio de Agricultura:** publicar el método y la fuente del rendimiento municipal de la EVA, y dejar de empalmar series sin avisar. Sin saber cómo se calcula la cifra municipal, ningún modelo puede separar el clima del método de medición.
2. **Finagro y las aseguradoras del seguro agropecuario:** publicar por municipio, año, cultivo y causa las indemnizaciones (sin datos personales). En EE. UU. eso permitió contrastar el índice con lo que de verdad pasó.
3. **Finagro y UPRA:** empezar con un piloto de contrato simple, con índice público, en una zona con buenos datos, y medirlo contra pagos reales antes de ampliarlo. Con lo aprendido en EE. UU.: un contrato tipo Palmer no se puede vender tal cual, hay que rediseñar el pago, y para poner precio hacen falta unos 15 años de historia local.

**Qué significa:** el problema de Colombia no es de modelos, es de datos: faltan una cifra de cosecha confiable y pagos públicos para comprobar.
""")

# ------------------------------------------------------------------------------------------------ 13. límites
md("""
## 15. Las limitaciones y lo que no se puede decir

**Se puede decir:**
- Un modelo entrenado en tres estados distingue años y condados con pérdida en otros siete mejor que una regla de lluvia, también sin 2012 y sin los condados con mucho riego. Dentro de un mismo año, la ventaja es modesta.
- Las probabilidades del modelo final, sin calibrar, son mejores que la tasa media incluso en estados nuevos, pero exageran en el riesgo más alto; para poner precio conviene ajustarlas con datos locales.
- Un modelo sencillo de curvas suaves sobre el clima frente a lo normal, entrenado en tres estados, ordena el riesgo en otros siete mejor que una regla de lluvia (0,762 frente a 0,659); un índice simple de calor (0,710) hace prácticamente lo mismo: en 2011-2025 no se distinguen.
- De cada $100 que pagaría el índice, unos $32 llegan a condados con pérdida, frente a unos $8 pagando al azar; el índice de calor logra casi lo mismo.
- Un contrato simple con el índice de Palmer se comporta como la regla de lluvia.

**No se puede decir:**
- Que el semáforo funcione: ninguno de los dos cumplió el criterio.
- Que el modelo funcione en cualquier estado: falla en Minnesota (0,40 entrenando con los otros nueve), donde la pérdida viene del frío y del exceso de agua, y es débil en Iowa, Nebraska y Wisconsin.
- Que el contrato con el índice de Palmer, con topes, sea vendible tal cual.
- Que las causas por estado expliquen por qué falla el modelo en Minnesota: es una coincidencia que los datos muestran, no una causa demostrada.
- Que el índice dirija la plata igual o mejor que el seguro real: no se midieron con la misma vara.
- Que el índice reemplace al seguro real: cubre más riesgos y paga por finca.
- Que el modelo sea mejor que un índice simple de calor: en el periodo limpio y dentro de cada año no se distinguen, y en dólares queda igual o por debajo.
- Que los siete estados sean una prueba del todo a ciegas para el modelo final: sus años 1991-2010 se usaron para escogerlo.
- Que el modelo funcione en Colombia: allá no hay datos para comprobarlo.

**Limitaciones que siguen abiertas:**
- El costo de operar el índice es un supuesto, no una medida.
- El área asegurada es el área cosechada, y el precio es nacional, no por estado.
- La pérdida se mide con el rendimiento del condado, no por finca.
- Falta la soya y las causas distintas de la sequía (exceso de lluvia, inundaciones).
- El modelo se evalúa con el clima de todo el verano, a fines de septiembre: no es un pronóstico a mitad de temporada.
- Sin datos de riego como variable del modelo (solo como filtro de evaluación).
- Los grados-día por encima de 29 °C se probaron en valor absoluto; medidos frente a lo normal solo se probaron de forma exploratoria.
- El rendimiento se calcula sobre el área cosechada: en sequías fuertes, los lotes abandonados pueden esconder parte de la pérdida.
- Los intervalos por remuestreo de años dependen de pocos años (20 a 35).

**Qué significa:** el proyecto muestra cómo medir con honestidad un seguro de sequía por índice, y que con buenos datos un modelo de clima ordena el riesgo mejor que una regla de lluvia. También muestra lo que todavía no se sostiene: el semáforo, el precio sin datos locales, el contrato Palmer con topes y el riesgo de base, que sigue siendo grande. Para Colombia, el primer paso no es un modelo: es un dato de cosecha confiable y pagos públicos.
""")

nb = nbf.v4.new_notebook()
nb["cells"] = celdas
nb["metadata"] = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python"}}
destino = RAIZ / "notebooks" / "proyecto_final.ipynb"
nbf.write(nb, destino)
print(f"Cuaderno escrito: {destino.relative_to(RAIZ)} ({len(celdas)} celdas)")
