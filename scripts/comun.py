"""
comun.py
Funciones y constantes que comparten los scripts del seguro de sequía para el maíz de EE. UU.
Antes vivían en los scripts del análisis de Colombia, México y café (04, 05, 07, 09, 11, 19, 20 y 24), que se
retiraron del proyecto. Se copiaron sin cambiar la lógica, para que los resultados sean los mismos.

Uso desde otro script:  import comun
"""
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

# lightgbm, scikit-learn, xarray y shapely se importan dentro de las funciones que los usan,
# para que cada script solo exija las librerías que de verdad necesita.

RAIZ = Path(__file__).resolve().parents[1]
CRUDOS = RAIZ / "datos" / "crudos"
RMA = CRUDOS / "eeuu" / "rma"

SEMILLA = 2026
UMBRAL_PERDIDA = 0.8                 # pérdida si el rendimiento es <= 80 % del esperado por la tendencia
MIN_ANIOS_TENDENCIA = 10             # años válidos mínimos para ajustar la tendencia
SALTO_AREA_MAX = 5                   # cambio de nivel de área (veces) que excluye un condado
BU_ACRE_A_T_HA = 0.0254 / 0.404686   # 1 bushel de maíz = 25,4 kg; 1 acre = 0,404686 ha
UMBRAL_ONI = 0.5
MES_CENTRAL_ONI = {"DJF": 1, "JFM": 2, "FMA": 3, "MAM": 4, "AMJ": 5, "MJJ": 6,
                   "JJA": 7, "JAS": 8, "ASO": 9, "SON": 10, "OND": 11, "NDJ": 12}
ESTADOS_RMA = ["IA", "IL", "IN"]     # siglas que deja leer_rma; 38 lo cambia a los diez estados

# Colores de las figuras
SUPERFICIE, TINTA, TINTA_2, REJILLA = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"

# Modelos: rejillas de hiperparámetros y parámetros fijos
REJILLAS = {
    "regresion_logistica": [{"C": c} for c in (0.01, 0.1, 1.0)],
    "bosque_aleatorio": [{"max_depth": d, "min_samples_leaf": h} for d in (4, 8, 12) for h in (5, 20)],
    "lightgbm": [{"num_leaves": n, "min_child_samples": m} for n in (7, 15, 31) for m in (20, 50)]}
FIJOS_BOSQUE = {"n_estimators": 300, "n_jobs": -1, "random_state": SEMILLA}
FIJOS_LGBM = {"n_estimators": 300, "learning_rate": 0.03, "subsample": 0.8, "subsample_freq": 1,
              "colsample_bytree": 0.8, "random_state": SEMILLA, "verbose": -1, "n_jobs": -1}


# ---------------------------------------------------------------- lluvia CHIRPS por condado
def asignar_pixeles(poligonos, lon, lat, columna):
    """Devuelve la lista de índices de píxel (aplanados) de cada polígono (condado)."""
    import shapely

    lon2d, lat2d = np.meshgrid(lon, lat)
    lon_f, lat_f = lon2d.ravel(), lat2d.ravel()
    pixeles, sin_pixel = {}, []
    for cod, geom in zip(poligonos[columna], poligonos.geometry):
        xmin, ymin, xmax, ymax = geom.bounds
        # Primero se filtra por el recuadro del polígono (más rápido)
        cand = np.where((lon_f >= xmin) & (lon_f <= xmax) & (lat_f >= ymin) & (lat_f <= ymax))[0]
        dentro = cand[shapely.contains_xy(geom, lon_f[cand], lat_f[cand])]
        if len(dentro) == 0:
            p = geom.representative_point()
            dentro = np.array([np.argmin((lon_f - p.x) ** 2 + (lat_f - p.y) ** 2)])
            sin_pixel.append(cod)
        pixeles[cod] = dentro
    print(f"Píxeles asignados a {len(pixeles):,} condados "
          f"(mediana {int(np.median([len(v) for v in pixeles.values()]))} píxeles por condado)")
    if sin_pixel:
        print(f"AVISO: {len(sin_pixel)} condados sin centro de píxel adentro: se usó el píxel más cercano")
    return pixeles


def lluvia_mensual(poligonos, archivos, columna="GEOID", nombre_codigo="fips"):
    """Lluvia mensual promedio por polígono a partir de los NetCDF anuales de CHIRPS."""
    import xarray as xr

    pixeles, partes = None, []
    for archivo in archivos:
        # engine="scipy": la librería C de NetCDF en Windows falla con rutas con tildes
        with xr.open_dataset(archivo, engine="scipy", decode_times=False) as ds:
            if pixeles is None:
                pixeles = asignar_pixeles(poligonos, ds["X"].values, ds["Y"].values, columna)
            lluvia = ds["precipitation"].values.reshape(ds.sizes["T"], -1)  # (mes, píxel)
            meses = np.floor(ds["T"].values).astype(int)  # meses desde enero de 1960
        for cod, idx in pixeles.items():
            partes.append(pd.DataFrame({nombre_codigo: cod, "anio": 1960 + meses // 12,
                                        "mes": meses % 12 + 1,
                                        "lluvia_mm": np.nanmean(lluvia[:, idx], axis=1).round(1)}))
    return pd.concat(partes, ignore_index=True).sort_values([nombre_codigo, "anio", "mes"])


# ---------------------------------------------------------------- calidad del dato y tendencia
def salto_de_nivel(areas):
    """Mayor cambio de nivel: mediana después del corte vs. antes (mínimo 3 años de cada lado)."""
    a = areas.to_numpy()
    mayor = 1.0
    for k in range(3, len(a) - 2):
        r = np.median(a[k:]) / np.median(a[:k])
        mayor = max(mayor, r, 1 / r)
    return mayor


def tendencia_ciclos(v, claves, min_anios):
    """Tendencia lineal del rendimiento por grupo con todos los años; marca pérdida si rend <= 80 % del esperado.
    La usa 08 para eeuu_base_ciclos.csv."""
    partes = []
    for _, d in v.groupby(claves):
        if len(d) < min_anios:
            continue
        pendiente, intercepto = np.polyfit(d["anio"], d["rendimiento_t_ha"], 1)
        d = d.copy()
        d["rend_esperado_t_ha"] = intercepto + pendiente * d["anio"]
        partes.append(d[d["rend_esperado_t_ha"] > 0])
    t = pd.concat(partes, ignore_index=True)
    t["rend_relativo"] = t["rendimiento_t_ha"] / t["rend_esperado_t_ha"]
    t["perdida"] = t["rend_relativo"] <= UMBRAL_PERDIDA
    return t


def tendencia(d, fin=None, minimo=MIN_ANIOS_TENDENCIA):
    """Rendimiento relativo a la tendencia lineal de cada unidad, opcionalmente solo hasta el año fin."""
    filas = []
    for _, u in d.groupby("unidad"):
        ajuste = u if fin is None else u[u["anio"] <= fin]
        if len(ajuste) < minimo:
            continue
        pendiente, intercepto = np.polyfit(ajuste["anio"], ajuste["rendimiento_t_ha"], 1)
        esperado = intercepto + pendiente * u["anio"]
        filas.append(pd.DataFrame({"unidad": u["unidad"], "anio": u["anio"], "esperado": esperado.where(esperado > 0),
                                   "relativo": u["rendimiento_t_ha"] / esperado.where(esperado > 0)}))
    return pd.concat(filas, ignore_index=True).dropna()


def particion(anios):
    """Años ordenados: 15 % más reciente para prueba, 15 % anterior para validación y el resto para entrenar."""
    anios = sorted(anios)
    n_val = round(0.15 * len(anios))
    return anios[:-2 * n_val], anios[-2 * n_val:-n_val], anios[-n_val:]


# ---------------------------------------------------------------- El Niño (ONI)
def leer_oni():
    d = pd.read_csv(CRUDOS / "oni" / "oni.ascii.txt", sep=r"\s+")
    return pd.Series(d["ANOM"].to_numpy(), index=d["YR"] * 12 + d["SEAS"].map(MES_CENTRAL_ONI) - 1)


def fase_oni(oni):
    return np.select([oni >= UMBRAL_ONI, oni <= -UMBRAL_ONI], ["El Niño", "La Niña"], "Neutral")


# ---------------------------------------------------------------- siniestros de la RMA
def leer_rma(prefijo, columnas):
    """Lee los .zip anuales de la RMA (separados por |) y deja solo maíz (0041) de los estados de ESTADOS_RMA."""
    partes = []
    for archivo in sorted(RMA.glob(f"{prefijo}_*.zip")):
        with zipfile.ZipFile(archivo) as z:
            d = pd.read_csv(z.open(z.namelist()[0]), sep="|", header=None, dtype=str,
                            usecols=list(columnas))
        d = d.apply(lambda s: s.str.strip())
        d = d[d[2].isin(ESTADOS_RMA) & (d[5] == "0041")]
        partes.append(d.rename(columns=columnas))
    d = pd.concat(partes, ignore_index=True)
    d["fips"] = d["cod_estado"].str.zfill(2) + d["cod_condado"].str.zfill(3)
    d["anio"] = d["anio"].astype(int)
    return d


# ---------------------------------------------------------------- modelos y métricas
def crear(nombre, parametros, numericas, categoricas):
    """Regresión logística, bosque aleatorio o LightGBM, con imputación (y escala en la logística) de las numéricas
    y one-hot de las categóricas."""
    import lightgbm as lgb
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    if nombre == "regresion_logistica":
        final = LogisticRegression(max_iter=2000, **parametros)
    elif nombre == "bosque_aleatorio":
        final = RandomForestClassifier(**FIJOS_BOSQUE, **parametros)
    else:
        final = lgb.LGBMClassifier(**FIJOS_LGBM, **parametros)
    pasos = [SimpleImputer(strategy="median")] + ([StandardScaler()] if nombre == "regresion_logistica" else [])
    return make_pipeline(ColumnTransformer([("num", make_pipeline(*pasos), numericas),
                                            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categoricas)]),
                         final)


def heidke(perdida, pago):
    """Puntaje de Heidke: acierto por encima del que daría pagar al azar con la misma frecuencia."""
    a = int((perdida & pago).sum())
    b = int((~perdida & pago).sum())
    c = int((perdida & ~pago).sum())
    d = len(perdida) - a - b - c
    den = (a + c) * (c + d) + (a + b) * (b + d)
    return 2 * (a * d - b * c) / den if den else np.nan


def pagar_igual_que_regla(puntaje, frecuencia):
    """Corte que hace pagar con la misma frecuencia que la regla, en esos mismos años."""
    if frecuencia <= 0:
        return np.zeros(len(puntaje), dtype=bool)
    orden = np.argsort(-puntaje, kind="stable")
    pago = np.zeros(len(puntaje), dtype=bool)
    pago[orden[:int(round(frecuencia * len(puntaje)))]] = True
    return pago


# ---------------------------------------------------------------- figuras
def estilo(ax):
    ax.set_facecolor(SUPERFICIE)
    ax.grid(axis="y", color=REJILLA, linewidth=0.7, zorder=0)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(REJILLA)
    ax.tick_params(axis="both", length=0, colors=TINTA_2)
