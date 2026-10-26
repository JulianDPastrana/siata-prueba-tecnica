"""Pruebas de la Tarea B con series sintéticas: sin fuga de información, MASE y preprocesamiento."""
import numpy as np
import pandas as pd
import pytest

from siata import series as S

H = 24
RAPIDO = dict(max_iter=15, max_leaf_nodes=7, min_samples_leaf=10)


def sintetica(dias=20, semilla=0):
    """Ciclo diurno más ruido normal."""
    rng = np.random.default_rng(semilla)
    idx = pd.date_range("2026-01-01", periods=24 * dias, freq="h")
    y = 18 + 4 * np.sin(2 * np.pi * (idx.hour - 8) / 24) + rng.normal(0, 0.5, len(idx))
    return pd.Series(y, index=idx)


def lluvia_sintetica(dias=20, semilla=1):
    rng = np.random.default_rng(semilla)
    idx = pd.date_range("2026-01-01", periods=24 * dias, freq="h")
    llueve = rng.random(len(idx)) < np.where((idx.hour >= 14) & (idx.hour <= 18), 0.3, 0.03)
    return pd.Series(np.where(llueve, rng.gamma(1.5, 1.5, len(idx)).round(1) + 0.3, 0.0), index=idx)


def futuro_alterado(s, origen):
    """Misma serie con todo lo posterior al origen reemplazado por basura (y un hueco)."""
    s2 = s.copy()
    despues = s2.index > origen
    s2[despues] = 1000.0 + np.arange(despues.sum())
    s2[s2.index[despues][:2]] = np.nan
    return s2


def test_origenes_dejan_horizonte_y_tienen_dato_en_el_origen():
    s = sintetica()
    sin_dato = s.index[-1] - (H + 25) * s.index.freq  # segundo origen de la rejilla, contando desde el final
    s[sin_dato] = np.nan
    os_ = S.origenes(s, H, 10, 25)
    assert len(os_) == 9 and sin_dato not in os_
    assert (os_ + H * s.index.freq <= s.last_valid_index()).all()


def test_variables_rezagadas_no_ven_el_futuro():
    s = sintetica()
    o = s.index[300]
    M = S.matriz_directa(s, s, H, [0, 1, 2, 23], 24, exog=S.lluvia_reciente(s, [3]))
    M2 = S.matriz_directa(futuro_alterado(s, o), futuro_alterado(s, o), H, [0, 1, 2, 23], 24,
                          exog=S.lluvia_reciente(futuro_alterado(s, o), [3]))
    hasta = M["t"] <= o
    variables = [c for c in M.columns if c != "y"]
    pd.testing.assert_frame_equal(M.loc[hasta, variables], M2.loc[hasta, variables])
    # el objetivo solo coincide si su fecha también es <= origen: por eso el entrenamiento filtra por fecha_hora
    conocido = M["fecha_hora"] <= o
    pd.testing.assert_series_equal(M.loc[conocido, "y"], M2.loc[conocido, "y"])


def test_rezago_estacional_exige_horizonte_menor_que_el_periodo():
    with pytest.raises(AssertionError):
        S.matriz_directa(sintetica(), sintetica(), 30, [0], 24)


@pytest.mark.parametrize("modelo", ["persistencia", "estacional", "ets", "ets_cada", "arima", "hgb", "hgb_incremento"])
def test_pronostico_no_cambia_si_cambia_el_futuro(modelo):
    s = sintetica()
    s.iloc[[297, 298]] = np.nan  # hueco corto que se interpola justo antes del origen
    o = s.index[300]

    def pronostico(obj):
        entrada, _ = S.rellenar_cortos(obj, 3)
        if modelo == "persistencia":
            return S.persistencia(entrada, [o], H)
        if modelo == "estacional":
            return S.estacional_ingenua(entrada, [o], H, 24)
        if modelo == "ets":
            return S.ets(entrada, [o], H, 24)
        if modelo == "ets_cada":  # el segundo origen reutiliza los parámetros del primero (smooth)
            return S.ets(entrada, [o - 24 * entrada.index.freq, o], H, 24, cada=2)
        if modelo == "arima":
            fourier = pd.DataFrame({"s": np.sin(2 * np.pi * obj.index.hour / 24),
                                    "c": np.cos(2 * np.pi * obj.index.hour / 24)}, index=obj.index)
            return S.arima(entrada, [o], H, (1, 0, 0), exog=fourier)
        M = S.matriz_directa(entrada, obj, H, [0, 1, 23], 24)
        return S.hgb(M, [o], params=RAPIDO, incremento=modelo == "hgb_incremento")

    pd.testing.assert_frame_equal(pronostico(s), pronostico(futuro_alterado(s, o)))


@pytest.mark.parametrize("modelo", ["dos_partes", "tsb", "climatologia"])
def test_pronostico_de_lluvia_no_cambia_si_cambia_el_futuro(modelo):
    s = lluvia_sintetica()
    o = s.index[300]

    def pronostico(obj):
        if modelo == "tsb":
            return S.tsb(obj, [o], H)
        if modelo == "climatologia":
            return S.climatologia_horaria(obj, [o], H)
        M = S.matriz_directa(obj, obj, H, [0, 1], 24, exog=S.lluvia_reciente(obj, [3, 6]))
        return S.dos_partes(M, [o], params=RAPIDO)

    pd.testing.assert_frame_equal(pronostico(s), pronostico(futuro_alterado(s, o)))


def test_mase_caso_conocido():
    entrena = pd.Series([1.0, 2, 3, 4, 5], index=pd.date_range("2026-01-01", periods=5, freq="h"))
    escala = S.escala_mase(entrena, entrena.index[-1], 1)  # |diferencias| = 1, 1, 1, 1
    assert escala == 1.0
    assert S.mase([1.0, 2.0], [escala, escala]) == 1.5  # errores 1 y 2 sobre escala 1
    estacional = pd.Series([1.0, 5, 2, 6, 4, 8], index=pd.date_range("2026-01-01", periods=6, freq="h"))
    assert S.escala_mase(estacional, estacional.index[-1], 2) == pytest.approx(1.5)  # |1|, |1|, |2|, |2|


def test_escala_mase_solo_usa_el_entrenamiento():
    s = pd.Series([0.0, 1, 0, 1, 50, 0], index=pd.date_range("2026-01-01", periods=6, freq="h"))
    assert S.escala_mase(s, s.index[3], 1) == 1.0  # el 50 está después del origen


def test_rellenar_cortos_no_toca_huecos_largos_ni_extremos():
    s = pd.Series([np.nan, 1.0, np.nan, np.nan, 4, 5, np.nan, np.nan, np.nan, np.nan, 10, np.nan],
                  index=pd.date_range("2026-01-01", periods=12, freq="h"))
    entrada, imputado = S.rellenar_cortos(s, 3)
    assert entrada.iloc[2:4].tolist() == [2.0, 3.0]
    assert entrada.iloc[6:10].isna().all() and np.isnan(entrada.iloc[0]) and np.isnan(entrada.iloc[-1])
    assert imputado.tolist() == [False, False, True, True] + [False] * 8
    assert s.iloc[2:4].isna().all()  # la serie original no cambia


def test_brier_y_muestra_comun():
    assert S.brier([1.0, 0.0, 0.5], [True, False, True]) == pytest.approx(0.25 / 3)
    f = pd.date_range("2026-01-01 01:00", periods=2, freq="h")
    p = pd.DataFrame({"modelo": ["a", "a", "b", "b"], "origen": f[0], "fecha_hora": list(f) * 2,
                      "real": [1.0, 2.0, 1.0, 2.0], "pred": [1.0, 2.0, 1.0, np.nan]})
    comun = S.muestra_comun(p)
    assert len(comun) == 2 and (comun["fecha_hora"] == f[0]).all()  # la fila sin pronóstico de b sale para todos


def test_tsb_actualiza_tamano_solo_cuando_llueve():
    p, z = S.tsb_filtro([0.0, 2.0, 0.0, np.nan, 0.0, 4.0], 0.5, 0.5, umbral=0.254)
    assert z[0] == 3.0 and z[1] == 2.5 and z[2] == z[3] == z[4] == 2.5 and z[5] == 3.25
    assert p[1] > p[0] and p[2] < p[1] and p[3] == p[2]  # el NaN no cambia el estado


def test_conformal_solo_usa_resultados_conocidos_en_el_origen():
    f = pd.date_range("2026-01-01", periods=200, freq="h")
    rng = np.random.default_rng(2)
    filas = []
    for i, o in enumerate(f[::4][:40]):
        fechas = pd.date_range(o + pd.Timedelta("1h"), periods=4, freq="h")
        filas.append(pd.DataFrame({"origen": o, "fecha_hora": fechas, "horizonte": range(1, 5), "pred": 0.0,
                                   "inf80": -1.0, "sup80": 1.0, "real": rng.normal(0, 2, 4)}))
    p = pd.concat(filas, ignore_index=True)
    o = p["origen"].unique()[30]
    p2 = p.copy()
    p2.loc[p2["fecha_hora"] > o, "real"] = 99.0
    a, b = S.conformal(p, min_n=8), S.conformal(p2, min_n=8)
    pd.testing.assert_frame_equal(a.loc[a["origen"] <= o, ["inf80", "sup80"]], b.loc[b["origen"] <= o, ["inf80", "sup80"]])
    assert a.loc[a["origen"] == p["origen"].iloc[0], "inf80"].isna().all()  # sin historia no hay ajuste
    assert (a.loc[a["origen"] == o, "sup80"] > 1.0).all()  # real con desviación 2 y banda de +-1: debe ampliar


def test_conformal_respeta_la_mascara_aunque_las_filas_lleguen_desordenadas():
    f = pd.date_range("2026-01-01", periods=120, freq="h")
    p = pd.concat([pd.DataFrame({"origen": o, "fecha_hora": pd.date_range(o + pd.Timedelta("1h"), periods=2, freq="h"),
                                 "horizonte": [1, 2], "pred": 0.0, "inf80": -1.0, "sup80": 1.0, "real": [5.0, 0.0]})
                   for o in f[::2][:40]], ignore_index=True)
    usar = (p["horizonte"] == 1).to_numpy()
    orden = np.random.default_rng(0).permutation(len(p))
    a = S.conformal(p, min_n=8, usar=usar)
    b = S.conformal(p.iloc[orden], min_n=8, usar=usar[orden])
    pd.testing.assert_frame_equal(a, b)
    assert (a.loc[a["horizonte"] == 2, "sup80"] == 1.0).all()  # las filas fuera de la máscara no se tocan
