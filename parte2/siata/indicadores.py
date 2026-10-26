"""Los tres indicadores de calidad de la pregunta 1.3, que alimentan la vista de salud de la red (Tarea F2).

1. Completitud: fracción de los registros esperados que llegó con valor.
2. Proporción de datos válidos: fracción de lo recibido que pasa todas las reglas deterministas.
3. Confiabilidad de la bandera: acuerdo (kappa de Cohen) entre la columna calidad de SIATA y el control
   independiente de este repositorio.
"""
import numpy as np
import pandas as pd

from .calidad import BUENO, FALTANTE
from .datos import CENTINELAS

# Semáforo: (límite de aceptable, límite de alerta). Por debajo del segundo es crítico.
SEMAFORO = {
    "completitud": (0.95, 0.80),
    "validos": (0.98, 0.90),
    "kappa": (0.61, 0.41),  # Landis y Koch (1977): inicio del acuerdo sustancial y del moderado
}
# Códigos de SIATA que no indican un problema del dato: 1 confiable en tiempo real, 2 confiable no en tiempo real
CALIDAD_CONFIABLE = (1, 2)


def semaforo(valor, indicador):
    if pd.isna(valor):
        return "sin dato"
    aceptable, alerta = SEMAFORO[indicador]
    return "aceptable" if valor >= aceptable else "alerta" if valor >= alerta else "crítico"


def completitud(banderas, freq="D"):
    """Por variable y periodo: minutos con valor / minutos esperados (la malla ya es la esperada)."""
    return (banderas != FALTANTE).resample(freq).mean()


def proporcion_validos(banderas, freq="D"):
    """Por variable y periodo: minutos con bandera buena / minutos con valor."""
    con_dato = banderas != FALTANTE
    buenos = (banderas == BUENO).resample(freq).sum()
    return buenos / con_dato.resample(freq).sum().replace(0, np.nan)


def kappa(a, b):
    """Kappa de Cohen entre dos clasificaciones binarias.

    Si solo una de las dos marca positivos el kappa es 0 (acuerdo de azar). Solo es NaN cuando el acuerdo
    esperado es 1, por ejemplo si ninguna de las dos marca nada: ahí no hay nada que medir.
    """
    a, b = np.asarray(a, bool), np.asarray(b, bool)
    if len(a) == 0:
        return np.nan
    observado = (a == b).mean()
    esperado = a.mean() * b.mean() + (1 - a.mean()) * (1 - b.mean())
    if esperado == 1:
        return np.nan
    return (observado - esperado) / (1 - esperado)


def kappa_maximo(a, b):
    """Kappa más alto posible con las prevalencias de a y b: separa desacuerdo real de distinta sensibilidad."""
    pa, pb = np.mean(a), np.mean(b)
    esperado = pa * pb + (1 - pa) * (1 - pb)
    if esperado == 1:
        return np.nan
    return (min(pa, pb) + min(1 - pa, 1 - pb) - esperado) / (1 - esperado)


def confiabilidad_bandera(calidad_siata, bandera_propia, freq="MS"):
    """Kappa por periodo entre 'SIATA lo marca dudoso' y 'el control independiente no lo da por bueno'.

    Se calcula por mes: con pocos datos dudosos el kappa es inestable. freq=None da el periodo completo.
    También devuelve las dos tasas que lo explican.
    """
    con_dato = calidad_siata.notna() & (bandera_propia != FALTANTE)
    t = pd.DataFrame({"siata_dudoso": ~calidad_siata.isin(CALIDAD_CONFIABLE),
                      "propio_dudoso": bandera_propia != BUENO})[con_dato]
    filas = {}
    for periodo, g in ([("total", t)] if freq is None else t.resample(freq)):
        confiables = ~g["siata_dudoso"]
        filas[periodo] = {
            "kappa": kappa(g["siata_dudoso"], g["propio_dudoso"]),
            "kappa_max": kappa_maximo(g["siata_dudoso"], g["propio_dudoso"]),
            # de lo que SIATA publica como confiable, cuánto no pasa el control independiente
            "falsos_confiables": (g["propio_dudoso"] & confiables).sum() / max(confiables.sum(), 1),
            # de lo que SIATA marca dudoso, cuánto pasa el control independiente
            "dudosos_que_pasan": (~g["propio_dudoso"] & g["siata_dudoso"]).sum() / max(g["siata_dudoso"].sum(), 1),
            "n": len(g),
        }
    return pd.DataFrame.from_dict(filas, orient="index")


def completitud_tabla_larga(tabla, intervalo_s, freq="D", desde=None, hasta=None):
    """Pregunta 1.4 en Python: completitud sobre una tabla (codigo, fecha_hora, valor, calidad).

    intervalo_s: dict codigo -> intervalo nominal de muestreo en segundos. Cada registro se asigna a su
    casilla del intervalo nominal, de modo que dos registros en la misma casilla cuentan una sola vez y
    estaciones con muestreo distinto (1, 5 o 10 min) se comparan en la misma escala de 0 a 1.
    Con desde y hasta, los periodos sin ningún registro salen con 0 en vez de desaparecer.
    """
    t = tabla.dropna(subset=["valor"]).copy()
    t = t[~t["valor"].isin(CENTINELAS)]
    paso = t["codigo"].map(intervalo_s)
    segundos = (t["fecha_hora"] - pd.Timestamp("1970-01-01")).dt.total_seconds()
    t["casilla"] = segundos // paso
    t["periodo"] = t["fecha_hora"].dt.floor(freq)
    recibidos = t.groupby(["codigo", "periodo"])["casilla"].nunique()
    duracion_s = {"D": 86400, "h": 3600}[freq]
    esperados = recibidos.index.get_level_values("codigo").map(intervalo_s).map(lambda s: duracion_s // s)
    completitud = (recibidos / esperados.to_numpy()).rename("completitud")
    if desde is not None and hasta is not None:
        malla = pd.MultiIndex.from_product([sorted(intervalo_s), pd.date_range(desde, hasta, freq=freq)],
                                           names=["codigo", "periodo"])
        completitud = completitud.reindex(malla, fill_value=0.0)
    return completitud
