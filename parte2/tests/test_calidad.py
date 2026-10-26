"""Pruebas de las reglas de calidad con series sintéticas pequeñas (no usan los datos de la prueba)."""
import numpy as np
import pandas as pd
import pytest

from siata import calidad as Q
from siata import datos as D
from siata import indicadores as I


def serie(valores, inicio="2026-01-01 00:00"):
    return pd.Series(valores, index=pd.date_range(inicio, periods=len(valores), freq="min"), dtype=float)


def test_rango_marca_solo_lo_que_sale():
    s = serie([-1, 0, 50, 100, 101])
    assert Q.fuera_de_rango(s, 0, 100).tolist() == [True, False, False, False, True]


def test_salto_marca_los_dos_minutos_del_salto():
    s = serie([20.0, 20.1, 24.0, 24.1])
    assert Q.salto(s, 3).tolist() == [False, True, True, False]


def test_persistencia_detecta_valor_congelado_y_cubre_toda_la_ventana():
    s = serie(list(np.linspace(15, 16, 30)) + [17.5] * 60 + list(np.linspace(17, 18, 30)))
    falla = Q.persistencia(s, 60, 0.1)
    assert falla.iloc[30:90].all()
    assert not falla.iloc[:29].any() and not falla.iloc[91:].any()


def test_persistencia_respeta_la_condicion():
    s = serie([0.0] * 120)  # calma: viento en cero no es una falla
    assert not Q.persistencia(s, 60, 0.5, condicion=pd.Series(False, index=s.index)).any()


def test_congelado_48_horas_queda_sospechoso():
    # escenario del enunciado: valores plausibles pero congelados durante 48 h
    idx = pd.date_range("2026-01-01", periods=4 * 1440, freq="min")
    t = pd.Series(18 + 3 * np.sin(np.arange(len(idx)) * 2 * np.pi / 1440), index=idx)
    t.iloc[1440:4320] = 18.42
    d = pd.DataFrame({v: 1.0 for v in D.ESTACIONES["367"]["variables"]}, index=idx)
    d["t"], d["h"], d["pr"], d["vv"], d["vv_max"] = t, 80 + np.sin(np.arange(len(idx))), 816.0, 1.0, 2.0
    d["pr"] += np.sin(np.arange(len(idx)) / 30)
    banderas, fallas = Q.evaluar(d, "367")
    assert (banderas["t"].iloc[1440:4320] == Q.SOSPECHOSO).all()
    assert set(fallas.loc[fallas["variable"] == "t", "prueba"]) == {"persistencia"}


def test_rafaga_menor_que_media_es_mala():
    idx = pd.date_range("2026-01-01", periods=3, freq="min")
    d = pd.DataFrame({v: 1.0 for v in D.ESTACIONES["367"]["variables"]}, index=idx)
    d["vv"], d["vv_max"] = [1.0, 3.0, 1.0], [2.0, 2.0, 2.0]
    banderas, _ = Q.evaluar(d, "367")
    assert banderas["vv_max"].tolist() == [Q.BUENO, Q.MALO, Q.BUENO]


def test_hueco_queda_faltante_y_gana_sobre_lo_demas():
    idx = pd.date_range("2026-01-01", periods=3, freq="min")
    d = pd.DataFrame({"p1": [0.0, np.nan, 0.254], "p2": [0.0, np.nan, 0.254]}, index=idx)
    banderas, fallas = Q.evaluar(d, "35")
    assert banderas["p1"].tolist() == [Q.BUENO, Q.FALTANTE, Q.BUENO]
    assert (fallas["prueba"] == "hueco").sum() == 2


def test_resolucion_del_balancin():
    idx = pd.date_range("2026-01-01", periods=3, freq="min")
    d = pd.DataFrame({"p1": [0.254, 0.3, 0.508], "p2": [0.254, 0.254, 0.508]}, index=idx)
    banderas, _ = Q.evaluar(d, "35")
    assert banderas["p1"].tolist() == [Q.BUENO, Q.SOSPECHOSO, Q.BUENO]


def test_nivel_alto_sin_lluvia_es_malo_y_con_lluvia_no():
    idx = pd.date_range("2026-01-01", periods=10 * 1440, freq="min")
    nivel = pd.Series(3.0, index=idx)
    nivel.iloc[-60:] = 60.0  # meseta de 57 cm sobre la base
    lluvia_cero = pd.DataFrame({"p1": 0.0, "p2": 0.0}, index=idx)
    b, _ = Q.evaluar(pd.DataFrame({"nivel": nivel}), "803", {"35": lluvia_cero})
    assert (b["nivel"].iloc[-59:] == Q.MALO).all()
    con_lluvia = lluvia_cero.copy()
    con_lluvia.iloc[-120:-60] = 0.254  # 15 mm justo antes de la subida
    b, _ = Q.evaluar(pd.DataFrame({"nivel": nivel}), "803", {"35": con_lluvia})
    assert (b["nivel"].iloc[-59:] != Q.MALO).all()


def test_radiacion_de_noche_es_sospechosa_y_de_dia_no():
    idx = pd.DatetimeIndex(["2026-01-15 00:00", "2026-01-15 12:00"])  # hora local
    d = pd.DataFrame({"radiacion": [50.0, 900.0]}, index=idx)
    b, _ = Q.evaluar(d, "6004")
    assert b["radiacion"].tolist() == [Q.SOSPECHOSO, Q.BUENO]


def test_geometria_solar_mediodia_en_el_tropico():
    sol = Q.geometria_solar(pd.DatetimeIndex(["2026-03-20 12:00"]), 6.4, -75.4)
    assert sol["elevacion"].iloc[0] > 80  # equinoccio, cerca del cenit


def test_media_circular_no_promedia_350_y_10_como_180():
    assert D.media_circular([350, 10]) == pytest.approx(0, abs=1e-6)


def test_agregacion_respeta_cobertura():
    s = serie([1.0] * 30 + [np.nan] * 30 + [2.0] * 60)
    h = D.agregar(s, "t")
    assert np.isnan(h.iloc[0]) and h.iloc[1] == 2.0


def test_kappa_acuerdo_total_y_azar():
    a = np.array([1, 1, 0, 0, 0, 0, 0, 0], bool)
    assert I.kappa(a, a) == pytest.approx(1)
    assert I.kappa(a, ~a) < 0
    assert I.kappa(a, np.zeros(8, bool)) == pytest.approx(0)  # solo uno marca: acuerdo de azar
    assert np.isnan(I.kappa(np.zeros(8, bool), np.zeros(8, bool)))  # ninguno marca: no hay qué medir


def test_completitud_con_intervalos_distintos():
    # una estación cada minuto y otra cada 5 min, ambas completas en una hora: las dos deben dar 1
    t1 = pd.date_range("2026-01-01 00:00", periods=60, freq="min")
    t5 = pd.date_range("2026-01-01 00:00", periods=12, freq="5min")
    tabla = pd.concat([pd.DataFrame({"codigo": "A", "fecha_hora": t1, "valor": 1.0, "calidad": 1}),
                       pd.DataFrame({"codigo": "B", "fecha_hora": t5, "valor": 1.0, "calidad": 1})])
    c = I.completitud_tabla_larga(tabla, {"A": 60, "B": 300}, freq="h")
    assert c.tolist() == [1.0, 1.0]
    # un registro repetido en la misma casilla, un centinela y un nulo no suben ni bajan la cuenta
    extra = pd.DataFrame({"codigo": "B", "fecha_hora": pd.to_datetime(["2026-01-01 00:02", "2026-01-01 00:07",
                          "2026-01-01 00:12"]), "valor": [1.0, -999.0, np.nan], "calidad": 1})
    c = I.completitud_tabla_larga(pd.concat([tabla, extra]), {"A": 60, "B": 300}, freq="h")
    assert c.tolist() == [1.0, 1.0]
    # el -9999 de la guía de piranómetros tampoco cuenta como dato recibido
    uno = (tabla["codigo"] == "B") & (tabla["fecha_hora"] == t5[1])
    c = I.completitud_tabla_larga(tabla.assign(valor=np.where(uno, -9999.0, tabla["valor"])), {"A": 60, "B": 300}, freq="h")
    assert c.tolist() == [1.0, pytest.approx(11 / 12)]


def test_salto_tiene_dos_niveles_como_la_omm():
    # OMM (WMO-No. 488, ap. VI.2): temperatura sospechosa desde 3 °C y errónea desde 10 °C entre minutos
    idx = pd.date_range("2026-01-01", periods=4, freq="min")
    d = pd.DataFrame({v: 1.0 for v in D.ESTACIONES["367"]["variables"]}, index=idx)
    d["t"] = [20.0, 24.0, 24.0, 35.0]
    banderas, _ = Q.evaluar(d, "367")
    assert banderas["t"].tolist() == [Q.SOSPECHOSO, Q.SOSPECHOSO, Q.MALO, Q.MALO]


def test_anemometro_en_cero_es_malo_y_la_calma_no():
    idx = pd.date_range("2026-01-01", periods=3, freq="min")
    d = pd.DataFrame({v: 1.0 for v in D.ESTACIONES["367"]["variables"]}, index=idx)
    d["vv"], d["vv_max"], d["dv"], d["dv_max"] = [0.0, 0.0, 2.0], [0.0, 0.3, 3.0], [0.0, 0.0, 90.0], [0.0, 10.0, 95.0]
    banderas, _ = Q.evaluar(d, "367")
    assert banderas["vv"].tolist() == [Q.MALO, Q.BUENO, Q.BUENO]


def test_rafaga_trabada_con_viento_fuerte():
    idx = pd.date_range("2026-01-01", periods=2, freq="min")
    d = pd.DataFrame({v: 1.0 for v in D.ESTACIONES["367"]["variables"]}, index=idx)
    d["vv"], d["vv_max"], d["dv"], d["dv_max"] = [12.85, 6.0], [13.0, 9.0], [90.0, 90.0], [95.0, 95.0]
    banderas, _ = Q.evaluar(d, "367")
    assert banderas["vv_max"].tolist() == [Q.SOSPECHOSO, Q.BUENO]


def test_regularizar_pasa_la_6004_a_hora_local_y_el_centinela_a_vacio():
    crudo = pd.DataFrame({"codigo": 6004, "fecha_hora": pd.to_datetime(["2025-12-01 05:00:00", "2025-12-01 05:01:20"]),
                          "radiacion": [0.0, 3.5], "calidad": 1})
    d = D.regularizar(crudo, "6004")
    assert d.index[0] == pd.Timestamp("2025-11-30 19:00")  # el archivo viene en UTC
    assert d.loc["2025-12-01 00:01", "radiacion"] == 3.5 and d.loc["2025-12-01 00:01", "fuera_de_minuto"]
    assert d["presente"].sum() == 2
    crudo = pd.DataFrame({"codigo": 35, "fecha_hora": pd.to_datetime(["2025-12-01 00:00:00"]),
                          "p1": [-999.0], "p2": [0.254], "calidad": 151})
    d = D.regularizar(crudo, "35")
    assert np.isnan(d.iloc[0]["p1"]) and d.iloc[0]["centinela"] and d.iloc[0]["p2"] == 0.254


def test_confiabilidad_de_la_bandera_y_sus_tasas():
    idx = pd.date_range("2026-01-01", periods=8, freq="min")
    calidad_siata = pd.Series([1, 1, 1, 1, 151, 151, 2, 1], index=idx)  # el 2 es confiable (llegó tarde)
    propia = pd.Series([Q.BUENO, Q.BUENO, Q.BUENO, Q.SOSPECHOSO, Q.MALO, Q.BUENO, Q.BUENO, Q.FALTANTE], index=idx)
    r = I.confiabilidad_bandera(calidad_siata, propia, freq=None).iloc[0]
    assert r["n"] == 7  # el faltante no cuenta
    assert r["falsos_confiables"] == pytest.approx(1 / 5)  # de 5 confiables para SIATA, 1 no pasa el control
    assert r["dudosos_que_pasan"] == pytest.approx(1 / 2)
    assert r["kappa"] == pytest.approx(I.kappa([0, 0, 0, 0, 1, 1, 0], [0, 0, 0, 1, 1, 0, 0]))


def test_completitud_da_cero_en_un_dia_sin_registros():
    t = pd.date_range("2026-01-01", periods=1440, freq="min").append(pd.date_range("2026-01-03", periods=1440, freq="min"))
    tabla = pd.DataFrame({"codigo": "A", "fecha_hora": t, "valor": 1.0, "calidad": 1})
    c = I.completitud_tabla_larga(tabla, {"A": 60}, freq="D", desde="2026-01-01", hasta="2026-01-03")
    assert c.tolist() == [1.0, 0.0, 1.0]


def test_nivel_alto_sin_dato_de_lluvia_no_se_marca():
    # si la 35 no reporta no se puede afirmar que fue seco: una creciente real no debe quedar mala
    idx = pd.date_range("2026-01-01", periods=10 * 1440, freq="min")
    nivel = pd.Series(3.0, index=idx)
    nivel.iloc[-60:] = 60.0
    sin_lluvia = pd.DataFrame({"p1": np.nan, "p2": np.nan}, index=idx)
    b, _ = Q.evaluar(pd.DataFrame({"nivel": nivel}), "803", {"35": sin_lluvia})
    assert (b["nivel"].iloc[-59:] != Q.MALO).all()


def _base_367(n, inicio="2026-01-01"):
    idx = pd.date_range(inicio, periods=n, freq="min")
    d = pd.DataFrame({v: 1.0 for v in D.ESTACIONES["367"]["variables"]}, index=idx)
    ruido = np.sin(np.arange(n) / 7)
    d["t"], d["h"], d["pr"] = 18 + ruido, 80 + 3 * ruido, 816 + ruido
    d["vv"], d["vv_max"], d["dv"], d["dv_max"] = 2 + ruido, 3 + ruido, 180 + 20 * ruido, 185 + 20 * ruido
    return d


def test_persistencia_redondea_la_resta_de_coma_flotante():
    # 16,6 y 16,7 varían justo 0,1: no es un valor congelado aunque 16,7 - 16,6 dé 0,0999... en coma flotante
    s = serie([16.6, 16.7] * 60)
    assert not Q.persistencia(s, 60, 0.1).any()
    assert Q.persistencia(serie([17.5] * 120), 60, 0.1).all()


def test_persistencia_aguanta_un_minuto_perdido():
    s = serie([17.5] * 120)
    s.iloc[30] = np.nan  # el registrador congelado pierde un minuto: igual se detecta
    assert Q.persistencia(s, 60, 0.1).iloc[40:100].all()


def test_veleta_trabada_en_el_norte_se_detecta():
    d = _base_367(180)
    d["dv"] = [359.0, 0.0] * 90  # oscila en el norte con viento: la resta lineal daría 359
    banderas, fallas = Q.evaluar(d, "367")
    assert "persistencia" in set(fallas.loc[fallas["variable"] == "dv", "prueba"])


def test_lluvia_sin_respaldo_con_una_vuelta_equivalente():
    d = _base_367(120)
    d["p"] = 0.0
    d.iloc[10, d.columns.get_loc("p")] = 0.1  # 0,1 mm en la 367 y nada en la 35
    lluvia_35 = pd.DataFrame({"p1": 0.0, "p2": 0.0}, index=d.index)
    b, f = Q.evaluar(d, "367", {"35": lluvia_35})
    assert b["p"].iloc[10] == Q.SOSPECHOSO and "lluvia_sin_respaldo" in set(f["prueba"])


def test_p1_p2_tolerancia_relativa():
    idx = pd.date_range("2026-01-01", periods=120, freq="min")
    d = pd.DataFrame({"p1": 0.0, "p2": 0.0}, index=idx)
    d.iloc[5:9, 0], d.iloc[5, 1] = 0.254, 0.254  # 1,016 frente a 0,254: tres vueltas de diferencia
    d.iloc[65, 0], d.iloc[66, 1], d.iloc[67, 1] = 0.254, 0.254, 0.254  # una vuelta de diferencia: normal
    b, _ = Q.evaluar(d, "35")
    assert b["p1"].iloc[5] == Q.SOSPECHOSO and b["p1"].iloc[65] == Q.BUENO


def test_sin_lluvia_de_referencia_el_nivel_queda_no_evaluado():
    idx = pd.date_range("2026-01-01", periods=10 * 1440, freq="min")
    nivel = pd.Series(3.0 + np.sin(np.arange(len(idx)) / 50), index=idx)
    sin_lluvia = pd.DataFrame({"p1": np.nan, "p2": np.nan}, index=idx)
    b, _ = Q.evaluar(pd.DataFrame({"nivel": nivel}), "803", {"35": sin_lluvia})
    assert (b["nivel"].iloc[-100:] == Q.NO_EVALUADO).all()


def test_centinela_9999_y_version_en_la_traza():
    idx = pd.date_range("2026-01-01", periods=3, freq="min")
    crudo = pd.DataFrame({"codigo": 6004, "fecha_hora": idx + pd.Timedelta(hours=5), "radiacion": [0.0, -9999.0, 0.0],
                          "calidad": 1})
    d = D.regularizar(crudo, "6004")
    assert d.loc[idx[1], "centinela"] and np.isnan(d.loc[idx[1], "radiacion"])
    _, f = Q.evaluar(d.loc[idx[0]:idx[2]], "6004")
    assert (f["version_reglas"] == Q.VERSION_REGLAS).all()


def test_formato_de_fecha_distinto_detiene_la_carga(tmp_path, monkeypatch):
    ruta = tmp_path / D.ESTACIONES["35"]["archivo"]
    pd.DataFrame({"codigo": 35, "fecha_hora": ["2026-01-01T00:00:00", "2026-01-01T00:01:00"], "p1": 0.0, "p2": 0.0,
                  "calidad": 1}).to_csv(ruta, index=False)
    monkeypatch.setattr(D, "DIR_DATOS", tmp_path)
    with pytest.raises(ValueError):
        D.cargar("35")


def test_bandera_por_fila_y_validos():
    idx = pd.date_range("2026-01-01", periods=1, freq="min")
    b = pd.DataFrame({"a": [Q.BUENO], "b": [Q.SOSPECHOSO], "c": [Q.FALTANTE]}, index=idx)
    assert Q.bandera_registro(b).iloc[0] == Q.SOSPECHOSO  # la peor con dato; el faltante no cuenta
    v = I.proporcion_validos(b)
    assert v["a"].iloc[0] == 1 and v["b"].iloc[0] == 0 and np.isnan(v["c"].iloc[0])


def test_kappa_maximo_con_prevalencias_conocidas():
    a = np.array([1] * 2 + [0] * 8, bool)  # prevalencia 0,2
    b = np.array([1] * 4 + [0] * 6, bool)  # prevalencia 0,4
    esperado = 0.2 * 0.4 + 0.8 * 0.6  # acuerdo de azar
    assert I.kappa_maximo(a, b) == pytest.approx((0.8 - esperado) / (1 - esperado))
    assert I.kappa(a, b) == pytest.approx(I.kappa_maximo(a, b))  # todo lo de a está dentro de b


def test_media_circular_ponderada_por_velocidad():
    s = serie([350.0, 90.0])
    w = pd.Series([10.0, 0.1], index=s.index)
    h = D.agregar(s, "dv", "h", cobertura_min=0, pesos=w)
    assert abs(((h.iloc[0] - 350 + 180) % 360) - 180) < 2  # casi 350°, no el promedio 220°


def test_direccion_sin_peso_no_cuenta_en_la_cobertura():
    # 60 minutos de dirección pero velocidad buena en uno solo: la media sale de 1 de 60 minutos, no se publica
    s = serie([180.0] * 60)
    w = pd.Series(np.nan, index=s.index)
    w.iloc[0] = 2.0
    assert D.agregar(s, "dv", "h", cobertura_min=0.75, pesos=w).isna().all()
