"""Pruebas de siata.relaciones con series sintéticas (no usan los datos de la prueba)."""
import numpy as np
import pandas as pd
import pytest

from siata import relaciones as R


def horaria(valores, inicio="2026-01-01 00:00", freq="h"):
    return pd.Series(valores, index=pd.date_range(inicio, periods=len(valores), freq=freq), dtype=float)


def test_correlacion_circular_resiste_el_corte_de_0_360():
    rng = np.random.default_rng(1)
    a = rng.normal(0, 20, 2000) % 360  # vientos alrededor del norte: muchos valores cerca de 0 y de 360
    b = (a + rng.normal(0, 5, 2000)) % 360
    circular, n = R.correlacion(pd.Series(a), pd.Series(b), "circular")
    assert n == 2000 and circular > 0.9
    assert R.correlacion(pd.Series(a), pd.Series(b))[0] < circular  # Pearson sobre grados se equivoca aquí
    # no depende de dónde se ponga el cero
    girado = R.correlacion(pd.Series((a + 137) % 360), pd.Series((b + 137) % 360), "circular")[0]
    assert girado == pytest.approx(circular)


def test_diferencia_angular_toma_el_camino_corto():
    assert R.diferencia_angular([359, 10, 180], [1, 350, 0]).tolist() == [2, 20, 180]


def test_correlacion_cruzada_encuentra_el_rezago():
    rng = np.random.default_rng(2)
    x = horaria(rng.normal(size=500), freq="10min")
    y = x.shift(3)  # y repite a x 30 minutos después
    cc = R.correlacion_cruzada(x, y, range(0, 70, 10))
    assert cc.idxmax() == 30 and cc[30] == pytest.approx(1)


def test_ciclo_sin_futuro_no_mira_el_futuro_ni_el_propio_dia():
    rng = np.random.default_rng(3)
    s = horaria(10 + np.tile(np.sin(np.arange(24) / 24 * 2 * np.pi), 20) + rng.normal(0, 0.1, 480))
    ciclo = R.ciclo_sin_futuro(s, dias=5, minimo=3)
    alterada = s.copy()
    alterada.iloc[240:] += 100  # cambiar el futuro desde el día 10
    assert R.ciclo_sin_futuro(alterada, dias=5, minimo=3).iloc[:241].equals(ciclo.iloc[:241])
    assert ciclo.iloc[:72].isna().all() and ciclo.iloc[72:].notna().all()
    assert R.versiones(s, dias=10)["desestacionalizada"].iloc[200:].abs().max() < 1


def test_bootstrap_en_bloques_contiene_el_valor_verdadero():
    rng = np.random.default_rng(4)
    x = horaria(rng.normal(size=1000))
    y = 0.6 * x + 0.8 * horaria(rng.normal(size=1000))  # correlación teórica 0,6
    bajo, alto = R.ic_bootstrap_bloques(x, y, bloque=24, n=300)
    assert bajo < 0.6 < alto and alto - bajo < 0.2


def test_eventos_lluvia_separa_por_pausa_y_filtra_por_total():
    lluvia = horaria(np.zeros(600), freq="min")
    lluvia.iloc[100:110] = 1.0  # 10 mm
    lluvia.iloc[150:155] = 1.0  # 40 min después: mismo evento
    lluvia.iloc[300:302] = 1.0  # 2 mm, más de 60 min después: otro evento, menor que el mínimo
    ev = R.eventos_lluvia(lluvia, pausa_min=60, minimo_mm=5)
    assert len(ev) == 1
    assert ev.loc[0, "total"] == 15 and ev.loc[0, "duracion_min"] == 55 and ev.loc[0, "i10"] == 10


def test_respuesta_nivel_ignora_un_pico_de_un_minuto():
    nivel = horaria(np.full(300, 5.0), freq="min")
    nivel.iloc[150] = 50  # pico de un minuto (ruido)
    nivel.iloc[180:190] = 25  # crecida de 10 minutos
    ev = pd.DataFrame({"inicio": [nivel.index[120]], "fin": [nivel.index[160]]})
    r = R.respuesta_nivel(ev, nivel)
    assert r.loc[0, "subida_cm"] == 20 and r.loc[0, "min_al_pico"] == 60
