"""Carga de los CSV crudos, diccionario de estaciones y variables, regularización y agregación.

Los CSV de docs/ nunca se modifican: todo se hace sobre copias en memoria.
"""
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
DIR_DATOS = RAIZ / "docs" / "Datos Prueba Tecnica"
DIR_SALIDAS = RAIZ / "parte2" / "salidas"

# Coordenadas: centro de la caja geográfica de cada ficha en datos.siata.gov.co (consultada el 24 oct 2026).
# utc_archivo: desfase del reloj del archivo frente a UTC. La 6004 viene en UTC (ver informe, supuesto S1).
ESTACIONES = {
    "367": {"archivo": "Estacion_meteorologica_367_2025-12-01_2026-04-30.csv", "tipo": "Meteorológica",
            "nombre": "Joaquín Vallejo (La Ladera, Medellín)", "lat": 6.255345, "lon": -75.542478,
            "variables": ["h", "t", "pr", "vv", "vv_max", "dv", "dv_max", "p"], "utc_archivo": -5},
    "803": {"archivo": "Estacion_nivel_803_2025-12-01_2026-04-30.csv", "tipo": "Nivel",
            "nombre": "Q. La Aguadita, Colinas de Enciso (Medellín)", "lat": 6.25385, "lon": -75.544067,
            "variables": ["nivel"], "utc_archivo": -5},
    "6004": {"archivo": "Estacion_piranometro_6004_2025-12-01_2026-04-30.csv", "tipo": "Piranómetro",
             "nombre": "Parque de las Aguas (Barbosa)", "lat": 6.406712, "lon": -75.419344,
             "variables": ["radiacion"], "utc_archivo": 0},
    "35": {"archivo": "Estacion_pluviometrica_35_2025-12-01_2026-04-30.csv", "tipo": "Pluviométrica",
           "nombre": "I.E. Joaquín Vallejo Arbeláez (La Ladera, Medellín)", "lat": 6.255345, "lon": -75.542478,
           "variables": ["p1", "p2"], "utc_archivo": -5},
}
UTC_LOCAL = -5  # Colombia no tiene horario de verano

# Diccionario reconstruido. "agregacion" dice cómo se resume por hora; "circular" marca ángulos.
VARIABLES = {
    "h": {"nombre": "Humedad relativa", "unidad": "%", "agregacion": "media"},
    "t": {"nombre": "Temperatura del aire", "unidad": "°C", "agregacion": "media"},
    "pr": {"nombre": "Presión atmosférica en la estación", "unidad": "hPa", "agregacion": "media"},
    "vv": {"nombre": "Velocidad media del viento", "unidad": "m/s", "agregacion": "media"},
    "vv_max": {"nombre": "Velocidad máxima del viento (ráfaga)", "unidad": "m/s", "agregacion": "max"},
    "dv": {"nombre": "Dirección media del viento", "unidad": "grados", "agregacion": "circular", "circular": True},
    "dv_max": {"nombre": "Dirección de la ráfaga", "unidad": "grados", "agregacion": "circular", "circular": True},
    "p": {"nombre": "Precipitación (sensor de la estación meteorológica)", "unidad": "mm", "agregacion": "suma"},
    "nivel": {"nombre": "Nivel del agua (fondo de referencia menos lámina de agua)", "unidad": "cm", "agregacion": "media"},
    "radiacion": {"nombre": "Irradiancia solar global horizontal", "unidad": "W/m²", "agregacion": "media"},
    "p1": {"nombre": "Precipitación, sensor 1 (balancín de 0,254 mm)", "unidad": "mm", "agregacion": "suma"},
    "p2": {"nombre": "Precipitación, sensor 2 (balancín de 0,254 mm)", "unidad": "mm", "agregacion": "suma"},
}
CENTINELAS = (-999.0, -9999.0)  # -9999 es el faltante de la guía de piranómetros


def cargar(codigo):
    """Lee el CSV crudo de una estación tal cual viene (fecha_hora como texto convertido a datetime)."""
    df = pd.read_csv(DIR_DATOS / ESTACIONES[codigo]["archivo"])
    # Formato explícito: lo que no lo cumpla queda como NaT. Si pasan del 1 %, el formato cambió y se detiene
    df["fecha_hora"] = pd.to_datetime(df["fecha_hora"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    malas = int(df["fecha_hora"].isna().sum())
    if malas > 0.01 * len(df):
        raise ValueError(f"{codigo}: {malas} de {len(df)} fechas no cumplen el formato AAAA-MM-DD HH:MM:SS")
    if malas:
        warnings.warn(f"{codigo}: {malas} fechas no cumplen el formato y se descartan")
    return df


def a_hora_local(fecha_hora, codigo):
    """Lleva el reloj del archivo a hora local de Colombia (UTC-5)."""
    return fecha_hora + pd.Timedelta(hours=UTC_LOCAL - ESTACIONES[codigo]["utc_archivo"])


def malla(codigo):
    """Minutos esperados del periodo, en hora local."""
    inicio = a_hora_local(pd.Timestamp("2025-12-01 00:00"), codigo)
    return pd.date_range(inicio, inicio + pd.Timedelta("150D") + pd.Timedelta("23h59min"), freq="min")


def regularizar(df, codigo):
    """Serie minutal en hora local sobre la malla completa.

    - Las marcas que no caen en el minuto exacto se llevan al minuto (floor); si chocan, gana la primera.
    - Los minutos sin registro quedan en NaN con presente=False (no se interpola nada).
    - Los centinelas (-999) pasan a NaN y quedan marcados en la columna centinela.
    """
    d = df.dropna(subset=["fecha_hora"]).copy()
    d["fecha_hora_archivo"] = d["fecha_hora"]
    d["fuera_de_minuto"] = d["fecha_hora"].dt.second != 0
    d["fecha_hora"] = a_hora_local(d["fecha_hora"].dt.floor("min"), codigo)
    d = d.drop_duplicates("fecha_hora", keep="first").set_index("fecha_hora")
    variables = ESTACIONES[codigo]["variables"]
    d["centinela"] = d[variables].isin(CENTINELAS).any(axis=1)
    d[variables] = d[variables].mask(d[variables].isin(CENTINELAS))
    out = d.reindex(malla(codigo))
    out.index.name = "fecha_hora"
    out["presente"] = out["codigo"].notna()
    out["codigo"] = codigo
    out["fuera_de_minuto"] = out["fuera_de_minuto"].fillna(False).astype(bool)
    out["centinela"] = out["centinela"].fillna(False).astype(bool)
    return out


def media_circular(grados, pesos=None):
    """Dirección media en grados [0, 360) a partir de componentes vectoriales."""
    rad = np.deg2rad(np.asarray(grados, dtype=float))
    w = np.ones_like(rad) if pesos is None else np.asarray(pesos, dtype=float)
    ok = ~np.isnan(rad) & ~np.isnan(w)
    if not ok.any() or w[ok].sum() == 0:
        return np.nan
    grados = np.rad2deg(np.arctan2((w[ok] * np.sin(rad[ok])).sum(), (w[ok] * np.cos(rad[ok])).sum()))
    return float(np.round(grados, 9) % 360)  # el redondeo evita devolver 360 por un -1e-15


def agregar(serie_min, variable, freq="h", cobertura_min=0.75, pesos=None):
    """Agrega una serie minutal a freq. Devuelve NaN si la fracción de minutos con dato < cobertura_min.

    La lluvia se suma; la ráfaga toma el máximo; la dirección usa media vectorial ponderada por la velocidad.
    """
    regla = VARIABLES[variable]["agregacion"]
    if pesos is not None:  # un minuto sin peso no entra en la media: tampoco cuenta en la cobertura
        serie_min = serie_min.where(pesos.reindex(serie_min.index).notna())
    grupos = serie_min.resample(freq)
    esperados = grupos.size()
    cobertura = grupos.count() / esperados
    if regla == "suma":
        valor = grupos.sum(min_count=1)
    elif regla == "max":
        valor = grupos.max()
    elif regla == "circular":
        w = pd.Series(1.0, index=serie_min.index) if pesos is None else pesos.reindex(serie_min.index)
        rad = np.deg2rad(serie_min)
        u = (w * np.sin(rad)).resample(freq).sum(min_count=1)
        v = (w * np.cos(rad)).resample(freq).sum(min_count=1)
        valor = pd.Series(np.round(np.rad2deg(np.arctan2(u, v)), 9) % 360, index=u.index)
        valor = valor.where((u != 0) | (v != 0))  # sin viento no hay dirección
    else:
        valor = grupos.mean()
    return valor.where(cobertura >= cobertura_min)


def cargar_todo():
    """Las cuatro estaciones regularizadas, en hora local."""
    return {c: regularizar(cargar(c), c) for c in ESTACIONES}
