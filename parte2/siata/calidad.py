"""Reglas deterministas de control de calidad (Tarea C1) y esquema de banderas (Tarea C5).

Cada prueba devuelve una serie booleana (True = el dato falla la prueba). evaluar() las corre todas,
asigna a cada dato la bandera más severa y deja la traza de qué prueba la disparó.

Es un control diferido (sobre el periodo completo): el salto marca también el minuto anterior y la persistencia
marca toda la ventana hacia atrás, así que la bandera de un minuto puede depender de minutos posteriores.
En tiempo real se usaría la misma regla marcando solo el último minuto.

Esquema de banderas: el de la recomendación IOC/UNESCO (Manuals and Guides 54, vol. 3, 2013):
1 bueno, 2 no evaluado, 3 sospechoso, 4 malo, 9 faltante.
"""
import numpy as np
import pandas as pd

from .datos import ESTACIONES, agregar

BUENO, NO_EVALUADO, SOSPECHOSO, MALO, FALTANTE = 1, 2, 3, 4, 9
VERSION_REGLAS = "2026-10-25"  # se escribe en cada salida: un cambio de regla debe cambiar este valor
NOMBRE_BANDERA = {BUENO: "bueno", NO_EVALUADO: "no evaluado", SOSPECHOSO: "sospechoso", MALO: "malo",
                  FALTANTE: "faltante"}

# Umbrales y su origen. Se citan en parte1/03 (pregunta 1.6) y en el panel de transparencia del dashboard.
# OMM: WMO-No. 488, Guide to the Global Observing System (2010, act. 2017), apéndice VI.2, pp. 202-203.
UMBRALES = {
    # Límites fijos de la OMM (fuera de ellos el dato es erróneo). La nota de la OMM permite ajustarlos a la región:
    # la temperatura se acota a -20/50 °C. La radiación usa el mínimo de BSRN; su máximo depende del sol (abajo).
    "rango_fisico": {"h": (0, 100), "t": (-20, 50), "pr": (500, 1100), "vv": (0, 75), "vv_max": (0, 150),
                     "dv": (0, 360), "dv_max": (0, 360), "p": (0, 40), "p1": (0, 40), "p2": (0, 40),
                     "radiacion": (-4, None)},
    # Rango climatológico del sitio: posible pero raro (sospechoso)
    "rango_clima": {"t": (5, 35), "pr": (800, 835), "vv": (0, 30), "vv_max": (0, 40), "h": (5, 100),
                    "p": (0, 5), "p1": (0, 5), "p2": (0, 5),
                    # nivel: el máximo con calidad 1 es 36 cm; 100 cm pide revisión humana (no se borra:
                    # puede ser una creciente real). Debe recalibrarse con la sección del cauce.
                    "nivel": (None, 100)},
    # Salto máximo entre minutos consecutivos (OMM, p. 202): sospechoso y erróneo. Nivel: criterio propio
    "salto": {"t": 3, "h": 10, "pr": 0.5, "vv": 10, "radiacion": 800, "nivel": 20},
    "salto_malo": {"t": 10, "h": 15, "pr": 2, "vv": 20, "radiacion": 1000},
    # Variabilidad mínima en una ventana (minutos, cambio mínimo): por debajo, valor congelado.
    # Los de 60 min son los de la OMM (p. 203); nivel y radiación: criterio propio
    "persistencia": {"t": (60, 0.1), "h": (60, 1), "pr": (60, 0.1), "vv": (60, 0.5), "dv": (60, 10),
                     "nivel": (360, 0.1), "radiacion": (30, 0.01)},
    # Subida del nivel sobre su línea base (percentil 25 de 7 días) sin lluvia: sospechoso, malo.
    # 15 cm queda justo sobre el máximo visto en datos con calidad 1 y sin lluvia (14 cm).
    "nivel_pico_sin_lluvia_cm": (15, 30),
    "lluvia_previa_mm": 1.0,  # lluvia en la 35 en las 3 h previas que justifica una subida del nivel
    "radiacion_noche_wm2": 5,  # con el sol más de 3° bajo el horizonte
    # Diferencia horaria entre balancines: la mayor entre dos vueltas y el 10 % de la lluvia de la hora
    # (incertidumbre alcanzable de 5 % por pluviómetro, WMO-No. 8 vol. I anexo 1.A, sumada en los dos)
    "p1_p2_hora_mm": 0.508,
    "p1_p2_hora_fraccion": 0.10,
    "p_367_vs_35_mm": 1.0,  # lluvia horaria en la 35 sin un solo registro en la 367
    # la 367 registra cerca de 0,28 veces lo de la 35: 0,08 mm en la 367 equivalen a una vuelta (0,254 mm) en la 35
    "p_367_sin_respaldo_mm": 0.08,
}

DESCRIPCION_PRUEBA = {
    "hueco": "No llegó el registro del minuto (o llegó el centinela -999).",
    "rango_fisico": "Valor fuera del rango posible de la variable o del sensor.",
    "rango_clima": "Valor posible pero fuera del rango climatológico del sitio.",
    "salto": "Cambio entre minutos consecutivos mayor que el máximo plausible.",
    "viento_cuadruple_cero": "vv, vv_max, dv y dv_max en 0 a la vez: el anemómetro no reporta (no es calma).",
    "factor_rafaga": "Viento de 5 m/s o más con ráfaga menor que 1,1 veces la media: ráfaga y media trabadas juntas.",
    "persistencia": "Valor congelado: la variable casi no cambia en la ventana.",
    "rafaga_menor": "La ráfaga (vv_max) es menor que la velocidad media (vv).",
    "direccion_sin_viento": "Hay dirección del viento con velocidad cero.",
    "pico_sin_lluvia": "Nivel más de 15 cm sobre su línea base con menos de 1 mm de lluvia en la 35 en las 3 h previas.",
    "radiacion_nocturna": "Radiación mayor que 5 W/m² con el sol más de 3° bajo el horizonte.",
    "radiacion_extrema": "Radiación sobre el límite 'extremadamente raro' de BSRN.",
    "radiacion_imposible": "Radiación sobre el límite 'físicamente posible' de BSRN.",
    "p1_p2_difieren": "Los dos balancines de la 35 difieren en la hora más de dos vueltas y más del 10 %.",
    "resolucion": "Valor que no es múltiplo de la vuelta del balancín (0,254 mm).",
    "lluvia_no_registrada": "Llovió en la 35 (mismo sitio) y la 367 no registró nada en la hora.",
    "lluvia_sin_respaldo": "La 367 registró 0,08 mm o más en la hora (una vuelta de la 35) y los dos balancines de la 35 no.",
    "sin_contexto": "No se pudo evaluar: faltan las 3 h previas de lluvia de la 35 o de historia del nivel.",
}


# ---------- Pruebas genéricas ----------

def fuera_de_rango(s, minimo=None, maximo=None):
    falla = pd.Series(False, index=s.index)
    if minimo is not None:
        falla |= s < minimo
    if maximo is not None:
        falla |= s > maximo
    return falla


def salto(s, maximo):
    """Marca los dos minutos de un salto mayor que maximo (no se sabe cuál de los dos está mal).

    Solo compara minutos consecutivos: a través de un hueco no hay salto que medir.
    """
    consecutivo = (s.index.to_series().diff() == pd.Timedelta("1min")).to_numpy()
    d = (s.diff().abs() > maximo) & consecutivo
    return d | d.shift(-1, fill_value=False)


def persistencia(s, ventana, cambio_minimo, condicion=None):
    """Marca toda la ventana en la que max - min < cambio_minimo. condicion limita dónde aplica.

    La OMM marca si el valor "no varía más de" el umbral (<=). Aquí es < estricto a propósito: en la 367 la
    resolución real de h (1 %) y de t (0,1 °C) es igual al umbral, y con <= la humedad pasaría de 1827 a 18 737
    minutos marcados (8,6 % del periodo). Con < y valores en pasos de la resolución, la prueba equivale a "valor
    idéntico toda la ventana"; en t, el 39 % de los minutos trae promedios con más decimales.
    La diferencia se redondea porque en coma flotante 16,7 - 16,6 da 0,0999... y 17,6 - 17,5 da 0,1000...1, y la
    regla se volvería "<=" al azar. Basta el 90 % de la ventana con dato, para que no se escape un registrador
    congelado que pierde un minuto de vez en cuando.
    """
    r = s.rolling(ventana, min_periods=int(0.9 * ventana))
    quieta = (r.max() - r.min()).round(6) < cambio_minimo
    if condicion is not None:
        quieta &= condicion
    # extiende la marca hacia atrás para cubrir toda la ventana, no solo su último minuto
    return quieta[::-1].rolling(ventana, min_periods=1).max()[::-1].fillna(0).astype(bool)


# ---------- Geometría solar (para la radiación) ----------

def geometria_solar(indice_local, lat, lon, utc_local=-5):
    """Coseno del ángulo cenital y constante solar corregida por distancia Tierra-Sol (Spencer, 1971)."""
    utc = indice_local - pd.Timedelta(hours=utc_local)
    doy = utc.day_of_year.to_numpy()
    hora = utc.hour.to_numpy() + utc.minute.to_numpy() / 60
    g = 2 * np.pi / 365 * (doy - 1 + (hora - 12) / 24)
    decl = (0.006918 - 0.399912 * np.cos(g) + 0.070257 * np.sin(g) - 0.006758 * np.cos(2 * g)
            + 0.000907 * np.sin(2 * g) - 0.002697 * np.cos(3 * g) + 0.00148 * np.sin(3 * g))
    ecuacion_tiempo = 229.18 * (0.000075 + 0.001868 * np.cos(g) - 0.032077 * np.sin(g)
                                - 0.014615 * np.cos(2 * g) - 0.040849 * np.sin(2 * g))
    angulo_horario = np.deg2rad((hora * 60 + ecuacion_tiempo + 4 * lon) / 4 - 180)
    phi = np.deg2rad(lat)
    cos_z = np.sin(phi) * np.sin(decl) + np.cos(phi) * np.cos(decl) * np.cos(angulo_horario)
    sa = 1361 * (1.00011 + 0.034221 * np.cos(g) + 0.00128 * np.sin(g) + 0.000719 * np.cos(2 * g)
                 + 0.000077 * np.sin(2 * g))
    return pd.DataFrame({"cos_z": cos_z, "elevacion": np.rad2deg(np.arcsin(np.clip(cos_z, -1, 1))), "sa": sa},
                        index=indice_local)


def limites_bsrn(sol):
    """Límites BSRN para irradiancia global (Long y Dutton, V2.0; recogidos en Long y Shi, 2008):
    físicamente posible y extremadamente raro."""
    mu = sol["cos_z"].clip(lower=0)
    return sol["sa"] * 1.5 * mu ** 1.2 + 100, sol["sa"] * 1.2 * mu ** 1.2 + 50


# ---------- Evaluación por estación ----------

def _pruebas_367(d, contexto):
    u = UMBRALES
    p = []
    for v in ESTACIONES["367"]["variables"]:
        p.append((v, "rango_fisico", fuera_de_rango(d[v], *u["rango_fisico"][v]), MALO))
        if v in u["rango_clima"]:
            p.append((v, "rango_clima", fuera_de_rango(d[v], *u["rango_clima"][v]), SOSPECHOSO))
        if v in u["salto"]:
            p.append((v, "salto", salto(d[v], u["salto"][v]), SOSPECHOSO))
        if v in u["salto_malo"]:
            p.append((v, "salto", salto(d[v], u["salto_malo"][v]), MALO))
    # OMM, notas de la p. 203: humedad solo bajo 95 % y viento solo con media de 10 min sobre 0,1 m/s
    con_viento = d["vv"].rolling(10, min_periods=10).mean().rolling(60, min_periods=60).min() > 0.1
    for v, (ventana, cambio) in u["persistencia"].items():
        if v not in d:
            continue
        condicion = {"h": d["h"] < 95, "vv": con_viento, "dv": con_viento}.get(v)  # niebla y calma sí son quietas
        quieta = persistencia(d[v], ventana, cambio, condicion)
        if v == "dv":  # una veleta trabada en el norte oscila entre 359 y 0: se prueba también girada 180°
            quieta |= persistencia((d[v] + 180) % 360, ventana, cambio, condicion)
        p.append((v, "persistencia", quieta, SOSPECHOSO))
    p.append(("vv_max", "rafaga_menor", d["vv_max"] < d["vv"], MALO))
    # Coherencia interna de la OMM (p. 203): sin viento la dirección es 0. La otra mitad de la regla (con viento
    # no puede ser 0) no se aplica porque este registrador escribe el norte como 0 (dv va de 0 a 359)
    p.append(("dv", "direccion_sin_viento", (d["vv"] == 0) & (d["dv"] > 0), SOSPECHOSO))
    # Fallas del anemómetro vistas en el EDA (código 1567 de SIATA): las cuatro columnas en 0 a la vez son un
    # sensor que no reporta, y un viento fuerte con ráfaga casi igual a la media es una lectura trabada.
    # El factor de ráfaga típico de 1 minuto es mayor que 1,1 (calibrado con estos datos, ver notebook 01)
    cuadruple_cero = (d[["vv", "vv_max", "dv", "dv_max"]] == 0).all(axis=1)
    rafaga_trabada = (d["vv"] >= 5) & (d["vv_max"] < 1.1 * d["vv"])
    for v in ("vv", "vv_max", "dv", "dv_max"):
        p.append((v, "viento_cuadruple_cero", cuadruple_cero, MALO))
    for v in ("vv", "vv_max"):
        p.append((v, "factor_rafaga", rafaga_trabada, SOSPECHOSO))
    if contexto and "35" in contexto:
        horas = pd.DataFrame({"p": agregar(d["p"], "p", cobertura_min=0.9),
                              "p1": agregar(contexto["35"]["p1"], "p1", cobertura_min=0.9),
                              "p2": agregar(contexto["35"]["p2"], "p2", cobertura_min=0.9)})
        no_registro = (horas["p1"] >= u["p_367_vs_35_mm"]) & (horas["p2"] >= u["p_367_vs_35_mm"]) & (horas["p"] == 0)
        sin_respaldo = (horas["p"] >= u["p_367_sin_respaldo_mm"]) & (horas["p1"] == 0) & (horas["p2"] == 0)
        a_minutos = lambda h: h.reindex(d.index, method="ffill").fillna(False).astype(bool)
        p.append(("p", "lluvia_no_registrada", a_minutos(no_registro), SOSPECHOSO))
        p.append(("p", "lluvia_sin_respaldo", a_minutos(sin_respaldo) & (d["p"] > 0), SOSPECHOSO))
    return p


def _pruebas_803(d, contexto):
    u = UMBRALES
    n = d["nivel"]
    # Los niveles negativos no se marcan: son el caudal base bajo un cero mal documentado (configuración)
    p = [("nivel", "rango_clima", fuera_de_rango(n, *u["rango_clima"]["nivel"]), SOSPECHOSO),
         ("nivel", "salto", salto(n, u["salto"]["nivel"]), SOSPECHOSO),
         ("nivel", "persistencia", persistencia(n, *u["persistencia"]["nivel"]), SOSPECHOSO)]
    if contexto and "35" in contexto:
        # sin dato de lluvia (menos del 95 % de las 3 h) no se puede afirmar que fue seco: no se marca
        lluvia = contexto["35"][["p1", "p2"]].max(axis=1).rolling("3h", min_periods=171).sum().reindex(d.index)
        # el percentil 25 no lo mueven mesetas de horas; al inicio del periodo basta con 3 h de historia, como en la lluvia
        base = n.rolling("7D", min_periods=171).quantile(0.25)
        subida = n - base
        seco = lluvia < u["lluvia_previa_mm"]
        sosp, malo = u["nivel_pico_sin_lluvia_cm"]
        p.append(("nivel", "pico_sin_lluvia", seco & (subida > sosp) & (subida <= malo), SOSPECHOSO))
        p.append(("nivel", "pico_sin_lluvia", seco & (subida > malo), MALO))
        # sin lluvia de referencia o sin línea base la prueba no corre: el dato queda "no evaluado" (2), no "bueno"
        p.append(("nivel", "sin_contexto", lluvia.isna() | base.isna(), NO_EVALUADO))
    return p


def _pruebas_6004(d, contexto):
    u = UMBRALES
    r = d["radiacion"]
    est = ESTACIONES["6004"]
    sol = geometria_solar(d.index, est["lat"], est["lon"])
    posible, raro = limites_bsrn(sol)
    de_dia = sol["elevacion"] > 10
    return [("radiacion", "rango_fisico", r < u["rango_fisico"]["radiacion"][0], MALO),
            ("radiacion", "radiacion_imposible", r > posible, MALO),
            ("radiacion", "radiacion_extrema", (r > raro) & (r <= posible), SOSPECHOSO),
            ("radiacion", "radiacion_nocturna", (sol["elevacion"] < -3) & (r > u["radiacion_noche_wm2"]), SOSPECHOSO),
            ("radiacion", "salto", salto(r, u["salto"]["radiacion"]), SOSPECHOSO),
            ("radiacion", "salto", salto(r, u["salto_malo"]["radiacion"]), MALO),
            ("radiacion", "persistencia", persistencia(r, *u["persistencia"]["radiacion"], de_dia), SOSPECHOSO)]


def _pruebas_35(d, contexto):
    u = UMBRALES
    p = []
    horas = pd.DataFrame({v: agregar(d[v], v, cobertura_min=0.9) for v in ("p1", "p2")})
    tolerancia = np.maximum(u["p1_p2_hora_mm"], u["p1_p2_hora_fraccion"] * horas.max(axis=1))
    difieren = (horas["p1"] - horas["p2"]).abs() > tolerancia
    difieren_min = difieren.reindex(d.index, method="ffill").fillna(False).astype(bool)
    for v in ("p1", "p2"):
        p.append((v, "rango_fisico", fuera_de_rango(d[v], *u["rango_fisico"][v]), MALO))
        p.append((v, "rango_clima", fuera_de_rango(d[v], *u["rango_clima"][v]), SOSPECHOSO))
        vueltas = d[v] / 0.254
        p.append((v, "resolucion", (vueltas - vueltas.round()).abs() > 0.01, SOSPECHOSO))
        p.append((v, "p1_p2_difieren", difieren_min & (d[v] > 0), SOSPECHOSO))
    return p


PRUEBAS = {"367": _pruebas_367, "803": _pruebas_803, "6004": _pruebas_6004, "35": _pruebas_35}


def evaluar(d, codigo, contexto=None):
    """Corre las pruebas de una estación regularizada (ver datos.regularizar).

    contexto: dict con otras estaciones regularizadas para las pruebas espaciales (la 35 para 367 y 803).
    Devuelve (banderas, fallas): banderas tiene una columna por variable con el código 1, 2, 3, 4 o 9;
    fallas es la traza larga (fecha_hora, variable, prueba, bandera) de cada prueba que falló.
    """
    variables = ESTACIONES[codigo]["variables"]
    banderas = pd.DataFrame(BUENO, index=d.index, columns=variables)
    trazas = []
    for v, prueba, falla, severidad in PRUEBAS[codigo](d, contexto):
        falla = falla.reindex(d.index, fill_value=False).astype(bool) & d[v].notna()
        banderas.loc[falla, v] = np.maximum(banderas.loc[falla, v], severidad)
        if falla.any():
            trazas.append(pd.DataFrame({"fecha_hora": d.index[falla], "variable": v, "prueba": prueba,
                                        "bandera": severidad}))
    for v in variables:
        hueco = d[v].isna()
        banderas.loc[hueco, v] = FALTANTE
        if hueco.any():
            trazas.append(pd.DataFrame({"fecha_hora": d.index[hueco], "variable": v, "prueba": "hueco",
                                        "bandera": FALTANTE}))
    fallas = (pd.concat(trazas, ignore_index=True) if trazas
              else pd.DataFrame(columns=["fecha_hora", "variable", "prueba", "bandera"]))
    fallas.insert(0, "codigo", codigo)
    fallas["version_reglas"] = VERSION_REGLAS
    return banderas, fallas


def bandera_registro(banderas):
    """Bandera de la fila completa (la columna calidad de SIATA es por fila): la peor entre variables con dato."""
    con_dato = banderas.where(banderas != FALTANTE)
    peor = con_dato.max(axis=1)
    return peor.fillna(FALTANTE).astype(int)
