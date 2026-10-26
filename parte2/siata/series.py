"""Tarea B: preprocesamiento, particiones de origen móvil, modelos, métricas e intervalos.

Todo pronóstico hecho en el origen T usa solo datos con fecha <= T. Las pruebas de
tests/test_series.py lo verifican cambiando los datos posteriores a T y comprobando que el pronóstico no cambia.

Dos series por variable:
- objetivo: la serie limpia (solo datos con bandera buena). Contra ella se evalúa; nunca tiene imputados.
- entrada: la misma con los huecos cortos interpolados. Solo alimenta los modelos.
"""
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from statsmodels.tsa.exponential_smoothing.ets import ETSModel
from statsmodels.tsa.statespace.sarimax import SARIMAX

from .calidad import BUENO, SOSPECHOSO, geometria_solar
from .datos import DIR_SALIDAS, ESTACIONES, agregar

UMBRAL_LLUVIA = 0.254  # mm en la hora: al menos una vuelta del balancín de p1
ALFAS = {80: 0.2, 95: 0.05}
# Árboles pequeños y 100 iteraciones: el notebook completo debe correr en menos de 15 min.
# Sin early stopping: evita la partición aleatoria de validación que haría por dentro.
PARAMS_HGB = dict(max_iter=100, learning_rate=0.1, max_leaf_nodes=15, min_samples_leaf=40,
                  early_stopping=False, random_state=0)


# ---------------------------------------------------------------- B1. Preprocesamiento

def serie_horaria(columna):
    """Columna de horario.parquet (medias o sumas de datos con bandera buena) recortada a su periodo con dato."""
    s = pd.read_parquet(DIR_SALIDAS / "horario.parquet")[columna]
    return s.loc[s.first_valid_index():s.last_valid_index()].asfreq("h")


def lluvia_10min():
    """Lluvia p1 de la 35 en bloques de 10 min, con el mismo criterio de horario.parquet: datos buenos y
    sospechosos (el desacuerdo entre balancines no invalida un aguacero), suma con cobertura 0,9."""
    m = pd.read_parquet(DIR_SALIDAS / "minutal_35.parquet", columns=["p1", "b_p1"])
    return agregar(m["p1"].where(m["b_p1"] <= SOSPECHOSO), "p1", "10min", 0.9).asfreq("10min").rename("lluvia")


def nivel_10min():
    """Nivel de la 803 en bloques de 10 min: media de minutos con bandera buena (cobertura 0,75), redondeo a 0,1 cm."""
    m = pd.read_parquet(DIR_SALIDAS / "minutal_803.parquet")
    limpio = m["nivel"].where(m["b_nivel"] == BUENO).round(1)  # viene en float32 (2,700012)
    return agregar(limpio, "nivel", "10min", 0.75).asfreq("10min").rename("nivel")


def huecos(s):
    """Tabla de huecos: inicio, fin y número de pasos sin dato."""
    na = s.isna()
    grupo = (na != na.shift()).cumsum()
    g = pd.DataFrame({"fecha": s.index, "na": na.to_numpy(), "grupo": grupo.to_numpy()})
    g = g[g["na"]].groupby("grupo")["fecha"].agg(["min", "max", "size"])
    return g.rename(columns={"min": "inicio", "max": "fin", "size": "pasos"}).reset_index(drop=True)


def rellenar_cortos(s, max_pasos):
    """Interpola (en el tiempo) solo los huecos de hasta max_pasos con dato a ambos lados.

    Devuelve (entrada, imputado). Los huecos largos y los de los extremos quedan en NaN.
    """
    na = s.isna()
    grupo = (na != na.shift()).cumsum()
    largo = na.groupby(grupo).transform("size")
    corto = na & (largo <= max_pasos)
    entrada = s.where(~corto, s.interpolate(method="time", limit_area="inside"))
    return entrada, corto & entrada.notna()


def radiacion_extraterrestre(indice, codigo="6004"):
    """Media de la irradiancia extraterrestre horizontal (W/m²) en cada intervalo del índice. Solo depende del reloj."""
    paso = indice.freq
    minutos = pd.date_range(indice[0], indice[-1] + paso - pd.Timedelta("1min"), freq="min")
    e = ESTACIONES[codigo]
    sol = geometria_solar(minutos, e["lat"], e["lon"])
    g0 = (sol["sa"] * sol["cos_z"].clip(lower=0)).resample(paso).mean()
    return g0.reindex(indice).rename("g0")


# ---------------------------------------------------------------- Particiones de origen móvil

def origenes(objetivo, horizonte, n, cada):
    """n orígenes separados `cada` pasos, el último a `horizonte` pasos del final.

    Solo se conservan los orígenes con dato observado en el propio origen: así ningún valor interpolado que
    se use como entrada pudo haber tomado información de después del origen.
    """
    paso = objetivo.index.freq
    fin = objetivo.last_valid_index() - horizonte * paso
    candidatos = pd.date_range(end=fin, periods=n, freq=cada * paso)
    return candidatos[objetivo.reindex(candidatos).notna().to_numpy()]


def escala_mase(objetivo, origen, m):
    """MAE de la ingenua de periodo m dentro del entrenamiento (datos <= origen)."""
    y = objetivo.loc[:origen]
    return float((y - y.shift(m)).abs().mean())


# ---------------------------------------------------------------- Variables para el modelo de aprendizaje automático

def matriz_directa(entrada, objetivo, horizonte, rezagos, periodo, exog=None, futuras=None):
    """Una fila por (t, h): lo que se sabe en t y el objetivo en t + h (estrategia directa, h es una variable).

    exog: variables ya calculadas de forma causal en t (por ejemplo lluvia acumulada hasta t).
    futuras: variables deterministas del reloj evaluadas en t + h (por ejemplo la radiación extraterrestre).
    """
    assert horizonte <= periodo, "el rezago estacional vería el futuro"
    paso = entrada.index.freq
    base = pd.DataFrame({f"y_{l}": entrada.shift(l) for l in rezagos})
    base["media_ciclo"] = entrada.rolling(periodo, min_periods=periodo // 2).mean()
    if exog is not None:
        base = base.join(exog)
    bloques = []
    for h in range(1, horizonte + 1):
        b = base.copy()
        fecha = entrada.index + h * paso
        fraccion = (fecha.hour * 60 + fecha.minute) / 1440
        b["h"] = h
        b["y_estacional"] = entrada.shift(periodo - h)  # mismo momento del ciclo anterior al objetivo
        b["sen_hora"], b["cos_hora"] = np.sin(2 * np.pi * fraccion), np.cos(2 * np.pi * fraccion)
        if futuras is not None:
            b = b.join(futuras.to_frame().shift(-h).add_suffix("_obj"))  # futuras: Series del reloj
        b["y"] = objetivo.shift(-h)
        b["t"], b["fecha_hora"] = entrada.index, fecha
        bloques.append(b)
    return pd.concat(bloques, ignore_index=True)


def lluvia_reciente(lluvia, ventanas):
    """Lluvia acumulada en las últimas k observaciones (hasta t inclusive) y pasos desde la última lluvia."""
    out = pd.DataFrame({f"lluvia_{k}": lluvia.rolling(k, min_periods=1).sum() for k in ventanas})
    hubo = lluvia.fillna(0) > 0
    ultimo = pd.Series(np.where(hubo, np.arange(len(lluvia)), np.nan), index=lluvia.index).ffill()
    out["pasos_sin_lluvia"] = np.arange(len(lluvia)) - ultimo
    return out


# ---------------------------------------------------------------- Modelos (cada uno devuelve una tabla larga)

def _tabla(origen, fechas, pred, inf=np.nan, sup=np.nan, prob=np.nan, inf95=np.nan, sup95=np.nan):
    n = len(fechas)
    return pd.DataFrame({"origen": origen, "fecha_hora": fechas, "horizonte": np.arange(1, n + 1),
                         "pred": np.asarray(pred, float), "inf80": inf, "sup80": sup,
                         "inf95": inf95, "sup95": sup95, "prob": prob})


def _futuro(origen, horizonte, paso):
    return pd.date_range(origen + paso, periods=horizonte, freq=paso)


def persistencia(entrada, origenes_, horizonte, umbral=None):
    """El último valor observado se repite en todo el horizonte."""
    paso = entrada.index.freq
    out = []
    for o in origenes_:
        y = entrada.loc[o]
        prob = float(y >= umbral) if umbral is not None else np.nan
        out.append(_tabla(o, _futuro(o, horizonte, paso), np.full(horizonte, y), prob=prob))
    return pd.concat(out, ignore_index=True)


def estacional_ingenua(entrada, origenes_, horizonte, m, umbral=None):
    """Cada paso repite el valor de un ciclo (m pasos) antes."""
    paso = entrada.index.freq
    h = np.arange(1, horizonte + 1)
    atras = h - np.ceil(h / m).astype(int) * m  # siempre <= 0: nunca mira después del origen
    out = []
    for o in origenes_:
        fechas = _futuro(o, horizonte, paso)
        pos = entrada.index.get_loc(o) + atras
        assert pos.min() >= 0, "origen a menos de un ciclo del inicio: un índice negativo leería el futuro"
        previo = entrada.to_numpy()[pos]
        prob = (previo >= umbral).astype(float) if umbral is not None else np.nan
        out.append(_tabla(o, fechas, previo, prob=prob))
    return pd.concat(out, ignore_index=True)


def _ultimo_tramo(y):
    """Desde el último NaN en adelante: ETS no acepta huecos."""
    na = np.flatnonzero(y.isna().to_numpy())
    return y.iloc[na[-1] + 1:] if len(na) else y


def ets(entrada, origenes_, horizonte, m, cada=1, avisos=None):
    """ETS(A,N,A) con intervalos analíticos del propio modelo.

    Los parámetros se estiman cada `cada` orígenes; en los intermedios se filtra la serie hasta el origen con
    los últimos parámetros (smooth), igual que `arima`. Si el tramo sin huecos cambió de inicio, se reestima.
    """
    paso = entrada.index.freq
    out, params, inicio = [], None, None
    for i, o in enumerate(origenes_):
        y = _ultimo_tramo(entrada.loc[:o])
        if len(y) < 2 * m:  # tras un hueco largo no hay dos ciclos para estimar: se salta ese origen
            continue
        modelo = ETSModel(y, error="add", trend=None, seasonal="add", seasonal_periods=m)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            if i % cada == 0 or y.index[0] != inicio:
                res = modelo.fit(disp=False, start_params=params if y.index[0] == inicio else None)
                params, inicio = res.params, y.index[0]
            else:
                res = modelo.smooth(params)
        if avisos is not None:
            avisos.extend(str(x.message) for x in w)
        p = res.get_prediction(start=len(y), end=len(y) + horizonte - 1)
        f80, f95 = p.summary_frame(alpha=ALFAS[80]), p.summary_frame(alpha=ALFAS[95])
        out.append(_tabla(o, _futuro(o, horizonte, paso), f80["mean"], f80["pi_lower"].to_numpy(),
                          f80["pi_upper"].to_numpy(), inf95=f95["pi_lower"].to_numpy(),
                          sup95=f95["pi_upper"].to_numpy()))
    return pd.concat(out, ignore_index=True)


def arima(entrada, origenes_, horizonte, orden, exog=None, tendencia="c", cada=1, avisos=None):
    """SARIMAX (regresión con errores ARIMA si hay exog). Acepta NaN: el filtro de Kalman los salta.

    Los parámetros se estiman cada `cada` orígenes con los datos hasta ese origen; en los orígenes intermedios
    el modelo solo incorpora los datos nuevos (extend) sin reestimar. exog debe ser determinista (conocida a futuro).
    """
    paso = entrada.index.freq
    out, previos = [], None
    for i, o in enumerate(origenes_):
        if i % cada == 0:
            ajuste = o
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                base = SARIMAX(entrada.loc[:o], exog=None if exog is None else exog.loc[:o], order=orden,
                               trend=tendencia).fit(disp=False, start_params=previos)
            previos = base.params  # arranque en caliente: el siguiente ajuste converge más rápido
            if avisos is not None:
                avisos.extend(str(x.message) for x in w)
            res = base
        else:
            nuevo = entrada.loc[ajuste + paso:o]
            res = base.extend(nuevo, exog=None if exog is None else exog.loc[nuevo.index])
        fechas = _futuro(o, horizonte, paso)
        f = res.get_forecast(horizonte, exog=None if exog is None else exog.loc[fechas])
        c80, c95 = f.conf_int(alpha=ALFAS[80]).to_numpy(), f.conf_int(alpha=ALFAS[95]).to_numpy()
        out.append(_tabla(o, fechas, f.predicted_mean, c80[:, 0], c80[:, 1], inf95=c95[:, 0], sup95=c95[:, 1]))
    return pd.concat(out, ignore_index=True)


def _columnas(M):
    return [c for c in M.columns if c not in ("t", "fecha_hora", "y")]


def hgb(M, origenes_, cuantiles=(0.1, 0.9), cada=1, minimo=None, params=None, incremento=False):
    """HistGradientBoosting directo multihorizonte: un modelo para la media y uno por cuantil (pérdida quantile).

    En cada reajuste solo se usan filas cuyo objetivo (t + h) es <= origen. `minimo` recorta por debajo (0 en
    radiación y lluvia). Con `incremento` aprende y(t + h) - y(t) y luego suma y(t): los árboles no extrapolan
    fuera del rango visto, y en el nivel el cambio importa más que el valor absoluto.
    """
    params = {**PARAMS_HGB, **(params or {})}
    X = _columnas(M)
    objetivo = M["y"] - M["y_0"] if incremento else M["y"]
    out = []
    for i, o in enumerate(origenes_):
        if i % cada == 0:
            tr = (M["fecha_hora"] <= o) & objetivo.notna()
            modelos = [HistGradientBoostingRegressor(**params).fit(M.loc[tr, X], objetivo[tr])]
            modelos += [HistGradientBoostingRegressor(loss="quantile", quantile=q, **params)
                        .fit(M.loc[tr, X], objetivo[tr]) for q in cuantiles]
        te = M[M["t"] == o].sort_values("h")
        base = te["y_0"].to_numpy() if incremento else 0.0
        pred = modelos[0].predict(te[X]) + base
        inf, sup = ((modelos[1].predict(te[X]) + base, modelos[2].predict(te[X]) + base) if cuantiles
                    else (np.full(len(te), np.nan),) * 2)
        inf, sup = np.minimum(inf, sup), np.maximum(inf, sup)  # evita cruces de cuantiles
        if minimo is not None:
            pred, inf, sup = (np.maximum(v, minimo) for v in (pred, inf, sup))
        out.append(_tabla(o, te["fecha_hora"].to_numpy(), pred, inf, sup))
    return pd.concat(out, ignore_index=True)


def dos_partes(M, origenes_, umbral=UMBRAL_LLUVIA, cuantiles=(0.1, 0.9), cada=1, params=None):
    """Lluvia en dos partes: P(lluvia >= umbral) con un clasificador y cantidad condicionada con un regresor
    (pérdida Poisson, solo filas con lluvia). Pronóstico puntual = P x cantidad (valor esperado).
    El intervalo sale de dos regresores por cuantil sobre la lluvia completa (ceros incluidos).
    """
    params = {**PARAMS_HGB, **(params or {})}
    X = _columnas(M)
    out = []
    for i, o in enumerate(origenes_):
        if i % cada == 0:
            tr = M[(M["fecha_hora"] <= o) & M["y"].notna()]
            llueve = tr["y"] >= umbral
            clf = HistGradientBoostingClassifier(**params).fit(tr[X], llueve)
            cantidad = HistGradientBoostingRegressor(loss="poisson", **params).fit(tr.loc[llueve, X],
                                                                                 tr.loc[llueve, "y"])
            qs = [HistGradientBoostingRegressor(loss="quantile", quantile=q, **params).fit(tr[X], tr["y"])
                  for q in cuantiles]
        te = M[M["t"] == o].sort_values("h")
        prob = clf.predict_proba(te[X])[:, 1]
        inf, sup = (np.maximum(q.predict(te[X]), 0) for q in qs)
        out.append(_tabla(o, te["fecha_hora"].to_numpy(), prob * cantidad.predict(te[X]),
                          np.minimum(inf, sup), np.maximum(inf, sup), prob=prob))
    return pd.concat(out, ignore_index=True)


def climatologia_horaria(objetivo, origenes_, horizonte, umbral=UMBRAL_LLUVIA):
    """Para cada hora del día, con el entrenamiento: P(lluvia), media (pronóstico) y cuantiles 10 y 90 (intervalo)."""
    paso = objetivo.index.freq
    out = []
    for o in origenes_:
        y = objetivo.loc[:o].dropna()
        g = y.groupby(y.index.hour)
        tabla = pd.DataFrame({"pred": g.mean(), "inf": g.quantile(0.1), "sup": g.quantile(0.9),
                              "prob": (y >= umbral).groupby(y.index.hour).mean()})
        fechas = _futuro(o, horizonte, paso)
        t = tabla.reindex(fechas.hour)
        out.append(_tabla(o, fechas, t["pred"], t["inf"].to_numpy(), t["sup"].to_numpy(),
                          prob=t["prob"].to_numpy()))
    return pd.concat(out, ignore_index=True)


def tsb_filtro(y, alfa, beta, umbral=UMBRAL_LLUVIA):
    """Teunter-Syntetos-Babai: probabilidad de ocurrencia p (se actualiza siempre) y tamaño z (solo cuando ocurre).

    Devuelve p y z después de ver cada dato; los NaN no cambian el estado. Pronóstico a cualquier horizonte: p x z.
    """
    y = np.asarray(y, float)
    ok = ~np.isnan(y)
    ocurre = ok & (y >= umbral)
    p, z = ocurre[ok].mean(), (y[ocurre].mean() if ocurre.any() else umbral)
    ps, zs = np.empty(len(y)), np.empty(len(y))
    for i in range(len(y)):
        if ok[i]:
            p += alfa * (ocurre[i] - p)
            if ocurre[i]:
                z += beta * (y[i] - z)
        ps[i], zs[i] = p, z
    return ps, zs


def tsb(objetivo, origenes_, horizonte, rejilla=(0.02, 0.05, 0.1, 0.2), umbral=UMBRAL_LLUVIA):
    """TSB con alfa y beta elegidos en cada origen por el error cuadrático a un paso dentro del entrenamiento."""
    paso = objetivo.index.freq
    out = []
    for o in origenes_:
        y = objetivo.loc[:o].to_numpy()
        mejor = None
        for a in rejilla:
            for b in rejilla:
                ps, zs = tsb_filtro(y, a, b, umbral)
                err = np.nanmean((y[1:] - (ps * zs)[:-1]) ** 2)
                if mejor is None or err < mejor[0]:
                    mejor = (err, ps[-1], zs[-1])
        _, p, z = mejor
        out.append(_tabla(o, _futuro(o, horizonte, paso), np.full(horizonte, p * z), prob=p))
    return pd.concat(out, ignore_index=True)


def siempre_cero(objetivo, origenes_, horizonte):
    """Referencia para la lluvia: nunca llueve. Muestra por qué MAE y MASE engañan con series intermitentes."""
    paso = objetivo.index.freq
    return pd.concat([_tabla(o, _futuro(o, horizonte, paso), np.zeros(horizonte), prob=0.0) for o in origenes_],
                     ignore_index=True)


def conformal(p, nivel=80, usar=None, minimo=None, min_n=48):
    """CQR secuencial (Romano et al., 2019, aplicado en línea): ajusta el intervalo de cada origen con el cuantil
    de los puntajes max(inf - real, real - sup) de los orígenes anteriores cuyo dato real ya se conocía en ese
    origen (fecha_hora <= origen). No usa nada posterior al origen. `usar` limita las filas que dan y reciben
    el ajuste (por ejemplo solo horas con sol). Sin min_n puntajes previos el intervalo queda en NaN.
    """
    p = p.assign(_usar=True if usar is None else np.asarray(usar, bool))  # la máscara viaja con su fila al ordenar
    p = p.sort_values(["origen", "horizonte"]).reset_index(drop=True)
    usar = p.pop("_usar").to_numpy(bool)
    inf, sup = p[f"inf{nivel}"].to_numpy(float).copy(), p[f"sup{nivel}"].to_numpy(float).copy()
    puntaje = np.maximum(inf - p["real"].to_numpy(), p["real"].to_numpy() - sup)
    origen, fecha = p["origen"].to_numpy(), p["fecha_hora"].to_numpy()
    for o in np.unique(origen):
        previos = (origen < o) & (fecha <= o) & usar & ~np.isnan(puntaje)
        filas = (origen == o) & usar
        n = previos.sum()
        if n < min_n:
            inf[filas] = sup[filas] = np.nan
            continue
        q = np.quantile(puntaje[previos], min(1.0, (1 - ALFAS[nivel]) * (n + 1) / n))
        inf[filas], sup[filas] = inf[filas] - q, sup[filas] + q
    cruzado = inf > sup  # un q negativo grande podría invertir el intervalo
    inf[cruzado] = sup[cruzado] = ((inf + sup) / 2)[cruzado]
    if minimo is not None:
        inf, sup = np.maximum(inf, minimo), np.maximum(sup, minimo)  # maximum propaga el NaN; fmax lo taparía
    return p.assign(**{f"inf{nivel}": inf, f"sup{nivel}": sup})


# ---------------------------------------------------------------- Métricas

def mase(errores_abs, escala):
    """Error absoluto medio escalado: promedio de |e| / escala (la escala es la del entrenamiento de cada origen)."""
    return float(np.mean(np.asarray(errores_abs, float) / np.asarray(escala, float)))


def brier(prob, ocurre):
    return float(np.mean((np.asarray(prob, float) - np.asarray(ocurre, float)) ** 2))


def muestra_comun(p):
    """Solo las filas (origen, fecha_hora) con dato real y pronóstico de todos los modelos: comparación justa."""
    ok = p.dropna(subset=["real", "pred"]).groupby(["origen", "fecha_hora"])["modelo"].transform("size")
    p = p.dropna(subset=["real", "pred"])
    return p[ok == p["modelo"].nunique()]


def metricas(p, escalas, umbral=None, referencia_brier=None):
    """Tabla por modelo: MAE, RMSE, MASE, cobertura y ancho del 80 % (y 95 %), y Brier y BSS si hay umbral."""
    p = muestra_comun(p).assign(escala=lambda d: d["origen"].map(escalas))
    filas = []
    for modelo, d in p.groupby("modelo", sort=False):
        e = d["pred"] - d["real"]
        fila = {"modelo": modelo, "MAE": e.abs().mean(), "RMSE": np.sqrt((e ** 2).mean()),
                "MASE": mase(e.abs(), d["escala"]), "n_origenes": d["origen"].nunique(), "n": len(d)}
        for nivel in (80, 95):
            con = d.dropna(subset=[f"inf{nivel}", f"sup{nivel}"])
            fila[f"cobertura{nivel}"] = (con["real"].between(con[f"inf{nivel}"], con[f"sup{nivel}"]).mean()
                                         if len(con) else np.nan)
            fila[f"ancho{nivel}"] = (con[f"sup{nivel}"] - con[f"inf{nivel}"]).mean() if len(con) else np.nan
        if umbral is not None:
            fila["Brier"] = brier(d["prob"], d["real"] >= umbral)
        filas.append(fila)
    t = pd.DataFrame(filas)
    if umbral is not None and referencia_brier is not None:
        t["BSS"] = 1 - t["Brier"] / t.loc[t["modelo"] == referencia_brier, "Brier"].iloc[0]
    return t


def por_horizonte(p):
    """MAE, cobertura del 80 % y ancho medio por horizonte y modelo (sobre la muestra común)."""
    p = muestra_comun(p)
    g = p.assign(ae=(p["pred"] - p["real"]).abs(),
                 dentro=p["real"].between(p["inf80"], p["sup80"]).astype(float).where(p["inf80"].notna()),
                 ancho=p["sup80"] - p["inf80"]).groupby(["modelo", "horizonte"], sort=False)
    t = g.agg(MAE=("ae", "mean"), cobertura80=("dentro", "mean"), ancho80=("ancho", "mean")).reset_index()
    return t.sort_values("horizonte", kind="stable")  # sort=False deja los horizontes en orden de aparición
