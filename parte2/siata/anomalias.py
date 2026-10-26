"""Detección de anomalías con métodos estadísticos y de aprendizaje automático (Tarea C2), comparación con la
columna calidad como etiqueta débil (C3) y consolidación y clasificación de eventos (C4).

Las reglas deterministas (C1) y el esquema de banderas (C5) están en calidad.py; aquí se usan su traza y sus
banderas. Los métodos de este módulo trabajan sobre series horarias calculadas con todos los datos recibidos,
también los que no pasan las reglas, para que la comparación con ellas no sea circular.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from statsmodels.tsa.seasonal import STL

from .calidad import MALO
from .indicadores import CALIDAD_CONFIABLE

UMBRAL_Z = 3.5  # puntaje z modificado: umbral usual de Iglewicz y Hoaglin (1993)
VARIABLES_ALERTA = {"nivel", "p", "p1", "p2"}  # las que alimentan alertas de inundación
TIPOS = ("falla de sensor", "falla de comunicación", "problema de configuración", "evento físico real")


def etiqueta_debil(calidad):
    """True donde SIATA marca el dato como dudoso: código distinto de 1 y 2 (2 es dato válido no en tiempo real).

    Sin registro (NaN) queda False: no es una opinión de SIATA sobre un valor.
    """
    return calidad.notna() & ~calidad.isin(CALIDAD_CONFIABLE)


def puntaje_robusto(x, grupos=None):
    """Puntaje z robusto (x - mediana) / (1,4826 · MAD).

    Con grupos (por ejemplo la hora del día) la mediana y la MAD se calculan por grupo, porque la dispersión
    del residuo cambia a lo largo del día. Donde la MAD es cero el puntaje queda NaN, no infinito.
    """
    x = pd.Series(x, dtype=float)
    g = np.zeros(len(x)) if grupos is None else np.asarray(grupos)
    mediana = x.groupby(g).transform("median")
    mad = (x - mediana).abs().groupby(g).transform("median")
    return (x - mediana) / (1.4826 * mad.where(mad > 0))


def residuo_stl(s, periodo=24, estacional=31):
    """Residuo de STL robusto (Cleveland y otros, 1990) de una serie horaria.

    estacional=31: el ciclo diurno se suaviza sobre unos 31 días, así no persigue cada día atípico.
    Los huecos se interpolan linealmente solo para poder ajustar; en el residuo quedan en NaN y no se evalúan.
    """
    ajuste = STL(s.interpolate(limit_direction="both"), period=periodo, seasonal=estacional, robust=True).fit()
    return ajuste.resid.where(s.notna())


def anomalias_stl(s, umbral=UMBRAL_Z, evaluar=None):
    """Horas cuyo residuo de STL tiene |z robusto| > umbral, con la escala calculada por hora del día.

    evaluar: máscara booleana opcional de las horas que se evalúan (por ejemplo, solo de día en la radiación).
    """
    r = residuo_stl(s)
    if evaluar is not None:
        r = r.where(evaluar.reindex(r.index, fill_value=False))
    z = puntaje_robusto(r, r.index.hour)
    return pd.DataFrame({"valor": s, "residuo": r, "z": z, "anomalia": z.abs() > umbral})


def isolation_forest(H, contaminacion=0.01, semilla=0):
    """Isolation Forest (Liu, Ting y Zhou, 2008) sobre variables horarias, sus cambios en una hora y la hora
    del día (seno y coseno, para que un valor normal al mediodía pueda ser raro a medianoche).

    Las variables se escalan con mediana y rango intercuartílico. contaminacion es la fracción de horas que
    se marca: es un supuesto, no algo que el modelo aprenda. Devuelve puntaje (mayor = más raro) y marca;
    las horas sin datos completos quedan sin puntaje y sin marca.
    """
    X = H.join(H.diff().add_prefix("d_"))
    angulo = 2 * np.pi * X.index.hour / 24
    X = X.assign(sen_hora=np.sin(angulo), cos_hora=np.cos(angulo)).dropna()
    X = (X - X.median()) / (X.quantile(0.75) - X.quantile(0.25))
    modelo = IsolationForest(n_estimators=300, contamination=contaminacion, random_state=semilla).fit(X)
    salida = pd.DataFrame({"puntaje": -modelo.score_samples(X), "anomalia": modelo.predict(X) == -1}, index=X.index)
    salida = salida.reindex(H.index)
    salida["anomalia"] = salida["anomalia"].fillna(False).astype(bool)
    return salida


def segmentacion_binaria(s, penalizacion=None, tam_min=7):
    """Cambios de media por segmentación binaria con costo cuadrático (Scott y Knott, 1974).

    Parte el tramo donde la reducción del costo es mayor mientras supere la penalización. Por defecto la
    penalización es tipo BIC, 2·σ²·ln(n), con σ estimada por la MAD de las diferencias (no la inflan los
    propios cambios). tam_min: mínimo de puntos por segmento. Los NaN se descartan.
    Devuelve un DataFrame de segmentos: inicio, fin, n, media.
    """
    x = s.dropna()
    v = x.to_numpy(float)
    n = len(v)
    if penalizacion is None:
        d = np.diff(v)
        sigma = 1.4826 * np.median(np.abs(d - np.median(d))) / np.sqrt(2)
        penalizacion = 2 * sigma ** 2 * np.log(n)
    cambios, pendientes = [], [(0, n)]
    while pendientes:
        i, j = pendientes.pop()
        tramo = v[i:j]
        m = len(tramo)
        if m < 2 * tam_min:
            continue
        k = np.arange(tam_min, m - tam_min + 1)
        izquierda = np.cumsum(tramo)[k - 1]
        # reducción del costo al partir en k: k(m-k)/m · (media izquierda - media derecha)²
        ganancia = k * (m - k) / m * (izquierda / k - (tramo.sum() - izquierda) / (m - k)) ** 2
        b = int(ganancia.argmax())
        if ganancia[b] > penalizacion:
            corte = i + int(k[b])
            cambios.append(corte)
            pendientes += [(i, corte), (corte, j)]
    bordes = [0, *sorted(cambios), n]
    return pd.DataFrame([{"inicio": x.index[a], "fin": x.index[b - 1], "n": b - a, "media": v[a:b].mean()}
                         for a, b in zip(bordes[:-1], bordes[1:])])


def precision_exhaustividad(marca, etiqueta):
    """Precisión y exhaustividad de una marca frente a la etiqueta débil, con los conteos que las explican."""
    marca, etiqueta = np.asarray(marca, bool), np.asarray(etiqueta, bool)
    vp = int((marca & etiqueta).sum())
    return {"precision": vp / marca.sum() if marca.any() else np.nan,
            "exhaustividad": vp / etiqueta.sum() if etiqueta.any() else np.nan,
            "n_marcados": int(marca.sum()), "n_etiqueta": int(etiqueta.sum()), "n_total": len(marca)}


def eventos(marcas, tolerancia="1min", por=("codigo", "variable")):
    """Une en eventos los intervalos [inicio, fin] de un mismo grupo que se tocan o están a menos de tolerancia.

    marcas: DataFrame con inicio, fin y las columnas de por. Las demás columnas se resumen en el evento: las
    numéricas con el máximo (por ejemplo la bandera) y las de texto con sus valores únicos unidos por '+'.
    """
    por = list(por)
    m = marcas.sort_values([*por, "inicio"]).reset_index(drop=True)
    fin_previo = m.groupby(por)["fin"].transform(lambda f: f.cummax().shift())
    m["_evento"] = (~(m["inicio"] <= fin_previo + pd.Timedelta(tolerancia))).cumsum()
    resumen = {"inicio": "min", "fin": "max"}
    for c in m.columns.difference([*por, "inicio", "fin", "_evento"]):
        resumen[c] = "max" if pd.api.types.is_numeric_dtype(m[c]) else (lambda x: "+".join(sorted(set(map(str, x)))))
    ev = m.groupby([*por, "_evento"]).agg(resumen).reset_index().drop(columns="_evento")
    ev["duracion_min"] = ((ev["fin"] - ev["inicio"]) / pd.Timedelta("1min")).astype(int) + 1
    return ev


def tipo_evento(reglas, variable, lluvia_mm=0.0, valores_distintos=None, centinela=False):
    """Clasifica un evento según qué lo marcó y su contexto. Criterio explícito; gana la peor lectura.

    reglas: nombres de las pruebas o modelos unidos por '+'. variable: la variable (o variables con '+').
    lluvia_mm: lluvia en la 35 desde 3 h antes del inicio hasta el fin del evento.
    valores_distintos: cuántos valores distintos tomó la variable durante el evento.
    """
    tipos = set()
    for r in reglas.split("+"):
        if r == "hueco":
            tipos.add("falla de sensor" if centinela else "falla de comunicación")
        elif r in ("direccion_sin_viento", "resolucion", "sin_contexto"):
            # convención del registrador (en la 367 dv va de 0 a 359 y el norte se escribe 0), no un valor físico
            tipos.add("problema de configuración")
        elif r == "radiacion_extrema" or (r == "salto" and variable == "radiacion"):
            tipos.add("evento físico real")  # realce y paso de nubes
        elif r == "persistencia" and valores_distintos is not None and valores_distintos > 1:
            tipos.add("evento físico real")  # el sensor sigue cambiando: la variable está estable, no congelada
        elif r in ("salto", "stl_mad", "isolation_forest") and lluvia_mm >= 1.0:
            tipos.add("evento físico real")  # responde a lluvia medida en la 35
        else:
            tipos.add("falla de sensor")
    for t in TIPOS:  # orden de prioridad: si algo apunta a falla, el evento no se da por real
        if t in tipos:
            return t


def severidad(tipo, variables, duracion_min, bandera=None):
    """Severidad ligada al impacto en las alertas de inundación (nivel y lluvia).

    Problema del dato (falla o configuración):
      alta  = nivel o lluvia, y dato malo (4) o una hora o más (la quebrada llega al pico en unos 25 min);
      media = nivel o lluvia por menos de una hora, u otra variable por una hora o más;
      baja  = otra variable por menos de una hora.
    Evento físico real: alta si es de nivel o lluvia, porque borrarlo dejaría a la alerta sin el evento que
    debe detectar; baja en otro caso.
    """
    alerta = bool(VARIABLES_ALERTA & set(variables.split("+")))
    if tipo == "evento físico real":
        return "alta" if alerta else "baja"
    if alerta:
        return "alta" if bandera == MALO or duracion_min >= 60 else "media"
    return "media" if duracion_min >= 60 else "baja"
