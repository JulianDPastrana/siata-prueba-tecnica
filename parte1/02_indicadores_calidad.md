# 2.2 Indicadores de calidad de los datos entregados

## Pregunta 1.3. Tres indicadores de calidad

> **Pregunta 1.3.** Proponga **tres (3) indicadores de calidad** aplicables a los datos que SIATA publica. Para cada uno, complete la ficha técnica: nombre y dimensión de calidad; objetivo y pregunta que responde; fórmula (con definición de cada término); unidad de medida y periodicidad de cálculo; fuente de datos y nivel de agregación (estación, red, variable); umbrales de semáforo (aceptable, alerta, crítico) y su justificación; responsable y acción correctiva asociada; limitaciones y posibles sesgos del indicador.
>
> **Criterios de la pregunta.** Los indicadores deben ser *medibles, automatizables, accionables y comparables entre variables y estaciones*. Se penalizan indicadores redundantes entre sí (por ejemplo, dos formas de medir completitud). Los tres deben cubrir dimensiones distintas.

Los tres indicadores le hacen tres preguntas distintas a cada dato: si llegó, si es plausible y si la bandera que SIATA publica sobre él es creíble (completitud, exactitud semántica y credibilidad en ISO/IEC 25012). Están en `parte2/siata/indicadores.py`, los calcula `python -m siata.pipeline` y quedan en `parte2/resultados/`.

Notación: e es la estación, v la variable, d el día y m el mes, en hora local (UTC-5). Una casilla es un intervalo nominal de muestreo (1440 al día en estaciones minutales).

### Indicador 1: Completitud

| Campo | Descripción |
|---|---|
| Nombre y dimensión de calidad | Completitud de la serie. Dimensión: completitud (ISO/IEC 25012, como la recoge MinTIC 2022, sección 4.7): el grado en que los datos tienen valores para todo lo esperado. |
| Objetivo y pregunta que responde | Medir cuánto de lo que la estación debía entregar llegó con valor. Pregunta: de las casillas esperadas en el día, ¿cuántas llegaron con un valor utilizable? |
| Fórmula (con definición de cada término) | C(e, v, d) = R(e, v, d) / E(e, d). E son las casillas esperadas en el día (86 400 s entre el intervalo nominal), salvo en los días del borde del periodo, donde solo cuentan las que caen dentro de él: en la 6004, cuyo archivo va en UTC, el 30 nov y el 30 abr en hora local esperan 300 y 1140 minutos. R son las casillas con valor, sin nulos ni los centinelas -999 y -9999; dos registros en la misma casilla cuentan una vez. Para la red, C_red(d) = suma de R / suma de E sobre los pares estación-variable. |
| Unidad de medida y periodicidad de cálculo | Proporción de 0 a 1, reportada en %. Diaria; el pipeline también la da por mes y para el periodo. |
| Fuente de datos y nivel de agregación (estación, red, variable) | Malla minutal de `datos.regularizar` (la 6004 pasada de UTC a UTC-5) con las banderas de `calidad.evaluar`. Variable y estación, en `indicadores_diarios.csv`, `indicadores_mensuales.csv` e `indicadores_periodo.csv`. La cifra de red es el promedio de las 12 filas de `indicadores_periodo.csv` (todas esperan las mismas 217 440 casillas) y da 99,88 % en el periodo. |
| Umbrales de semáforo (aceptable, alerta, crítico) y su justificación | Aceptable desde 95 % (perder hasta 72 minutos al día), alerta de 80 % a 95 % (hasta 4,8 horas), crítico bajo 80 %. Son cortes operativos propios. Para productos mensuales se suma la regla de la OMM: no calcular un valor medio mensual si faltan 11 días o más, o 5 seguidos, ni un total mensual como la lluvia si falta cualquier dato (OMM No. 1203, 2017, sección 4.4.1). |
| Responsable y acción correctiva asociada | Vigila Calidad de Datos y corrige instrumentación y telemetría (supuesto: no conozco el organigrama de SIATA). En alerta, revisar la transmisión y recuperar lo guardado en el registrador; por ejemplo, la 6004 tuvo 85,2 % el 23 dic 2025. En crítico, orden de mantenimiento y el día queda no apto para productos diarios. |
| Limitaciones y posibles sesgos del indicador | No dice nada de la exactitud: un sensor congelado cuenta como completo. No distingue 5 horas seguidas sin dato de 300 minutos sueltos, así que conviene reportar también el hueco más largo. En la cifra de red pesa más la 367, que aporta 8 de los 12 pares. |

### Indicador 2: Proporción de datos válidos

| Campo | Descripción |
|---|---|
| Nombre y dimensión de calidad | Proporción de datos válidos. Dimensión: exactitud semántica (MinTIC 2022, sección 4.6: cercanía a un dominio semánticamente correcto) y, por las pruebas de coherencia, consistencia (sección 4.8). |
| Objetivo y pregunta que responde | Medir cuánto de lo recibido se puede usar sin revisión humana. Pregunta: de los datos que llegaron, ¿cuántos pasan todas las pruebas de un control de calidad independiente del de SIATA? |
| Fórmula (con definición de cada término) | P(e, v, d) = B(e, v, d) / R(e, v, d). R son los datos recibidos con valor, como en el indicador 1. B son los que quedan con bandera 1 tras todas las pruebas de `calidad.py` (rango, salto, persistencia, coherencia interna y espacial); 2, 3 y 4 cuentan como no válidos. Si R es 0, queda sin dato. Para la red, suma de B / suma de R. |
| Unidad de medida y periodicidad de cálculo | Proporción de 0 a 1, reportada en %. Diaria; también por mes y para el periodo. |
| Fuente de datos y nivel de agregación (estación, red, variable) | Banderas por variable de `calidad.evaluar` y su traza (`parte2/salidas/fallas.parquet`), que dice qué prueba disparó cada bandera. Variable y estación, en los mismos archivos del indicador 1. La cifra de red es el promedio de las 12 filas de `indicadores_periodo.csv` ponderado por su completitud (suma de B / suma de R) y da 99,46 %. |
| Umbrales de semáforo (aceptable, alerta, crítico) y su justificación | Aceptable desde 98 % (hasta unos 29 minutos marcados al día), alerta de 90 % a 98 %, crítico bajo 90 %. Son cortes propios, más exigentes que los de completitud porque un dato malo publicado engaña y un hueco por lo menos se ve. La OMM cuenta como faltante el dato que no pasa el control (OMM No. 1203, nota 2 de la sección 4.4.1). |
| Responsable y acción correctiva asociada | Calidad de Datos. En alerta, mirar en la traza qué prueba disparó y decidir si es un evento real o una falla. En crítico, revisión humana antes de publicar el día como validado y orden de mantenimiento si falla el sensor; por ejemplo, 12 de los 13 días críticos de la 803 (5 entre el 2 y el 8 dic 2025 y 7 entre el 11 y el 17 mar 2026) coinciden con las mesetas de nivel; el otro es el 1 dic 2025, cuyos primeros 170 minutos quedan en 2 porque aún no hay 3 h previas de lluvia de la 35. |
| Limitaciones y posibles sesgos del indicador | Pasar las reglas no garantiza que el dato sea correcto: la lluvia de la 367 es el 32 % del total de la 35 y el 99,6 % de sus minutos pasa. Los umbrales de nivel de la 803 se calibraron con estos mismos datos, lo que lo vuelve optimista. La persistencia marca la ventana completa, así que un episodio pesa mucho en el día, y un extremo real puede quedar como sospechoso. |

### Indicador 3: Confiabilidad de la bandera publicada

| Campo | Descripción |
|---|---|
| Nombre y dimensión de calidad | Confiabilidad de la bandera de calidad de SIATA. Dimensión: credibilidad (MinTIC 2022, sección 4.11), aplicada a la columna `calidad`, que es lo que el usuario mira para decidir si confía en el dato. |
| Objetivo y pregunta que responde | Saber si se le puede creer a la bandera publicada. Pregunta: cuando SIATA marca un dato como dudoso o confiable, ¿coincide con un control independiente más allá del azar? |
| Fórmula (con definición de cada término) | kappa(e, m) = (po - pe) / (1 - pe), el kappa de Cohen sobre los registros del mes con calidad publicada y algún dato. A = 1 si SIATA marca el registro dudoso, es decir, con calidad distinta de 1 y 2. Las guías pluviométrica, meteorológica y de nivel definen el 1 y el 2 como confiable en tiempo real y no en tiempo real (P-GAA-SIATA-107, p. 6; 108, p. 6; 110, p. 5); la de piranómetros no trae el 2. B = 1 si el control propio no lo da por bueno (peor bandera distinta de 1). po es la fracción con A = B y pe = pA·pB + (1 - pA)·(1 - pB). Van además el kappa máximo que permiten pA y pB y las tasas de falsos confiables (B = 1 entre A = 0) y de dudosos que pasan (B = 0 entre A = 1). |
| Unidad de medida y periodicidad de cálculo | Sin unidad, de -1 a 1: 1 es acuerdo perfecto, 0 el del azar. Mensual, porque con tan pocos dudosos por día un kappa diario sería inestable (en la 35, SIATA marca menos de uno al día). También para el periodo. |
| Fuente de datos y nivel de agregación (estación, red, variable) | Columna `calidad` de SIATA y bandera de registro del control propio (`calidad.bandera_registro`). Nivel estación, porque SIATA publica una sola calidad por fila. Salidas: `indicadores_mensuales.csv` e `indicadores_periodo.csv`. Para la red se usa la mediana (0,06 en el periodo) y no el kappa de todos los registros juntos, que dominaría la 803. |
| Umbrales de semáforo (aceptable, alerta, crítico) y su justificación | Aceptable desde 0,61, donde empieza el acuerdo sustancial de Landis y Koch (1977); alerta desde 0,41, donde empieza el moderado; crítico bajo 0,41. Se exige ese nivel porque la bandera es lo que el usuario usa para filtrar. La escala es una convención, así que los cortes se deben revisar con la experiencia de la red. |
| Responsable y acción correctiva asociada | Calidad de Datos junto con quien mantiene el algoritmo de SIATA. Si dominan los falsos confiables, la bandera deja pasar fallas y faltan reglas; si dominan los dudosos que pasan, descarta datos buenos y hay que corregir la regla, como el código 1582 de la 6004 ("mayor a 0 de noche"), que cae con el sol sobre el horizonte en el 79 % de los casos. Si falla el control propio, se corrige el propio. |
| Limitaciones y posibles sesgos del indicador | Mide el acuerdo con otro control que también se equivoca: un kappa bajo no dice quién tiene la razón. Con prevalencias bajas el kappa queda bajo aunque po sea alto (Feinstein y Cicchetti, 1990); por eso van las tasas y el máximo. Si solo una de las dos marca en el mes, el kappa vale 0; es indefinido solo si ninguna marca. El diccionario de SIATA tiene huecos que afectan la lectura: en la guía del nivel el 1504 tiene la misma descripción que el 1502 (P-GAA-SIATA-110, p. 5) y el 1567 de la 367 no está en la tabla meteorológica (solo se explica por su regla de combinación, 156 + 157). |

### Por qué cumplen los criterios y no son redundantes

Los tres se calculan sobre registros sin juicio manual (medibles) y los produce el pipeline (automatizables); el kappa, la completitud con intervalos distintos y las reglas de `calidad.py` tienen pruebas en `parte2/tests/`. Cada color tiene responsable y acción (accionables), y quedan en la misma escala para cualquier variable, estación o intervalo (comparables), salvo que el kappa solo existe por estación.

- Completitud frente a válidos: distinto denominador (lo esperado frente a lo recibido). El 8 dic 2025 la 803 tuvo 100 % de completitud y 19,3 % de válidos; el 8 abr 2026 la 6004 tuvo 23,7 % de completitud y 100 % de válidos.
- Válidos frente a kappa: el primero califica el dato y el segundo la bandera publicada. La 367 tiene entre 98,93 % y 99,98 % de válidos en sus variables y un kappa de 0,053.
- Completitud frente a kappa: el kappa solo usa registros recibidos, así que un hueco no lo mueve, y la completitud no mira la columna `calidad`.

### Resultado actual

Periodo del 1 dic 2025 al 30 abr 2026. Los días en alerta y en crítico toman cada día la variable más baja de la estación. Fuente: `parte2/resultados/`; po sale de `parte2/salidas/minutal_*.parquet`.

| Estación | Completitud | Días alerta / crítico | Válidos | Días alerta / crítico | po | Kappa del periodo (máximo posible) | Kappa mensual (dic a abr) |
|---|---|---|---|---|---|---|---|
| 367 meteorológica | 99,98 % | 0 / 0 | 98,93 a 99,98 % | 57 / 2 | 97,3 % | 0,053 crítico (0,21) | dic 0 (1); ene a abr de 0,040 a 0,074 |
| 803 nivel | 99,94 % | 0 / 0 | 96,37 % (alerta) | 2 / 13 | 91,4 % | 0,42 alerta (0,43) | dic 0,53; ene 0 (1); feb 0 (1); mar 0,68; abr 0,00 |
| 6004 piranómetro | 98,80 % | 2 / 2 | 99,98 % | 0 / 0 | 99,2 % | 0,008 crítico (0,04) | de -0,001 a 0,056; mar 0 (1) |
| 35 pluviométrica | 99,997 % | 0 / 0 | 99,92 % | 3 / 0 | 99,9 % | 0,068 crítico (0,58) | dic, ene y abr 0; feb y mar 0,41 |

(1) Solo una de las dos clasificaciones marca en ese mes (367 dic: SIATA 0 y control propio 951; 803 ene y feb: SIATA 3193 y 3809, propio 0; 6004 mar: SIATA 435, propio 0), así que el kappa vale 0 y el semáforo es crítico. La 6004 tiene además unas horas de nov 2025 (en hora local su archivo empieza el 30 nov a las 19:00) sin marcas de ninguno: es el único mes con kappa indefinido.

Faltan pocos datos y los válidos solo están en alerta en la 803, por las mesetas de nivel. La bandera de SIATA y el control independiente coinciden en casi todos los registros (po de 91,4 % a 99,9 %), pero no en cuáles son dudosos: como los dos marcan muy pocos, el acuerdo por azar ya es casi total y el kappa queda cerca de 0. El máximo ayuda a leerlo. En la 803 el kappa queda cerca de su máximo: 0,42 frente a 0,43, o 0,422 y 0,423 si los 170 minutos no evaluados del 1 dic contaran como buenos. Casi todo lo que el control propio marca como sospechoso o malo también lo marca SIATA (7707 de 7724 registros), pero SIATA marca más, sobre todo con dos códigos que el control propio deja en bueno: el 1502, "oscilaciones fuera de rango" (14 319 de sus 14 333 registros), y el 1504 de niveles negativos (2984 de 2987), que el propio no marca a propósito. En la 35 el máximo es 0,58 y el kappa 0,07: ahí las dos banderas sí marcan minutos distintos.

## Pregunta 1.4. Cálculo de uno de los indicadores

> **Pregunta 1.4.** Para uno de los tres indicadores, escriba el pseudocódigo o la consulta (SQL o Python) que lo calcula sobre una tabla con columnas *codigo*, *fecha_hora*, *valor* y *calidad*, e indique cómo trataría las estaciones con intervalos de muestreo distintos.

Indicador elegido: completitud diaria (indicador 1), en PostgreSQL.

Supuestos: `observaciones(codigo, fecha_hora, valor, calidad)` tiene `fecha_hora` como `timestamp` sin zona, ya en hora local (la 6004, que viene en UTC, se convierte antes), y `valor` como `double precision`. El catálogo `estaciones(codigo, intervalo_s)` trae el intervalo nominal en segundos, que divide a 86 400. Colombia no tiene horario de verano: todos los días duran 86 400 s. Si la tabla trae una columna de variable, se agrega a la malla y a los `GROUP BY`.

```sql
-- Completitud diaria por estación: casillas del intervalo nominal con valor / casillas esperadas
WITH parametros AS (
    SELECT DATE '2025-12-01' AS desde, DATE '2026-04-30' AS hasta
),
malla AS (  -- todas las estaciones por todos los días, lleguen o no datos
    SELECT e.codigo, e.intervalo_s, g.dia::date AS dia
    FROM estaciones e
    CROSS JOIN parametros p
    CROSS JOIN generate_series(p.desde::timestamp, p.hasta::timestamp, INTERVAL '1 day') AS g(dia)
),
recibidas AS (  -- cada registro cae en su casilla; varios registros en una casilla cuentan una vez
    SELECT o.codigo,
           o.fecha_hora::date AS dia,
           COUNT(DISTINCT floor(extract(epoch FROM o.fecha_hora) / e.intervalo_s)) AS casillas
    FROM observaciones o
    JOIN estaciones e ON e.codigo = o.codigo
    CROSS JOIN parametros p
    WHERE o.valor IS NOT NULL
      AND o.valor NOT IN (-999, -9999)  -- centinelas de SIATA (-9999 en la guía de piranómetros)
      AND o.valor <> 'NaN'     -- en PostgreSQL NaN no es NULL
      AND o.fecha_hora >= p.desde
      AND o.fecha_hora < p.hasta + 1
    GROUP BY o.codigo, o.fecha_hora::date
)
SELECT m.codigo,
       m.dia,
       COALESCE(r.casillas, 0) AS casillas_recibidas,
       86400 / m.intervalo_s AS casillas_esperadas,
       round(COALESCE(r.casillas, 0)::numeric / (86400 / m.intervalo_s), 4) AS completitud
FROM malla m
LEFT JOIN recibidas r ON r.codigo = m.codigo AND r.dia = m.dia
ORDER BY m.codigo, m.dia;
```

La columna `calidad` no entra a propósito: la completitud cuenta lo que llegó, sin importar su bandera, que es materia del indicador 3. El filtro de fechas va sobre `fecha_hora` sin transformar, así que un índice en `observaciones(codigo, fecha_hora)` sirve para tablas grandes.

### Estaciones con intervalos de muestreo distintos

Se cuentan casillas del intervalo nominal en lugar de filas. Cada registro va a la casilla `floor(segundos desde 1970 / intervalo_s)` y el denominador es 86 400 / `intervalo_s`: 1440 casillas al día para una estación de 1 minuto, 288 para una de 5 y 144 para una de 10. Así todas quedan en la misma escala de 0 a 1, y como el intervalo divide a 86 400, ninguna casilla queda partida entre dos días.

Contar casillas distintas evita contar dos veces: una marca fuera de minuto que cae en un minuto ocupado (la 6004 tiene 15 marcas con segundos y una choca con un minuto existente) cuenta una vez, y una estación que reporta más seguido que su intervalo no pasa del 100 %. Los días sin ningún registro salen de `generate_series` con completitud 0 en vez de desaparecer, el error típico de calcularla solo con `GROUP BY`.

Si una estación cambia de intervalo, el catálogo necesita vigencia (`estaciones_intervalo(codigo, intervalo_s, desde, hasta)`): cada registro toma el intervalo vigente en su `fecha_hora` y las casillas esperadas se suman por tramo; un día que pasa de 5 a 1 minuto al mediodía espera 144 + 720 = 864.

La versión en Python es `indicadores.completitud_tabla_larga`, con la prueba `test_completitud_con_intervalos_distintos` (una estación de 1 minuto y otra de 5, completas en una hora, dan 1). La consulta SQL no se ejecutó (no hay PostgreSQL en el equipo); se revisó a mano.

## Referencias

- Cohen, J. (1960). A coefficient of agreement for nominal scales. *Educational and Psychological Measurement*, 20(1), 37-46.
- Feinstein, A. R. y Cicchetti, D. V. (1990). High agreement but low kappa: I. *Journal of Clinical Epidemiology*, 43(6), 543-549.
- Landis, J. R. y Koch, G. G. (1977). The measurement of observer agreement for categorical data. *Biometrics*, 33(1), 159-174.
- MinTIC (2022). Guía de estándares de calidad e interoperabilidad de los datos abiertos, v1, secciones 4.6, 4.7, 4.8 y 4.11 (definiciones de ISO/IEC 25012:2008).
- OMM (2017). *Guidelines on the Calculation of Climate Normals* (OMM No. 1203), sección 4.4.1 y nota 2.
- SIATA (2024). *Generalidades Repositorio de Datos*, guías P-GAA-SIATA-107, 108, 110 y 111, versión 01.
