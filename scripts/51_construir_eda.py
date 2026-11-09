"""
51_construir_eda.py
Arma notebooks/eda.ipynb: análisis exploratorio de los datos del seguro de sequía para el maíz de EE. UU.
(diez estados, 1981-2025). Solo lee tablas de datos/procesados; no entrena modelos.

Preguntas que responde:
  1. ¿Qué datos hay, de dónde salen y qué cubren?
  2. ¿Qué tan buenos son (faltantes, cifras repetidas, condados excluidos)?
  3. ¿Cómo se comporta la variable objetivo (pérdida) en el tiempo, por estado y según el umbral?
  4. ¿Se parecen los estados de la prueba a ciegas a los de entrenamiento (cambio de distribución)?
  5. ¿Qué variables se relacionan con la pérdida, por sí solas y dentro de cada año?
  6. ¿Qué variables dicen casi lo mismo (correlación)?
  7. ¿Cuánto de la pérdida es "el año" y cuánto "el condado"?
  8. ¿Qué implica todo esto para modelar?

Requiere 34 (eeuu_ciegas_base.csv) y 49 (eeuu_grados_dia.csv).
Para ejecutarlo y exportar la versión sin código:
    python scripts/51_construir_eda.py
    python -m nbconvert --to notebook --execute --inplace notebooks/eda.ipynb
    python -m nbconvert --to html --no-input --output-dir docs --output eda notebooks/eda.ipynb
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


# ------------------------------------------------------------------------------------------------ portada
md("""
# Análisis exploratorio: seguro de sequía para el maíz de EE. UU.

Este cuaderno revisa los datos **antes** de modelar: qué hay, qué tan buenos son, cómo se comporta la pérdida de cosecha
y qué variables se relacionan con ella. Cada sección termina con lo que implica para el modelo.

**Unidad de análisis:** un condado en un año. **Entrenamiento:** Iowa, Illinois e Indiana. **Prueba a ciegas:** Nebraska,
Minnesota, Ohio, Missouri, Kansas, South Dakota y Wisconsin.
""")
codigo('''
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from IPython.display import Markdown, display
from sklearn.metrics import roc_auc_score

RAIZ = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
PROC = RAIZ / "datos" / "procesados"

# Paleta (validada para daltonismo): azul = entrenamiento, naranja = prueba a ciegas; un solo tono para magnitudes
AZUL, NARANJA, SUPERFICIE, TINTA, TINTA_2, REJILLA = "#2a78d6", "#eb6834", "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
SECUENCIAL = plt.matplotlib.colors.LinearSegmentedColormap.from_list("azul", ["#cde2fb", "#86b6ef", "#2a78d6", "#1c5cab", "#0d366b"])
DIVERGENTE = plt.matplotlib.colors.LinearSegmentedColormap.from_list("div", ["#2a78d6", "#f0efec", "#eb6834"])
plt.rcParams.update({"figure.facecolor": SUPERFICIE, "axes.facecolor": SUPERFICIE, "axes.edgecolor": REJILLA,
                     "axes.labelcolor": TINTA_2, "xtick.color": TINTA_2, "ytick.color": TINTA_2, "axes.titlecolor": TINTA,
                     "axes.titlesize": 11, "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": REJILLA, "grid.linewidth": 0.6, "font.size": 9, "legend.frameon": False})

ORIGINALES = {"17", "18", "19"}
ESTADOS = {"17": "Illinois", "18": "Indiana", "19": "Iowa", "31": "Nebraska", "27": "Minnesota", "39": "Ohio",
           "29": "Missouri", "20": "Kansas", "46": "South Dakota", "55": "Wisconsin"}
ORDEN = ["Iowa", "Illinois", "Indiana", "Nebraska", "Minnesota", "Ohio", "Missouri", "Kansas", "South Dakota", "Wisconsin"]


def md(t):
    display(Markdown(t))


def c(x, d=2):
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(x, d=1):
    return c(100 * x, d) + " %"


def mostrar(df):
    display(df.style.hide(axis="index"))


b = pd.read_csv(PROC / "eeuu_ciegas_base.csv", dtype={"unidad": str, "grupo": str})
g = pd.read_csv(PROC / "eeuu_grados_dia.csv", dtype={"unidad": str})
b = b.merge(g, on=["unidad", "anio"], how="left")
b["estado"] = b["grupo"].map(ESTADOS)
b["conjunto"] = np.where(b["grupo"].isin(ORIGINALES), "Entrenamiento (3 estados)", "Prueba a ciegas (7 estados)")
b["perdida"] = b["perdida"].astype(bool)
md(f"**Base:** {c(len(b), 0)} condado-años, {b['unidad'].nunique()} condados, {b['anio'].min()}-{b['anio'].max()}.")
''')

# ------------------------------------------------------------------------------------------------ 1. datos
md("""
## 1. Los datos y de dónde salen

| Variable | Qué es | Unidad | Fuente |
|---|---|---|---|
| `rendimiento_t_ha` | Producción / área cosechada de maíz para grano | t/ha | NASS (USDA) |
| `rend_esperado_t_ha`, `rend_relativo` | Tendencia lineal del condado y rendimiento sobre esa tendencia | t/ha, proporción | Calculado |
| `perdida` | Rendimiento de 80 % o menos de lo esperado (**variable objetivo**) | sí / no | Calculado |
| `lluvia_may` … `lluvia_sep` | Lluvia del mes frente a lo normal del condado (1981-1994) | % de lo normal | CHIRPS (satélite) |
| `racha_meses_secos` | Mayor número de meses seguidos de mayo a septiembre con menos de 75 % de lo normal | meses | CHIRPS |
| `deficit_jul_ago` | Cuánto faltó de lluvia en julio y agosto frente a lo normal | % | CHIRPS |
| `tmax_jun` … `tmax_ago` | Temperatura máxima media del mes frente a lo normal | °C de diferencia | NOAA nClimDiv |
| `palmer_jun` … `palmer_ago` | Índice de sequía de Palmer (negativo = seco) | índice | NOAA nClimDiv |
| `gd_10_29_*` | Grados-día entre 10 y 29 °C (calor útil para el maíz) | °C·día | NOAA nClimGrid-Daily |
| `gd_29_*` | Grados-día por encima de 29 °C (calor dañino) | °C·día | NOAA nClimGrid-Daily |
| `dias_tmax_35_jun_ago` | Días de junio a agosto con máxima de 35 °C o más | días | NOAA nClimGrid-Daily |
| `latitud`, `longitud`, `grupo` | Ubicación del condado y estado | grados, FIPS | Census Bureau |

**Nota sobre la etiqueta de este cuaderno:** aquí `perdida` usa la tendencia ajustada con años hasta 2018 (la de la base). Los modelos usan una
versión más estricta, con la tendencia de los años anteriores a cada año que se predice; para describir los datos, las dos dicen casi lo mismo.
""")

# ------------------------------------------------------------------------------------------------ 2. cobertura
md("## 2. Cobertura: cuántos condados y años hay")
codigo('''
cob = b.groupby(["estado", "conjunto"]).agg(condados=("unidad", "nunique"), condado_anios=("anio", "size"),
                                            primer_anio=("anio", "min"), ultimo_anio=("anio", "max")).reset_index()
cob["estado"] = pd.Categorical(cob["estado"], ORDEN)
mostrar(cob.sort_values("estado").rename(columns={"estado": "Estado", "conjunto": "Conjunto", "condados": "Condados",
        "condado_anios": "Condado-años", "primer_anio": "Desde", "ultimo_anio": "Hasta"}))

por_anio = b.pivot_table(index="anio", columns="conjunto", values="unidad", aggfunc="nunique")
fig, ax = plt.subplots(figsize=(10, 3.2))
for col, color in zip(por_anio.columns, [AZUL, NARANJA]):
    ax.plot(por_anio.index, por_anio[col], color=color, lw=2, label=col)
ax.set_ylabel("Condados con dato")
ax.set_title("Condados con dato de cosecha válido, por año")
ax.legend(loc="lower left")
ax.set_ylim(0, None)
plt.show()
''')
md("{{INTERPRETACION_COBERTURA}}")

# ------------------------------------------------------------------------------------------------ 3. calidad
md("## 3. Calidad de los datos")
codigo('''
q = pd.read_csv(PROC / "eeuu_ciegas_calidad_anual.csv", dtype={"unidad": str})
q["estado"] = q["unidad"].str[:2].map(ESTADOS)
cal = q.groupby("estado").agg(con_dato=("anio", "size"), repetidos=("repetido", "sum")).reindex(ORDEN)
cal["% repetidos"] = (100 * cal["repetidos"] / cal["con_dato"]).round(2)
cal["en la base del modelo"] = b.groupby("estado").size().reindex(ORDEN)
cal["% que entra"] = (100 * cal["en la base del modelo"] / cal["con_dato"]).round(1)
mostrar(cal.reset_index().rename(columns={"estado": "Estado", "con_dato": "Condado-años con dato", "repetidos": "Repetidos"}))

vars_modelo = ["lluvia_may", "lluvia_jun", "lluvia_jul", "lluvia_ago", "lluvia_sep", "racha_meses_secos", "deficit_jul_ago",
               "tmax_jun", "tmax_jul", "tmax_ago", "palmer_jun", "palmer_jul", "palmer_ago",
               "gd_10_29_jun_ago", "gd_29_jun_ago", "dias_tmax_35_jun_ago"]
falt = b.groupby("estado")[vars_modelo].apply(lambda x: x.isna().mean() * 100).reindex(ORDEN)
falt = falt.loc[:, falt.max() > 0]
md("**Faltantes por variable y estado (% de condado-años; solo variables con algún faltante):**")
display(falt.round(2) if not falt.empty else Markdown("Ninguna variable del modelo tiene faltantes."))
''')
md("{{INTERPRETACION_CALIDAD}}")

# ------------------------------------------------------------------------------------------------ 4. rendimiento y tendencia
md("## 4. El rendimiento y su tendencia")
codigo('''
med = b.groupby(["anio", "conjunto"])["rendimiento_t_ha"].median().unstack()
fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 3.4))
for col, color in zip(med.columns, [AZUL, NARANJA]):
    a1.plot(med.index, med[col], color=color, lw=2, label=col)
a1.set_ylabel("Rendimiento mediano (t/ha)")
a1.set_title("El rendimiento sube con los años (tecnología)")
a1.legend(loc="upper left")
ejemplo = b[b["unidad"] == b.groupby("unidad").size().idxmax()].sort_values("anio")
a2.plot(ejemplo["anio"], ejemplo["rendimiento_t_ha"], "o", color=AZUL, ms=4, label="Rendimiento")
a2.plot(ejemplo["anio"], ejemplo["rend_esperado_t_ha"], color=TINTA_2, lw=1.5, label="Tendencia (esperado)")
a2.plot(ejemplo["anio"], 0.8 * ejemplo["rend_esperado_t_ha"], color=TINTA_2, lw=1, ls="--", label="80 % de lo esperado")
perd = ejemplo[ejemplo["perdida"]]
a2.plot(perd["anio"], perd["rendimiento_t_ha"], "o", color=NARANJA, ms=6, label="Pérdida")
a2.set_title(f"Ejemplo: {ejemplo['nombre'].iloc[0].title()}, {ejemplo['estado'].iloc[0]}")
a2.set_ylabel("t/ha")
a2.legend(loc="upper left", fontsize=7.5)
plt.tight_layout()
plt.show()

fig, ax = plt.subplots(figsize=(10, 3))
bins = np.linspace(0, 1.6, 65)
for conj, color in [("Entrenamiento (3 estados)", AZUL), ("Prueba a ciegas (7 estados)", NARANJA)]:
    ax.hist(b.loc[b["conjunto"] == conj, "rend_relativo"].clip(0, 1.6), bins=bins, density=True, histtype="step", lw=2, color=color, label=conj)
ax.axvline(0.8, color=TINTA, lw=1, ls="--")
ax.text(0.79, ax.get_ylim()[1] * 0.9, "umbral de pérdida (80 %)", ha="right", fontsize=8, color=TINTA)
ax.set_xlabel("Rendimiento sobre lo esperado")
ax.set_ylabel("Densidad")
ax.set_title("Distribución del rendimiento relativo: la cola izquierda son las pérdidas")
ax.legend(loc="upper left")
plt.show()
mostrar(b.groupby("conjunto")["rend_relativo"].describe(percentiles=[0.01, 0.05, 0.5, 0.95]).round(3).reset_index())
''')
md("{{INTERPRETACION_TENDENCIA}}")

# ------------------------------------------------------------------------------------------------ 5. objetivo
md("## 5. La variable objetivo: la pérdida de cosecha")
codigo('''
tasa = b.pivot_table(index="estado", columns="anio", values="perdida", aggfunc="mean").reindex(ORDEN)
fig, ax = plt.subplots(figsize=(12, 3.6))
im = ax.imshow(tasa.to_numpy(), aspect="auto", cmap=SECUENCIAL, vmin=0, vmax=1)
ax.set_yticks(range(len(tasa)), tasa.index)
ax.set_xticks(range(0, tasa.shape[1], 3), tasa.columns[::3])
ax.grid(False)
ax.axhline(2.5, color=TINTA, lw=1.5)
ax.set_title("Parte de los condados con pérdida, por estado y año (más oscuro = más condados perdieron)")
fig.colorbar(im, ax=ax, fraction=0.02, pad=0.01, format=lambda v, _: f"{v:.0%}")
plt.show()

resumen = b.groupby("conjunto").agg(condado_anios=("perdida", "size"), perdidas=("perdida", "sum"), tasa=("perdida", "mean")).reset_index()
resumen["tasa"] = resumen["tasa"].map(pct)
mostrar(resumen.rename(columns={"conjunto": "Conjunto", "condado_anios": "Condado-años", "perdidas": "Pérdidas", "tasa": "Tasa de pérdida"}))

por_anio = b.groupby("anio")["perdida"].sum().sort_values(ascending=False)
acum = por_anio.cumsum() / por_anio.sum()
top5 = acum.iloc[4]
fig, ax = plt.subplots(figsize=(10, 3))
ax.bar(range(1, len(acum) + 1), 100 * acum.to_numpy(), color=AZUL, width=0.8)
ax.set_xlabel("Número de años (del que más pérdidas tuvo al que menos)")
ax.set_ylabel("% acumulado de pérdidas")
ax.set_title("Las pérdidas se concentran en pocos años")
for i in range(5):
    ax.text(i + 1, 100 * acum.iloc[i] + 2, str(acum.index[i]), ha="center", fontsize=7, rotation=90, color=TINTA)
ax.set_ylim(0, 110)
plt.show()
md(f"Los 5 años con más pérdidas ({', '.join(map(str, acum.index[:5]))}) reúnen el **{pct(top5, 0)}** de todas las pérdidas de los diez estados.")

umb = []
for u in [0.7, 0.8, 0.9]:
    y = b["rend_relativo"] <= u
    umb.append({"Umbral": f"{int(u * 100)} % de lo esperado", "Tasa de pérdida": pct(y.mean()), "Pérdidas": int(y.sum()),
                "Años con 10 % o más de condados con pérdida": int((y.groupby(b["anio"]).mean() >= 0.10).sum())})
md("**Sensibilidad al umbral de pérdida:**")
mostrar(pd.DataFrame(umb))
''')
md("{{INTERPRETACION_OBJETIVO}}")

# ------------------------------------------------------------------------------------------------ 6. año vs condado
md("## 6. ¿Cuánto de la pérdida es el año y cuánto el condado?")
codigo('''
y = b["perdida"].astype(float)
total = ((y - y.mean()) ** 2).sum()
media_anio = b.groupby("anio")["perdida"].transform("mean")
media_condado = b.groupby("unidad")["perdida"].transform("mean")
media_estado_anio = b.groupby(["grupo", "anio"])["perdida"].transform("mean")
var = pd.DataFrame({"Agrupación": ["Año (igual para todos los condados)", "Estado y año", "Condado (igual todos los años)"],
                    "Parte de la variación explicada": [((media_anio - y.mean()) ** 2).sum() / total,
                                                        ((media_estado_anio - y.mean()) ** 2).sum() / total,
                                                        ((media_condado - y.mean()) ** 2).sum() / total]})
var["Parte de la variación explicada"] = var["Parte de la variación explicada"].map(pct)
mostrar(var)
''')
md("{{INTERPRETACION_ANIO}}")

# ------------------------------------------------------------------------------------------------ 7. cambio de distribución
md("## 7. ¿Se parecen los estados de la prueba a ciegas a los de entrenamiento?")
codigo('''
clave = ["lluvia_jul", "lluvia_ago", "deficit_jul_ago", "tmax_jul", "tmax_ago", "palmer_jul", "palmer_ago",
         "gd_10_29_jun_ago", "gd_29_jun_ago", "dias_tmax_35_jun_ago", "latitud", "longitud"]
tr, ci = b[b["grupo"].isin(ORIGINALES)], b[~b["grupo"].isin(ORIGINALES)]
filas = []
for v in clave:
    a, z = tr[v].dropna(), ci[v].dropna()
    dif = (z.mean() - a.mean()) / np.sqrt((a.var() + z.var()) / 2)
    fuera = ((z < a.quantile(0.005)) | (z > a.quantile(0.995))).mean()
    filas.append({"Variable": v, "Media entrenamiento": c(a.mean()), "Media prueba a ciegas": c(z.mean()),
                  "Diferencia estandarizada": c(dif), "% fuera del rango de entrenamiento": pct(fuera)})
mostrar(pd.DataFrame(filas))

fig, ejes = plt.subplots(2, 3, figsize=(12, 5.4))
for ax, v in zip(ejes.ravel(), ["deficit_jul_ago", "tmax_jul", "palmer_jul", "gd_10_29_jun_ago", "gd_29_jun_ago", "dias_tmax_35_jun_ago"]):
    lo, hi = b[v].quantile([0.005, 0.995])
    bins = np.linspace(lo, hi, 40)
    for d, color, nombre in [(tr, AZUL, "Entrenamiento"), (ci, NARANJA, "Prueba a ciegas")]:
        ax.hist(d[v].clip(lo, hi), bins=bins, density=True, histtype="step", lw=2, color=color, label=nombre)
    ax.set_title(v, fontsize=9.5)
    ax.set_yticks([])
ejes[0, 0].legend(loc="upper right", fontsize=7.5)
fig.suptitle("Distribución de variables clave: entrenamiento frente a prueba a ciegas", x=0.01, ha="left", color=TINTA)
plt.tight_layout()
plt.show()
''')
md("{{INTERPRETACION_CAMBIO}}")

# ------------------------------------------------------------------------------------------------ 8. relación con la pérdida
md("""
## 8. ¿Qué variables se relacionan con la pérdida?

Para cada variable se mide su capacidad de ordenar por sí sola (AUC, con el signo que más riesgo da) en dos versiones:
**global** (mezcla años malos y buenos) y **dentro de cada año** (qué condados pierden en un mismo año; años con 10 o más pérdidas,
ponderado por pérdidas). La segunda es la que importa para el riesgo de base.
""")
codigo('''
def auc_signo(y, x):
    m = x.notna()
    a = roc_auc_score(y[m], x[m])
    return max(a, 1 - a), ("+" if a >= 0.5 else "−")


def auc_dentro(d, v, signo):
    w = []
    for _, gg in d.groupby("anio"):
        m = gg[v].notna()
        if gg.loc[m, "perdida"].nunique() == 2 and gg.loc[m, "perdida"].sum() >= 10:
            a = roc_auc_score(gg.loc[m, "perdida"], gg.loc[m, v] if signo == "+" else -gg.loc[m, v])
            w.append((gg.loc[m, "perdida"].sum(), a))
    return np.average([a for _, a in w], weights=[n for n, _ in w]) if w else np.nan


todas = vars_modelo + ["gd_29_jul", "gd_29_ago", "latitud", "longitud"]
filas = []
for v in todas:
    a, s = auc_signo(b["perdida"], b[v])
    filas.append({"Variable": v, "Más riesgo cuando": "sube" if s == "+" else "baja", "AUC global": a,
                  "AUC dentro del año (10 estados)": auc_dentro(b, v, s),
                  "AUC dentro del año (prueba a ciegas)": auc_dentro(ci, v, s)})
uni = pd.DataFrame(filas).sort_values("AUC dentro del año (10 estados)", ascending=False)
mostrar(uni.round(3))
''')
codigo('''
fig, ejes = plt.subplots(2, 3, figsize=(12, 5.6), sharey=True)
for ax, v in zip(ejes.ravel(), ["deficit_jul_ago", "tmax_jul", "palmer_jul", "gd_29_jun_ago", "dias_tmax_35_jun_ago", "lluvia_jul"]):
    for d, color, nombre in [(tr, AZUL, "Entrenamiento"), (ci, NARANJA, "Prueba a ciegas")]:
        dd = d[[v, "perdida"]].dropna()
        cortes = pd.qcut(dd[v].rank(method="first"), 10, labels=False)
        r = dd.groupby(cortes).agg(x=(v, "median"), y=("perdida", "mean"))
        ax.plot(r["x"], 100 * r["y"], "o-", color=color, lw=2, ms=4, label=nombre)
    ax.set_title(v, fontsize=9.5)
ejes[0, 0].set_ylabel("% con pérdida")
ejes[1, 0].set_ylabel("% con pérdida")
ejes[0, 0].legend(loc="upper left", fontsize=7.5)
fig.suptitle("Tasa de pérdida por décimos de cada variable", x=0.01, ha="left", color=TINTA)
plt.tight_layout()
plt.show()
''')
md("{{INTERPRETACION_RELACION}}")

# ------------------------------------------------------------------------------------------------ 9. interacción
md("## 9. Calor y sequía juntos")
codigo('''
dd = b[["gd_29_jun_ago", "palmer_jul", "perdida"]].dropna().copy()
dd["calor"] = pd.qcut(dd["gd_29_jun_ago"].rank(method="first"), 5, labels=["muy bajo", "bajo", "medio", "alto", "muy alto"])
dd["sequia"] = pd.qcut((-dd["palmer_jul"]).rank(method="first"), 5, labels=["muy húmedo", "húmedo", "normal", "seco", "muy seco"])
t2 = dd.pivot_table(index="sequia", columns="calor", values="perdida", aggfunc="mean", observed=False)
n2 = dd.pivot_table(index="sequia", columns="calor", values="perdida", aggfunc="size", observed=False)
fig, ax = plt.subplots(figsize=(7, 4))
im = ax.imshow(t2.to_numpy(), cmap=SECUENCIAL, vmin=0, vmax=max(0.5, np.nanmax(t2.to_numpy())), origin="lower")
ax.set_xticks(range(5), t2.columns)
ax.set_yticks(range(5), t2.index)
ax.set_xlabel("Grados-día por encima de 29 °C (quintiles)")
ax.set_ylabel("Palmer de julio (quintiles)")
ax.grid(False)
for i in range(5):
    for j in range(5):
        v = t2.iloc[i, j]
        ax.text(j, i, f"{v:.0%}\\n(n={n2.iloc[i, j]})", ha="center", va="center", fontsize=7, color="white" if v > 0.3 else TINTA)
ax.set_title("Tasa de pérdida según calor y sequía")
plt.show()
''')
md("{{INTERPRETACION_INTERACCION}}")

# ------------------------------------------------------------------------------------------------ 10. correlación
md("## 10. Variables que dicen casi lo mismo")
codigo('''
corr = b[vars_modelo].corr(method="spearman")
fig, ax = plt.subplots(figsize=(9, 7.5))
im = ax.imshow(corr.to_numpy(), cmap=DIVERGENTE, vmin=-1, vmax=1)
ax.set_xticks(range(len(corr)), corr.columns, rotation=90)
ax.set_yticks(range(len(corr)), corr.index)
ax.grid(False)
fig.colorbar(im, ax=ax, fraction=0.04)
ax.set_title("Correlación de Spearman entre variables del modelo")
plt.show()
pares = corr.where(np.triu(np.ones(corr.shape, dtype=bool), 1)).stack().rename("rho").reset_index()
pares["|rho|"] = pares["rho"].abs()
md("**Pares más correlacionados:**")
mostrar(pares.sort_values("|rho|", ascending=False).head(10).round(3).rename(columns={"level_0": "Variable 1", "level_1": "Variable 2"}))
''')
md("{{INTERPRETACION_CORRELACION}}")

# ------------------------------------------------------------------------------------------------ 11. mapas
md("## 11. Dónde se pierde la cosecha")
codigo('''
mapa = b.groupby("unidad").agg(lat=("latitud", "first"), lon=("longitud", "first"), tasa=("perdida", "mean"),
                               calor=("gd_29_jun_ago", "mean"), conjunto=("conjunto", "first"))
fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.2))
s1 = a1.scatter(mapa["lon"], mapa["lat"], c=mapa["tasa"], cmap=SECUENCIAL, s=9, vmin=0, vmax=mapa["tasa"].quantile(0.98))
a1.set_title("Tasa de pérdida por condado, 1981-2025")
fig.colorbar(s1, ax=a1, fraction=0.03, format=lambda v, _: f"{v:.0%}")
s2 = a2.scatter(mapa["lon"], mapa["lat"], c=mapa["calor"], cmap=SECUENCIAL, s=9)
a2.set_title("Grados-día por encima de 29 °C, promedio de junio a agosto")
fig.colorbar(s2, ax=a2, fraction=0.03)
for ax in (a1, a2):
    ax.set_aspect(1.3)
    ax.grid(False)
    ax.set_xlabel("Longitud")
    ax.set_ylabel("Latitud")
plt.tight_layout()
plt.show()
''')
md("{{INTERPRETACION_MAPAS}}")

# ------------------------------------------------------------------------------------------------ 12. riego
md("## 12. El riego")
codigo('''
r = pd.read_csv(PROC / "eeuu_riego_censos.csv", dtype={"unidad": str})
rr = r.groupby("unidad")["fraccion"].mean().rename("riego")
mm = b.groupby("unidad").agg(tasa=("perdida", "mean"), estado=("estado", "first")).join(rr)
mostrar(mm.groupby("estado")["riego"].describe()[["count", "mean", "50%", "max"]].reindex(ORDEN).round(3).reset_index()
        .rename(columns={"estado": "Estado", "count": "Condados con censo", "mean": "Riego medio", "50%": "Mediana", "max": "Máximo"}))
mm["grupo_riego"] = pd.cut(mm["riego"], [-0.01, 0.05, 0.25, 1], labels=["menos de 5 %", "5 a 25 %", "más de 25 %"])
t = mm.groupby("grupo_riego", observed=False).agg(condados=("tasa", "size"), tasa_perdida=("tasa", "mean")).reset_index()
t["tasa_perdida"] = t["tasa_perdida"].map(pct)
mostrar(t.rename(columns={"grupo_riego": "Maíz con riego", "condados": "Condados", "tasa_perdida": "Tasa media de pérdida"}))
''')
md("{{INTERPRETACION_RIEGO}}")

# ------------------------------------------------------------------------------------------------ 13. conclusiones
md("## 13. Qué implica para el modelo")
md("{{CONCLUSIONES}}")

nb = nbf.v4.new_notebook()
nb["cells"] = celdas
nb["metadata"] = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python"}}
destino = RAIZ / "notebooks" / "eda.ipynb"
nbf.write(nb, destino)
print(f"Cuaderno escrito: {destino.relative_to(RAIZ)} ({len(celdas)} celdas)")
