"""Pruebas de los métodos de anomalías con series sintéticas pequeñas (no usan los datos de la prueba)."""
import numpy as np
import pandas as pd
import pytest

from siata import anomalias as A


def horas(n, inicio="2026-01-01"):
    return pd.date_range(inicio, periods=n, freq="h")


def test_etiqueta_debil_trata_1_y_2_como_confiables_y_nan_como_sin_opinion():
    c = pd.Series([1, 2, 151, 1582, np.nan])
    assert A.etiqueta_debil(c).tolist() == [False, False, True, True, False]


def test_puntaje_robusto_no_se_deja_arrastrar_por_el_atipico():
    z = A.puntaje_robusto([1, 2, 3, 4, 100])
    assert z.iloc[2] == 0
    assert z.iloc[4] == pytest.approx(97 / 1.4826)


def test_puntaje_robusto_por_grupo_y_mad_cero():
    # el grupo b tiene 10 veces la dispersión de a: con escala por grupo, 3 en a pesa lo mismo que 30 en b
    x = [0, 1, 2, 3, 0, 10, 20, 30, 5, 5, 5]
    g = ["a"] * 4 + ["b"] * 4 + ["c"] * 3
    z = A.puntaje_robusto(x, g)
    assert z.iloc[3] == pytest.approx(z.iloc[7])
    assert z.iloc[8:].isna().all()  # MAD cero: sin puntaje, no infinito


def test_stl_encuentra_un_pico_y_no_evalua_los_huecos():
    rng = np.random.default_rng(0)
    idx = horas(24 * 150)  # como los datos: unos 150 valores por hora del día para estimar la escala
    s = pd.Series(20 + 4 * np.sin(2 * np.pi * idx.hour / 24) + rng.normal(0, 0.2, len(idx)), index=idx)
    s.iloc[500] += 5
    s.iloc[700:705] = np.nan
    r = A.anomalias_stl(s)
    assert r["anomalia"].iloc[500] and r["z"].abs().idxmax() == idx[500]
    assert r["anomalia"].mean() < 0.005  # con ruido normal, |z| > 3,5 es raro
    assert r["z"].iloc[700:705].isna().all() and not r["anomalia"].iloc[700:705].any()


def test_isolation_forest_marca_la_hora_imposible():
    rng = np.random.default_rng(1)
    idx = horas(24 * 30)
    H = pd.DataFrame({"t": 20 + 4 * np.sin(2 * np.pi * idx.hour / 24) + rng.normal(0, 0.3, len(idx)),
                      "h": 80 + rng.normal(0, 2, len(idx))}, index=idx)
    H.iloc[300] = [45.0, 10.0]
    r = A.isolation_forest(H, contaminacion=0.005)
    assert r["anomalia"].iloc[300]
    assert r["puntaje"].idxmax() in idx[299:302]  # la hora rara o su cambio


def test_segmentacion_binaria_encuentra_el_escalon_y_no_inventa_cambios():
    rng = np.random.default_rng(2)
    idx = pd.date_range("2026-01-01", periods=100, freq="D")
    ruido = pd.Series(rng.normal(0, 0.3, 100), index=idx)
    escalon = ruido + np.r_[np.zeros(60), np.full(40, 2.0)]
    seg = A.segmentacion_binaria(escalon)
    assert len(seg) == 2 and seg["inicio"].iloc[1] == idx[60]
    assert len(A.segmentacion_binaria(ruido)) == 1


def test_precision_exhaustividad():
    r = A.precision_exhaustividad([1, 1, 0, 0, 1], [1, 0, 0, 1, 1])
    assert r["precision"] == pytest.approx(2 / 3) and r["exhaustividad"] == pytest.approx(2 / 3)
    assert np.isnan(A.precision_exhaustividad([0, 0], [1, 0])["precision"])


def test_eventos_une_contiguos_respeta_tolerancia_y_grupos():
    t = pd.to_datetime(["2026-01-01 00:00", "2026-01-01 00:01", "2026-01-01 00:05", "2026-01-01 00:00"])
    m = pd.DataFrame({"codigo": ["367", "367", "367", "803"], "variable": ["t", "t", "t", "nivel"],
                      "inicio": t, "fin": t, "regla": ["salto", "persistencia", "salto", "salto"],
                      "bandera": [3, 4, 3, 3]})
    ev = A.eventos(m)
    t367 = ev[ev["codigo"] == "367"]
    assert len(t367) == 2 and t367["duracion_min"].tolist() == [2, 1]
    assert t367["regla"].iloc[0] == "persistencia+salto" and t367["bandera"].iloc[0] == 4
    assert len(A.eventos(m, tolerancia="5min")) == 2  # la marca de las 00:05 se une a la primera


def test_tipo_evento():
    assert A.tipo_evento("hueco", "nivel") == "falla de comunicación"
    assert A.tipo_evento("hueco", "p1", centinela=True) == "falla de sensor"
    assert A.tipo_evento("persistencia", "t", valores_distintos=7) == "evento físico real"
    assert A.tipo_evento("persistencia", "t", valores_distintos=1) == "falla de sensor"
    assert A.tipo_evento("salto+stl_mad", "nivel", lluvia_mm=40) == "evento físico real"
    assert A.tipo_evento("pico_sin_lluvia+salto", "nivel", lluvia_mm=40) == "falla de sensor"  # gana la falla
    assert A.tipo_evento("salto", "radiacion") == "evento físico real"
    assert A.tipo_evento("direccion_sin_viento", "dv") == "problema de configuración"


def test_severidad_ligada_a_las_alertas():
    assert A.severidad("falla de sensor", "nivel", 30, bandera=4) == "alta"
    assert A.severidad("falla de sensor", "nivel", 30, bandera=3) == "media"
    assert A.severidad("falla de comunicación", "radiacion", 1752) == "media"
    assert A.severidad("falla de sensor", "pr", 3) == "baja"
    assert A.severidad("evento físico real", "p1+p2", 70) == "alta"
    assert A.severidad("evento físico real", "radiacion", 5) == "baja"
