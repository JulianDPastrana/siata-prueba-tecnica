"""Correlaciones y relaciones entre variables y estaciones (Tarea D).

Se trabaja con los datos de bandera buena (1) del control propio. Las funciones reciben pandas.Series con
índice de tiempo regular; los NaN (huecos o datos no buenos) se descartan por pares antes de cada cálculo.
"""
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.feature_selection import mutual_info_regression

from . import calidad as Q
from .datos import DIR_SALIDAS, ESTACIONES, media_circular


def buenos(codigo):
    """Variables minutales de una estación con NaN donde la bandera propia no es buena (1)."""
    d = pd.read_parquet(DIR_SALIDAS / f"minutal_{codigo}.parquet")
    variables = ESTACIONES[codigo]["variables"]
    return d[variables].where(d[[f"b_{v}" for v in variables]].eq(Q.BUENO).to_numpy())


# ---------- Desestacionalización ----------

def ciclo_sin_futuro(s, dias=30, minimo=7):
    """Ciclo diario medio de s: para cada hora (o minuto) del día, la media de esa misma hora en los `dias` días
    anteriores. No usa el propio día ni el futuro. s debe tener índice regular (una fila por día y hora del día);
    los primeros `minimo` días quedan en NaN.
    """
    hora_del_dia = s.index.hour * 60 + s.index.minute
    return s.groupby(hora_del_dia).transform(lambda g: g.shift(1).rolling(dias, min_periods=minimo).mean())


def versiones(s, dias=30):
    """Serie cruda, desestacionalizada (anomalía frente al ciclo diario sin futuro) y diferenciada (primera diferencia)."""
    return {"cruda": s, "desestacionalizada": s - ciclo_sin_futuro(s, dias), "diferenciada": s.diff()}


# ---------- Medidas de asociación ----------

def _pares(x, y):
    d = pd.concat([x, y], axis=1).dropna().to_numpy(dtype=float)
    return d[:, 0], d[:, 1]


def _valor(a, b, metodo, semilla=0, max_n=20000):
    if metodo == "pearson":
        return float(np.corrcoef(a, b)[0, 1])
    if metodo == "spearman":  # Pearson sobre rangos (empates con rango medio)
        return float(np.corrcoef(stats.rankdata(a), stats.rankdata(b))[0, 1])
    if metodo == "info_mutua":
        if len(a) > max_n:  # submuestra: con todas las filas el estimador k-NN tarda minutos; la MI no depende del orden
            i = np.random.default_rng(semilla).choice(len(a), max_n, replace=False)
            a, b = a[i], b[i]
        mi = mutual_info_regression(a.reshape(-1, 1), b, random_state=semilla)[0]
        # coeficiente informacional de Linfoot (1957): igual a |Pearson| si la relación es normal bivariada
        return float(np.sqrt(1 - np.exp(-2 * max(mi, 0.0))))
    if metodo == "circular":  # Jammalamadaka y SenGupta (2001), ángulos en grados
        sa, sb = np.sin(np.deg2rad(a - media_circular(a))), np.sin(np.deg2rad(b - media_circular(b)))
        return float((sa * sb).sum() / np.sqrt((sa ** 2).sum() * (sb ** 2).sum()))
    raise ValueError(f"metodo desconocido: {metodo}")


def correlacion(x, y, metodo="pearson"):
    """(valor, n) con los pares sin NaN.

    metodo: 'pearson', 'spearman', 'info_mutua' (información mutua llevada a un coeficiente de 0 a 1) o 'circular',
    para direcciones en grados: Pearson sobre grados falla en el corte 0/360 y depende de dónde se ponga el cero.
    """
    a, b = _pares(x, y)
    return _valor(a, b, metodo), len(a)


def diferencia_angular(a, b):
    """Diferencia más corta entre dos direcciones en grados, de 0 a 180 (359° y 1° están a 2°)."""
    return np.abs((np.asarray(a, dtype=float) - np.asarray(b, dtype=float) + 180) % 360 - 180)


def correlacion_cruzada(x, y, rezagos_min, metodo="pearson"):
    """Correlación entre x(t) e y(t + k) para cada rezago k en minutos. Rezago positivo: y va después de x.

    x e y deben compartir el mismo índice regular; k tiene que ser múltiplo del paso de la serie.
    """
    paso = (x.index[1] - x.index[0]) / pd.Timedelta("1min")
    valores = {}
    for k in rezagos_min:
        assert k % paso == 0, f"el rezago {k} min no es múltiplo del paso ({paso} min)"
        valores[k] = correlacion(x, y.shift(-int(k // paso)), metodo)[0]
    return pd.Series(valores, name="valor").rename_axis("rezago_min")


def ic_bootstrap_bloques(x, y, bloque, metodo="pearson", n=500, semilla=0):
    """Intervalo del 95 % por bootstrap de bloques móviles (Künsch, 1989).

    Remuestrea tramos contiguos de `bloque` pasos con los pares (x, y) juntos, así conserva la autocorrelación.
    El bootstrap clásico supone datos independientes y, con series autocorrelacionadas, da intervalos muy estrechos.
    """
    d = pd.concat([x, y], axis=1).to_numpy(dtype=float)
    m = len(d)
    k = -(-m // bloque)
    rng = np.random.default_rng(semilla)
    valores = np.empty(n)
    for i in range(n):
        idx = (rng.integers(0, m - bloque + 1, k)[:, None] + np.arange(bloque)).ravel()[:m]
        a, b = d[idx, 0], d[idx, 1]
        ok = ~np.isnan(a) & ~np.isnan(b)
        valores[i] = _valor(a[ok], b[ok], metodo)
    return tuple(np.percentile(valores, [2.5, 97.5]))


def spearman_parcial(d, x, y, z):
    """Spearman entre las columnas x e y de d quitando el efecto de z (correlación parcial sobre rangos)."""
    r = d[[x, y, z]].dropna().rank().corr()  # la misma muestra para los tres pares
    return (r.loc[x, y] - r.loc[x, z] * r.loc[y, z]) / np.sqrt((1 - r.loc[x, z] ** 2) * (1 - r.loc[y, z] ** 2))


# ---------- Eventos de lluvia y respuesta del nivel (hipótesis D5) ----------

def eventos_lluvia(lluvia, pausa_min=60, minimo_mm=5.0):
    """Eventos en una serie minutal de lluvia (mm por minuto): tramos separados por al menos `pausa_min` minutos
    secos y con al menos `minimo_mm`. Devuelve inicio, fin, total, duración, intensidades máximas en 10, 30 y
    60 min (mm acumulados en la ventana), minutos sin dato dentro del evento y lluvia de las 24 h previas.
    """
    con_lluvia = lluvia.index[lluvia.fillna(0) > 0]
    if len(con_lluvia) == 0:
        return pd.DataFrame()
    grupo = np.cumsum(np.r_[True, np.diff(con_lluvia) > pd.Timedelta(minutes=pausa_min)])
    filas = []
    for g in np.unique(grupo):
        inicio, fin = con_lluvia[grupo == g][[0, -1]]
        s = lluvia.loc[inicio:fin]
        if s.sum() < minimo_mm:
            continue
        acum = {f"i{w}": s.rolling(w, min_periods=1).sum().max() for w in (10, 30, 60)}
        filas.append({"inicio": inicio, "fin": fin, "total": s.sum(), "duracion_min": len(s), **acum,
                      "sin_dato_min": int(s.isna().sum()),
                      "previa_24h": lluvia.loc[inicio - pd.Timedelta("24h"):inicio - pd.Timedelta("1min")].sum()})
    return pd.DataFrame(filas)


def respuesta_nivel(eventos, nivel, despues_min=60, base_min=60):
    """Subida del nivel (cm) y minutos del inicio al pico, para cada evento (columnas inicio y fin).

    Subida = máximo de la mediana móvil de 3 min entre el inicio y `despues_min` después del fin, menos la mediana
    de los `base_min` minutos previos al inicio. La mediana móvil evita que un pico de un solo minuto sea el máximo.
    """
    suave = nivel.rolling(3, center=True, min_periods=2).median()
    subida, al_pico = [], []
    for inicio, fin in zip(eventos["inicio"], eventos["fin"]):
        base = nivel.loc[inicio - pd.Timedelta(minutes=base_min):inicio - pd.Timedelta("1min")].median()
        ventana = suave.loc[inicio:fin + pd.Timedelta(minutes=despues_min)].dropna()
        ok = len(ventana) > 0 and not np.isnan(base)
        subida.append(ventana.max() - base if ok else np.nan)
        al_pico.append((ventana.idxmax() - inicio) / pd.Timedelta("1min") if ok else np.nan)
    return pd.DataFrame({"subida_cm": subida, "min_al_pico": al_pico}, index=eventos.index)


def subida_en_seco(lluvia, nivel, duracion_min, n=500, semilla=0, despues_min=60, base_min=60):
    """La misma subida de respuesta_nivel calculada en `n` ventanas al azar sin lluvia (ni dato faltante de lluvia)
    durante la base, el falso evento y el tiempo posterior. Da el piso de ruido del nivel: lo que sube sin llover.
    """
    largo = base_min + duracion_min + despues_min
    seco = lluvia.fillna(1).rolling(largo).sum() == 0  # un minuto sin dato de lluvia no cuenta como seco
    finales = lluvia.index[seco.to_numpy()]
    elegidos = np.random.default_rng(semilla).choice(finales, size=min(n, len(finales)), replace=False)
    inicio = pd.DatetimeIndex(elegidos) - pd.Timedelta(minutes=duracion_min + despues_min - 1)
    falsos = pd.DataFrame({"inicio": inicio, "fin": inicio + pd.Timedelta(minutes=duracion_min - 1)})
    return respuesta_nivel(falsos, nivel, despues_min, base_min)["subida_cm"]
