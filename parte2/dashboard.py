"""Prototipo de dashboard de calidad de datos para cuatro estaciones de SIATA (Tarea F).

    streamlit run parte2/dashboard.py

Si no existen las salidas del control de calidad (parte2/salidas/), las genera la primera vez desde los CSV crudos.
"""
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
from siata import calidad as Q  # noqa: E402
from siata import indicadores as I  # noqa: E402
from siata.datos import DIR_SALIDAS, ESTACIONES, VARIABLES, agregar  # noqa: E402
from siata.pipeline import DIR_RESULTADOS, correr  # noqa: E402

st.set_page_config(page_title="Calidad de datos SIATA", layout="wide")

# Paleta apta para daltonismo: estados con ícono y texto, nunca solo color
ESTADO = {"aceptable": ("●", "#0ca30c"), "alerta": ("▲", "#fab219"), "crítico": ("■", "#d03b3b"),
          "sin dato": ("○", "#898781")}
FONDO_ESTADO = {"aceptable": "#e3f4e3", "alerta": "#fdf0d0", "crítico": "#f8dcdc", "sin dato": "#eeeeec"}
SEVERIDAD = {"alta": ESTADO["crítico"][1], "media": ESTADO["alerta"][1], "baja": ESTADO["sin dato"][1]}
SERIE, PRONOSTICO, HUECO = "#2a78d6", "#6250d6", "rgba(137,135,129,0.25)"
# Orden fijo validado para daltonismo (pares vecinos); nunca la paleta por defecto de plotly
CATEGORICA = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
MARCA = {Q.SOSPECHOSO: ("triangle-up", "#fab219", "sospechoso"), Q.MALO: ("x", "#d03b3b", "malo")}
NOMBRE_ESTACION = {c: f"{c} · {e['tipo']}" for c, e in ESTACIONES.items()}
RESOLUCION = {"min": "1 min", "10min": "10 min", "h": "1 h"}
VERSIONES = ["cruda", "desestacionalizada", "diferenciada"]  # color y símbolo fijos por versión, no por posición


def pct(x, dec=2):
    return "sin dato" if pd.isna(x) else f"{100 * x:.{dec}f} %".replace(".", ",")


def num(x, dec=2):
    return "sin dato" if pd.isna(x) else f"{x:.{dec}f}".replace(".", ",")


def con_estado(texto, estado):
    icono, _ = ESTADO[estado]
    return f"{icono} {texto} ({estado})"


def fondo(celda):
    """Fondo suave según el estado escrito al final de la celda; el texto va siempre en tinta oscura."""
    estado = celda[celda.rfind("(") + 1:-1]
    return f"background-color: {FONDO_ESTADO[estado]}; color: #0b0b0b" if estado in FONDO_ESTADO else ""


@st.cache_data(show_spinner="Corriendo el control de calidad por primera vez (unos segundos)...")
def asegurar_salidas():
    if not (DIR_SALIDAS / "minutal_367.parquet").exists():
        correr()
    return datetime.fromtimestamp((DIR_SALIDAS / "minutal_367.parquet").stat().st_mtime)


@st.cache_data
def minutal(codigo):
    return pd.read_parquet(DIR_SALIDAS / f"minutal_{codigo}.parquet")


@st.cache_data
def resultado(nombre):
    ruta = DIR_RESULTADOS / nombre
    if not ruta.exists():
        return None
    t = pd.read_csv(ruta)
    if "codigo" in t:
        t["codigo"] = t["codigo"].astype(str)
    return t


@st.cache_data
def pronosticos():
    """Predicciones del origen móvil (notebook 06); si no se ejecutó, el último origen versionado en resultados/."""
    ruta = DIR_SALIDAS / "pronosticos.parquet"
    if ruta.exists():
        p = pd.read_parquet(ruta)
    elif (DIR_RESULTADOS / "pronostico_ultimo_origen.csv").exists():
        p = pd.read_csv(DIR_RESULTADOS / "pronostico_ultimo_origen.csv", parse_dates=["origen", "fecha_hora"])
    else:
        return None
    p["codigo"] = p["codigo"].astype(str)
    return p


generado = asegurar_salidas()
periodo = ("1 dic 2025 a 30 abr 2026, hora local (UTC-5); la 6004 llega en UTC, así que en hora local va del "
           "30 nov 19:00 al 30 abr 18:59")

with st.sidebar:
    st.header("Calidad de datos SIATA")
    st.write(f"Periodo: {periodo}")
    st.write(f"Control de calidad generado: {generado:%Y-%m-%d %H:%M}. Eventos, pronósticos y correlaciones: "
             "última ejecución de los notebooks 06 a 08.")
    st.write("Fuente: [datos.siata.gov.co](https://datos.siata.gov.co/), estaciones 367, 803, 6004 y 35.")
    st.divider()
    st.caption("Para quién: jefe de área y operadores que necesitan saber, sin estadística, qué estaciones "
               "están sanas, qué dato no usar y por qué.")
    st.caption("Preguntas que responde: ¿qué estación o variable tiene problemas? ¿dónde están los huecos y las "
               "anomalías? ¿qué se espera en las próximas horas y con qué incertidumbre? ¿qué se relaciona con qué?")

salud, series, anomalias, relaciones, transparencia = st.tabs(
    ["Salud de la red", "Series de tiempo", "Anomalías", "Relaciones", "Transparencia"])

# ---------------- Salud de la red (F2) ----------------
with salud:
    st.subheader("Estado por estación y variable")
    st.caption("Completitud: minutos con dato / minutos esperados (aceptable ≥ 95 %, crítico < 80 %). "
               "Válidos: minutos que pasan todas las reglas / minutos con dato (aceptable ≥ 98 %, crítico < 90 %). "
               "Confiabilidad de la bandera: kappa de Cohen entre la columna calidad de SIATA y el control propio "
               "(1 = acuerdo total, 0 = acuerdo de azar; aceptable ≥ 0,61, crítico < 0,41, Landis y Koch 1977). "
               "Los íconos ●, ▲ y ■ repiten el estado para no depender del color.")
    periodo_t = resultado("indicadores_periodo.csv")
    tabla = pd.DataFrame({
        "Estación": periodo_t["codigo"].map(NOMBRE_ESTACION),
        "Variable": periodo_t["variable"].map(lambda v: f"{v} · {VARIABLES[v]['nombre']} ({VARIABLES[v]['unidad']})"),
        "Completitud": [con_estado(pct(c), e) for c, e in zip(periodo_t["completitud"], periodo_t["semaforo_completitud"])],
        "Válidos": [con_estado(pct(v), e) for v, e in zip(periodo_t["validos"], periodo_t["semaforo_validos"])],
        "Confiabilidad de la bandera": [con_estado(f"{num(k)} · máx. {num(km)}", e) for k, km, e in
                                        zip(periodo_t["kappa"], periodo_t["kappa_max"], periodo_t["semaforo_kappa"])],
    })
    estados = ["Completitud", "Válidos", "Confiabilidad de la bandera"]
    st.dataframe(tabla.style.map(fondo, subset=estados), hide_index=True, width="stretch",
                 height=36 * (len(tabla) + 1) + 3)  # todas las filas a la vista, sin barra de desplazamiento
    st.caption("La bandera se evalúa por fila (la columna calidad de SIATA es una sola para todas las variables "
               "de la estación), por eso la confiabilidad se repite entre variables de la 367. Máx.: el kappa más alto "
               "posible con las dos proporciones de datos marcados. Un kappa cerca de su máximo (803) dice que las dos "
               "banderas no se contradicen y una es más sensible; uno muy por debajo (35) es desacuerdo real.")

    st.subheader("Evolución en el tiempo")
    c1, c2 = st.columns([1, 3])
    codigo = c1.selectbox("Estación", list(ESTACIONES), format_func=NOMBRE_ESTACION.get, key="salud_estacion")
    diarios = resultado("indicadores_diarios.csv")
    diarios = diarios[diarios["codigo"] == codigo].assign(fecha=lambda d: pd.to_datetime(d["fecha"]))
    for columna, titulo, (acept, alerta) in [("completitud", "Completitud diaria", I.SEMAFORO["completitud"]),
                                             ("validos", "Proporción diaria de datos válidos", I.SEMAFORO["validos"])]:
        fig = go.Figure()
        for i, (variable, g) in enumerate(diarios.groupby("variable")):
            fig.add_scatter(x=g["fecha"], y=100 * g[columna], mode="lines", name=variable,
                            line=dict(width=2, color=CATEGORICA[i % len(CATEGORICA)]))
        fig.add_hline(y=100 * acept, line_dash="dot", line_color=ESTADO["aceptable"][1],
                      annotation_text=f"aceptable {pct(acept, 0)}")
        fig.add_hline(y=100 * alerta, line_dash="dot", line_color=ESTADO["crítico"][1],
                      annotation_text=f"crítico bajo {pct(alerta, 0)}")
        fig.update_layout(title=titulo, yaxis_title="% del día" if columna == "completitud" else "% de los minutos con dato",
                          yaxis_range=[0, 101], height=300,
                          hovermode="x unified", margin=dict(t=40, b=20))
        c2.plotly_chart(fig, width="stretch")
    mensual = resultado("indicadores_mensuales.csv")
    mensual = mensual[mensual["codigo"] == codigo].drop_duplicates("mes")
    fig = go.Figure(go.Bar(x=pd.to_datetime(mensual["mes"]).dt.strftime("%b %Y"), y=mensual["kappa"], marker_color=SERIE,
                           text=[num(k) for k in mensual["kappa"]], textposition="outside"))
    fig.add_hline(y=I.SEMAFORO["kappa"][0], line_dash="dot", line_color=ESTADO["aceptable"][1], annotation_text="aceptable 0,61")
    fig.add_hline(y=I.SEMAFORO["kappa"][1], line_dash="dot", line_color=ESTADO["crítico"][1], annotation_text="crítico bajo 0,41")
    fig.update_layout(title="Confiabilidad mensual de la bandera de SIATA (kappa)", yaxis_range=[-0.1, 1], height=300,
                      yaxis_title="kappa (sin unidad)", margin=dict(t=40, b=20))
    c2.plotly_chart(fig, width="stretch")
    c2.caption("Un mes sin rótulo es un mes en que ni SIATA ni el control propio marcaron datos dudosos, así que no hay "
               "qué comparar. Si solo uno de los dos marca, el kappa es 0 y la barra no se ve; queda solo el rótulo 0,00.")

# ---------------- Series de tiempo (F3) ----------------
with series:
    f1, f2, f3, f4 = st.columns([1, 1, 2, 1])
    # Enlace directo para la demo: ?estacion=803&desde=2025-12-02&hasta=2025-12-09
    pedida = st.query_params.get("estacion")
    codigo = f1.selectbox("Estación", list(ESTACIONES), format_func=NOMBRE_ESTACION.get, key="serie_estacion",
                          index=list(ESTACIONES).index(pedida) if pedida in ESTACIONES else 0)
    variable = f2.selectbox("Variable", ESTACIONES[codigo]["variables"],
                            format_func=lambda v: f"{v} · {VARIABLES[v]['nombre']}")
    m = minutal(codigo)
    lo, hi = m.index.min().date(), m.index.max().date()
    inicio_def, fin_def = max(lo, (m.index.max() - pd.Timedelta("7D")).date()), hi
    if "desde" in st.query_params and "hasta" in st.query_params:
        try:  # el enlace es entrada del usuario: se ajusta al periodo de la estación en vez de tumbar la página
            inicio_def, fin_def = sorted(min(max(pd.Timestamp(st.query_params[k]).date(), lo), hi) for k in ("desde", "hasta"))
        except (ValueError, TypeError):  # TypeError: "desde=" vacío da NaT
            st.warning("Las fechas del enlace no son válidas (use AAAA-MM-DD): se muestra la última semana.")
    rango = f3.date_input("Rango de fechas", value=(inicio_def, fin_def), min_value=lo, max_value=hi)
    ver_siata = f4.toggle("Bandera de SIATA", value=False)
    if not (isinstance(rango, tuple) and len(rango) == 2):
        st.info("Elija la fecha final del rango.")
        rango = (rango[0] if isinstance(rango, tuple) else rango,) * 2
    tramo = m.loc[str(rango[0]): str(rango[1])]
    dias = (pd.Timestamp(rango[1]) - pd.Timestamp(rango[0])).days + 1
    freq = "min" if dias <= 3 else "10min" if dias <= 21 else "h"
    unidad = VARIABLES[variable]["unidad"]

    valor = tramo[variable].where(tramo[f"b_{variable}"] != Q.FALTANTE)
    pesos = tramo["vv"] if variable in ("dv", "dv_max") else None
    cobertura = 0.9 if VARIABLES[variable]["agregacion"] == "suma" else 0.5  # una suma con huecos subestima
    y = valor if freq == "min" else agregar(valor, variable, freq, cobertura_min=cobertura, pesos=pesos)
    peor = tramo[f"b_{variable}"].where(tramo[f"b_{variable}"] != Q.FALTANTE)
    peor = peor if freq == "min" else peor.resample(freq).max()
    siata_dudoso = ~tramo["calidad"].isin(I.CALIDAD_CONFIABLE) & tramo["calidad"].notna()
    siata_dudoso = siata_dudoso if freq == "min" else siata_dudoso.resample(freq).max()

    fig = go.Figure()
    if VARIABLES[variable]["agregacion"] == "suma":
        fig.add_bar(x=y.index, y=y, name=f"{variable} ({unidad})", marker_color=SERIE)
    elif VARIABLES[variable].get("circular"):
        fig.add_scatter(x=y.index, y=y, mode="markers", name=f"{variable} ({unidad})", marker=dict(size=4, color=SERIE))
    else:
        fig.add_scatter(x=y.index, y=y, mode="lines", name=f"{variable} ({unidad})", connectgaps=False,
                        line=dict(width=2, color=SERIE))
    if ver_siata and siata_dudoso.any():
        sel = siata_dudoso.reindex(y.index, fill_value=False).astype(bool)
        fig.add_scatter(x=y.index[sel], y=y[sel], mode="markers", name="SIATA: calidad distinta de 1 y 2",
                        marker=dict(symbol="circle-open", size=11, color="#0b0b0b"))
    for bandera, (simbolo, color, texto) in MARCA.items():
        sel = peor == bandera
        if sel.any():
            fig.add_scatter(x=y.index[sel.reindex(y.index, fill_value=False)], y=y[sel.reindex(y.index, fill_value=False)],
                            mode="markers", name=f"control propio: {texto}",
                            marker=dict(symbol=simbolo, size=9, color=color, line=dict(width=1, color="#0b0b0b")))
    # Huecos: franjas grises donde no llegó el dato (no se interpola nada)
    hueco = tramo[f"b_{variable}"] == Q.FALTANTE
    grupos = (hueco != hueco.shift()).cumsum()[hueco]
    tramos_hueco = [(g.index[0], g.index[-1]) for _, g in grupos.groupby(grupos)]
    # Las franjas van en una sola lista: add_vrect copia todas las formas en cada llamada (cuadrático)
    franja = dict(type="rect", xref="x", yref="y domain", y0=0, y1=1, layer="below")
    franjas = [dict(franja, x0=a, x1=b + pd.Timedelta("1min"), fillcolor=HUECO, line=dict(width=0))
               for a, b in sorted(tramos_hueco, key=lambda t: t[1] - t[0], reverse=True)[:150]]
    desde, hasta = pd.Timestamp(rango[0]), pd.Timestamp(rango[1]) + pd.Timedelta("1D")
    eventos = resultado("eventos_anomalias.csv")
    largos = pd.DataFrame()
    if eventos is not None:
        # un evento puede juntar varias variables ("p1+p2"): se dibuja en cada una
        ev = eventos[(eventos["codigo"] == codigo) & eventos["variable"].str.split("+").apply(lambda vs: variable in vs)].copy()
        ev["inicio"], ev["fin"] = pd.to_datetime(ev["inicio"]), pd.to_datetime(ev["fin"])
        ev = ev[(ev["fin"] >= desde) & (ev["inicio"] <= hasta)]
        # los problemas de configuración cubren meses: van en una nota, no como franja
        largos = ev[(ev["fin"] - ev["inicio"]) > pd.Timedelta("3D")]
        cortos = ev.drop(largos.index)
        cortos = cortos.loc[(cortos["fin"] - cortos["inicio"]).sort_values(ascending=False).index[:150]]  # los 150 más largos
        franjas += [dict(franja, x0=max(e.inicio, desde), x1=min(e.fin, hasta), fillcolor="rgba(98,80,214,0.10)",
                         line=dict(width=1, color="rgba(98,80,214,0.5)")) for e in cortos.itertuples()]
    fig.update_layout(shapes=franjas)
    fig.update_xaxes(range=[desde, hasta])
    if VARIABLES[variable].get("circular"):
        fig.update_yaxes(range=[0, 360], tickvals=[0, 90, 180, 270, 360], ticktext=["N 0°", "E 90°", "S 180°", "O 270°", "N 360°"])
    fig.update_layout(title=f"{VARIABLES[variable]['nombre']} · estación {codigo} · resolución {RESOLUCION[freq]}",
                      yaxis_title=unidad, height=430, hovermode="x unified", legend=dict(orientation="h", y=-0.2),
                      margin=dict(t=50, b=20))
    st.plotly_chart(fig, width="stretch")
    st.caption(f"{len(tramos_hueco)} huecos en el rango. Las franjas grises marcan los minutos en que no llegó el dato; "
               "se dibujan como máximo los 150 huecos más largos. Nada se interpola: a 1 min la línea se corta en cada "
               "hueco; a 10 min y 1 h cada punto resume solo los minutos con dato y queda vacío si falta más de la mitad "
               "del intervalo (más del 10 % en la lluvia), así que un hueco corto no corta la línea. Las franjas violetas "
               "son eventos de la tabla de anomalías, también como máximo los 150 más largos. Los triángulos y las equis "
               "son la bandera del control propio en el minuto o en algún minuto del intervalo agregado.")
    for e in largos.itertuples():
        st.caption(f"Evento de largo plazo ({e.tipo}, {e.inicio:%Y-%m-%d} a {e.fin:%Y-%m-%d}): {e.descripcion}")
    if VARIABLES[variable].get("circular"):
        st.caption("La dirección del viento es circular (0° y 360° son el mismo norte): se muestra como puntos, nunca como "
                   "línea, y al agregar se usa la media vectorial ponderada por la velocidad.")
        sectores = ((tramo[variable] + 22.5) % 360 // 45).dropna().astype(int)
        nombres = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]
        rosa = sectores.value_counts(normalize=True).reindex(range(8), fill_value=0)
        fig = go.Figure(go.Barpolar(r=100 * rosa.to_numpy(), theta=nombres, marker_color=SERIE))
        fig.update_layout(title=f"Rosa de vientos del rango con {variable} (% del tiempo por sector de procedencia)", height=380,
                          polar=dict(angularaxis=dict(direction="clockwise", rotation=90)))
        st.plotly_chart(fig, width="stretch")

    p = pronosticos()
    metricas = resultado("metricas_pronostico.csv")
    if p is not None and variable in set(p.loc[p["codigo"] == codigo, "variable"]):
        pv = p[(p["codigo"] == codigo) & (p["variable"] == variable)]
        candidatos = sorted(set(pv["modelo"]))
        recomendado = candidatos[0]
        if metricas is not None and "MASE" in metricas:
            mv = metricas[(metricas["variable"] == variable) & metricas["modelo"].isin(candidatos)]
            mv = mv[~mv["modelo"].str.contains("ingenu|persist|climat", case=False)]
            if len(mv):
                recomendado = mv.sort_values("MASE").iloc[0]["modelo"]
        modelo = st.selectbox("Modelo del pronóstico", candidatos, index=candidatos.index(recomendado))
        ultimo = pv[pv["modelo"] == modelo]
        ultimo = ultimo[ultimo["origen"] == ultimo["origen"].max()].sort_values("fecha_hora")
        origen = pd.Timestamp(ultimo["origen"].iloc[0])
        historia = ultimo.set_index("fecha_hora")["real"]
        fig = go.Figure()
        probabilidad = "prob" in ultimo and ultimo["prob"].notna().any()
        if probabilidad:
            # En la lluvia lo útil es la probabilidad de que llueva en cada hora: la cantidad casi siempre es 0
            fig.add_bar(x=ultimo["fecha_hora"], y=100 * ultimo["prob"], name=f"probabilidad de lluvia ({modelo})",
                        marker_color=PRONOSTICO)
            llovio = historia[historia > 0]
            fig.add_scatter(x=llovio.index, y=[100] * len(llovio), mode="markers", name="observado: llovió en la hora",
                            marker=dict(symbol="triangle-down", size=11, color=SERIE))
            fig.update_yaxes(range=[0, 105])
        else:
            if {"inf80", "sup80"} <= set(ultimo):
                fig.add_scatter(x=pd.concat([ultimo["fecha_hora"], ultimo["fecha_hora"][::-1]]),
                                y=pd.concat([ultimo["sup80"], ultimo["inf80"][::-1]]), fill="toself",
                                fillcolor="rgba(98,80,214,0.18)", line=dict(width=0), name="intervalo del 80 %")
            fig.add_scatter(x=ultimo["fecha_hora"], y=ultimo["pred"], mode="lines", name=f"pronóstico ({modelo})",
                            line=dict(width=2, color=PRONOSTICO, dash="dash"))
            fig.add_scatter(x=historia.index, y=historia, mode="lines+markers", name="observado", connectgaps=False,
                            line=dict(width=2, color=SERIE), marker=dict(size=5))
        fig.add_vline(x=origen, line_dash="dot", line_color="#898781")
        fig.update_layout(title=f"Pronóstico desde el último origen de la validación ({origen:%Y-%m-%d %H:%M})",
                          yaxis_title="probabilidad de lluvia en la hora (%)" if probabilidad else unidad, height=360,
                          hovermode="x unified", legend=dict(orientation="h", y=-0.25))
        st.plotly_chart(fig, width="stretch")
        if metricas is not None:
            st.caption("Métricas del origen móvil (todos los orígenes, sin fuga de información):")
            st.dataframe(metricas[metricas["variable"] == variable].dropna(axis=1, how="all"), hide_index=True)

# ---------------- Anomalías (F4) ----------------
with anomalias:
    eventos = resultado("eventos_anomalias.csv")
    if eventos is None:
        st.info("Falta parte2/resultados/eventos_anomalias.csv: ejecute el notebook 07_anomalias.")
    else:
        a1, a2, a3, a4 = st.columns(4)
        f_est = a1.multiselect("Estación", sorted(eventos["codigo"].unique()), format_func=lambda c: NOMBRE_ESTACION.get(c, c),
                               placeholder="Todas")
        f_tipo = a2.multiselect("Tipo", sorted(eventos["tipo"].dropna().unique()), placeholder="Todos")
        f_sev = a3.multiselect("Severidad", [s for s in SEVERIDAD if s in set(eventos["severidad"])], placeholder="Todas")
        f_det = a4.multiselect("Detector", sorted(eventos["detector"].dropna().unique()), placeholder="Todos")
        ev = eventos.copy()
        for columna, valores in [("codigo", f_est), ("tipo", f_tipo), ("severidad", f_sev), ("detector", f_det)]:
            if valores:
                ev = ev[ev[columna].isin(valores)]
        conteo = ev.groupby(["tipo", "severidad"]).size().unstack(fill_value=0)
        fig = go.Figure()
        for sev in [s for s in SEVERIDAD if s in conteo]:  # severidad es un orden: rojo, ámbar y gris, no una categoría
            fig.add_bar(y=conteo.index, x=conteo[sev], name=f"severidad {sev}", orientation="h",
                        marker_color=SEVERIDAD[sev], text=conteo[sev], textposition="auto")
        fig.update_layout(barmode="stack", title=f"{len(ev)} eventos por tipo y severidad", xaxis_title="eventos",
                          height=320, legend=dict(orientation="h", y=-0.3))
        st.plotly_chart(fig, width="stretch")
        st.dataframe(ev, hide_index=True, width="stretch")
        st.download_button("Descargar la tabla filtrada (CSV)", ev.to_csv(index=False).encode("utf-8"), "eventos_anomalias.csv")
        st.caption("Un evento físico real, como el aguacero de 43,6 mm del 3 de abril de 2026, se reporta pero no se "
                   "borra, porque el sistema de alerta lo necesita.")

# ---------------- Relaciones (F5) ----------------
with relaciones:
    corr, cruzada = resultado("correlaciones.csv"), resultado("correlacion_cruzada.csv")
    if corr is None or cruzada is None:
        st.info("Faltan los resultados de correlación: ejecute el notebook 08_correlaciones.")
    else:
        r1, r2 = st.columns(2)
        medidas = sorted(corr["metodo"].unique())
        metodo = r1.selectbox("Medida", medidas, index=medidas.index("spearman") if "spearman" in medidas else 0)
        sub = corr[corr["metodo"] == metodo]
        versiones = sorted(sub["version"].unique())
        fig = go.Figure()
        for version in versiones:
            g = sub[sub["version"] == version]
            fig.add_scatter(x=g["valor"], y=g["par"], mode="markers", name=version,
                            marker=dict(size=11, color=CATEGORICA[VERSIONES.index(version)],
                                        symbol=["circle", "diamond", "square"][VERSIONES.index(version)]))
        fig.add_vline(x=0, line_color="#c3c2b7")
        fig.update_layout(title=f"{metodo}: serie cruda frente a desestacionalizada o diferenciada", xaxis_range=[-1, 1],
                          xaxis_title="correlación (sin unidad, de -1 a 1)", height=120 + 28 * sub["par"].nunique(),
                          legend=dict(orientation="h", y=-0.15))
        st.plotly_chart(fig, width="stretch")
        st.caption("Si la correlación cae mucho al quitar el ciclo diurno, venía sobre todo del ciclo que comparten las dos "
                   "variables y es espuria para decidir; lo que queda es la relación informativa. Aun así, una correlación "
                   "alta no prueba que una variable cause la otra.")
        par = r2.selectbox("Par para la correlación cruzada", sorted(cruzada["par"].unique()))
        fig = go.Figure()
        for version, g in cruzada[cruzada["par"] == par].groupby("version"):
            g = g.sort_values("rezago_min")
            fig.add_scatter(x=g["rezago_min"], y=g["valor"], mode="lines+markers", name=version,
                            line=dict(width=2, color=CATEGORICA[VERSIONES.index(version)]))
            mejor = g.loc[g["valor"].abs().idxmax()]
            fig.add_annotation(x=mejor["rezago_min"], y=mejor["valor"], text=f"{num(mejor['valor'])} a {mejor['rezago_min']:.0f} min",
                               showarrow=True, arrowhead=2)
        fig.add_hline(y=0, line_color="#c3c2b7")
        fig.update_layout(title=f"Correlación cruzada: {par}", xaxis_title="rezago (minutos)",
                          yaxis_title="correlación (sin unidad)", height=380, legend=dict(orientation="h", y=-0.25))
        st.plotly_chart(fig, width="stretch")

# ---------------- Transparencia (F6) ----------------
with transparencia:
    st.subheader("Diccionario de variables")
    filas = [{"Estación": NOMBRE_ESTACION[c], "Variable": v, "Descripción": VARIABLES[v]["nombre"],
              "Unidad": VARIABLES[v]["unidad"], "Cómo se agrega por hora": VARIABLES[v]["agregacion"]}
             for c, e in ESTACIONES.items() for v in e["variables"]]
    st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
    st.caption("Los CSV de la prueba no traían diccionario: se reconstruyó desde los datos y las fichas, y se contrastó con las "
               "guías Generalidades de cada red en datos.siata.gov.co. Los supuestos están en el informe técnico.")
    st.subheader("Banderas del control propio")
    st.dataframe(pd.DataFrame({"Código": list(Q.NOMBRE_BANDERA), "Significado": list(Q.NOMBRE_BANDERA.values())}),
                 hide_index=True)
    st.caption("Esquema de la recomendación IOC/UNESCO para intercambio de datos (Manuals and Guides 54, vol. 3, 2013). "
               "Una bandera 3 o 4 no borra el dato: lo marca y deja la traza de la prueba que la disparó.")
    st.subheader("Pruebas y umbrales")
    st.dataframe(pd.DataFrame({"Prueba": list(Q.DESCRIPCION_PRUEBA), "Qué revisa": list(Q.DESCRIPCION_PRUEBA.values())}),
                 hide_index=True, width="stretch")
    st.json({k: v for k, v in Q.UMBRALES.items()}, expanded=False)
    dic = resultado("diccionario_calidad_inferido.csv")
    if dic is not None:
        st.subheader("Códigos de la columna calidad de SIATA: inferidos y oficiales")
        st.dataframe(dic, hide_index=True, width="stretch")
        st.caption("Los significados se infirieron desde los datos y después se contrastaron con las guías oficiales de cada "
                   "red (Generalidades Repositorio de Datos, datos.siata.gov.co). Coinciden en los 21 pares de código y "
                   "estación con minutos en el periodo; el 1567 sale de la regla de combinación de la guía, 156 viento + 157 "
                   "dirección. La tabla incluye además el 1581 de la 6004, que está en la guía pero no aparece en los datos.")
    st.subheader("Fuente, actualización y limitaciones")
    st.markdown(
        f"- Fuente: CSV entregados para la prueba, con las fichas de [datos.siata.gov.co](https://datos.siata.gov.co/) "
        "(DOI 10.83041/MWDZIZ, 10.83041/SXHWBW, 10.83041/JUHKI6, 10.83041/UO0BXL).\n"
        f"- Periodo: {periodo}. Control de calidad generado el {generado:%Y-%m-%d %H:%M}; eventos, pronósticos y "
        "correlaciones salen de la última ejecución de los notebooks 06 a 08.\n"
        "- La 6004 llega en UTC y aquí se muestra en hora local (se restan 5 h). Las otras tres llegan en hora local.\n"
        "- El nivel de la 803 se mide sobre un cero de referencia no documentado (hay valores negativos).\n"
        "- La lluvia de la 367 registra cerca del 32 % de la de la 35 en el mismo sitio: no usarla para cantidades.\n"
        "- Los umbrales de las reglas son una propuesta: algunos vienen de la OMM y de BSRN y otros se calibraron con "
        "estos cinco meses; deben revisarse con más historia y con el equipo de operación.\n"
        "- Los pronósticos vienen de la validación de origen móvil del notebook 06, no de un sistema en operación.")
    st.code("streamlit run parte2/dashboard.py", language="bash")
