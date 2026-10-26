"""Corre el control de calidad completo y deja las salidas que usan los notebooks y el dashboard.

    python -m siata.pipeline        (desde parte2/)

parte2/salidas/    (no versionado) series minutales con banderas, traza de fallas y series horarias
parte2/resultados/ (versionado)    indicadores de calidad por día, por mes y del periodo
"""
import pandas as pd

from . import calidad as Q
from . import indicadores as I
from .datos import DIR_SALIDAS, ESTACIONES, RAIZ, agregar, cargar_todo

DIR_RESULTADOS = RAIZ / "parte2" / "resultados"


def correr():
    DIR_SALIDAS.mkdir(parents=True, exist_ok=True)
    DIR_RESULTADOS.mkdir(parents=True, exist_ok=True)
    todo = cargar_todo()
    fallas, diarios, mensuales, resumen, horario = [], [], [], [], {}
    for codigo, d in todo.items():
        variables = ESTACIONES[codigo]["variables"]
        banderas, f = Q.evaluar(d, codigo, todo)
        fallas.append(f)
        registro = Q.bandera_registro(banderas)
        minutal = d[variables + ["calidad", "presente", "centinela", "fuera_de_minuto"]].join(
            banderas.add_prefix("b_")).assign(b_registro=registro, version_reglas=Q.VERSION_REGLAS)
        minutal.to_parquet(DIR_SALIDAS / f"minutal_{codigo}.parquet")

        comp, val = I.completitud(banderas), I.proporcion_validos(banderas)
        diarios.append(pd.concat({"completitud": comp, "validos": val}, axis=1).stack(level=1, future_stack=True)
                       .rename_axis(["fecha", "variable"]).reset_index().assign(codigo=codigo))
        kappa_mes = I.confiabilidad_bandera(d["calidad"], registro)
        comp_mes, val_mes = I.completitud(banderas, "MS"), I.proporcion_validos(banderas, "MS")
        for v in variables:
            mensuales.append(pd.DataFrame({"codigo": codigo, "variable": v, "mes": comp_mes.index,
                                           "completitud": comp_mes[v].to_numpy(), "validos": val_mes[v].to_numpy(),
                                           "kappa": kappa_mes["kappa"].reindex(comp_mes.index).to_numpy()}))
        total = I.confiabilidad_bandera(d["calidad"], registro, freq=None).iloc[0]
        for v in variables:
            c = (banderas[v] != Q.FALTANTE).mean()
            p = (banderas[v] == Q.BUENO).sum() / (banderas[v] != Q.FALTANTE).sum()
            resumen.append({"codigo": codigo, "variable": v, "completitud": c, "validos": p,
                            "kappa": total["kappa"], "kappa_max": total["kappa_max"],
                            "falsos_confiables": total["falsos_confiables"],
                            "dudosos_que_pasan": total["dudosos_que_pasan"],
                            "semaforo_completitud": I.semaforo(c, "completitud"),
                            "semaforo_validos": I.semaforo(p, "validos"),
                            "semaforo_kappa": I.semaforo(total["kappa"], "kappa")})
            # horario solo con datos buenos; la dirección se pondera por la velocidad. En la lluvia el desacuerdo
            # entre balancines (sospechoso) no invalida la hora: quitarla borraría justo los aguaceros
            aceptable = Q.SOSPECHOSO if v in ("p1", "p2") else Q.BUENO
            limpio = d[v].where(banderas[v] <= aceptable)
            pesos = d["vv"].where(banderas["vv"] == Q.BUENO) if v in ("dv", "dv_max") else None
            cobertura = 0.9 if v in ("p", "p1", "p2") else 0.75
            horario[f"{codigo}_{v}"] = agregar(limpio, v, "h", cobertura, pesos)

    pd.concat(fallas, ignore_index=True).to_parquet(DIR_SALIDAS / "fallas.parquet")
    pd.DataFrame(horario).to_parquet(DIR_SALIDAS / "horario.parquet")
    pd.concat(diarios, ignore_index=True).to_csv(DIR_RESULTADOS / "indicadores_diarios.csv", index=False)
    pd.concat(mensuales, ignore_index=True).to_csv(DIR_RESULTADOS / "indicadores_mensuales.csv", index=False)
    tabla = pd.DataFrame(resumen)
    tabla.to_csv(DIR_RESULTADOS / "indicadores_periodo.csv", index=False)
    return tabla


if __name__ == "__main__":
    print(correr().round(4).to_string(index=False))
