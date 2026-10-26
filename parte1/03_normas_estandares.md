# 2.3 Normas y estándares

## Pregunta 1.5. Una práctica por grupo de estándares

> **Pregunta 1.5.** Para cada grupo de estándares, indique en **una frase** qué práctica concreta aplicaría SIATA.

| Estándar | Tema | Aplicación en SIATA |
|---|---|---|
| DAMA-DMBOK 2 | Gobierno y dimensiones de calidad | Nombrar un custodio por red que versione el diccionario de `calidad` y cada cambio de regla, porque el 1504 repite la descripción del 1502 (P-GAA-SIATA-110, p. 5) y en la 803 dejó de aplicarse en enero sin aviso. |
| ISO 8000 e ISO/IEC 25012 y 25024 | Modelo y medición de calidad del dato | Especificar cada variable (unidad, resolución, rango y zona horaria) y medir cada mes contra esa especificación la completitud, la exactitud y la credibilidad con medidas de la ISO/IEC 25024 y umbrales propios, como los indicadores de la 1.3. |
| ISO 19115 y 19157 | Metadatos y calidad geoespacial | Publicar por estación una ficha ISO 19115 con coordenadas, altura del sensor, linaje y distancia del sensor al fondo (hoy ausente, con el 5,4 % de los niveles de la 803 negativos) y su calidad según la ISO 19157-1 (medida, método y resultado). |
| OMM No. 8 y No. 100 | Calidad de instrumentos y de datos climatológicos | Correr sobre cada minuto las pruebas de la OMM No. 8 (valor plausible, tasa de cambio y variabilidad mínima) y guardar el valor original con su bandera y la prueba que la disparó, como pide la OMM No. 100. |
| OMM No. 1131 y metadatos WIGOS | Gestión de calidad y metadatos de estaciones | Llevar en el sistema de gestión de datos climáticos (OMM No. 1131) una ficha WIGOS por estación (OMM No. 1192) con reloj, altura del sensor, referencia del nivel y versión del control de calidad (hoy la zona UTC de la 6004 solo está en P-GAA-SIATA-111, p. 3). |
| Principios FAIR | Acceso y reutilización de datos | Conservar el DOI de cada conjunto (F1) y sumarle una licencia explícita (R1.1; los términos dicen "XXXX"), la versión de la regla de calidad (R1.2) y el diccionario de banderas con el esquema de la IOC (R1.3). |

## Pregunta 1.6. Cadena de control de calidad

> **Pregunta 1.6.** Describa una cadena de control de calidad de datos meteorológicos en al menos cuatro etapas (por ejemplo: formato y completitud, rango, coherencia temporal y persistencia, coherencia interna entre variables, coherencia espacial). Para cada etapa indique una prueba concreta, su umbral y qué bandera asignaría.

La cadena está en `parte2/siata/datos.py` (etapa 1) y `parte2/siata/calidad.py` (etapas 2 a 5) y corre sobre los datos de 1 minuto. Usa las banderas de la IOC/UNESCO (1 bueno, 2 no evaluado, 3 sospechoso, 4 malo, 9 faltante) y cada dato se queda con la más severa de las pruebas que falla.

| Etapa | Prueba concreta | Variables | Umbral | Bandera |
|---|---|---|---|---|
| 1. Formato y completitud | Fecha con formato fijo, reloj a hora local (la 6004 de UTC a UTC-5), marcas con segundos llevadas al minuto y comparación contra la malla de minutos esperados | Todas | Minuto esperado sin registro o con un centinela (-999, o -9999 como dice la guía de piranómetros) | 9 |
| 2. Rango | Rango físico | h, t, pr, vv, vv_max, dv, dv_max, p, p1, p2, radiación | h 0 a 100 %; t -20 a 50 °C; pr 500 a 1100 hPa; vv 0 a 75 m/s; vv_max 0 a 150 m/s; dv y dv_max 0 a 360°; lluvia 0 a 40 mm por minuto; radiación desde -4 W/m² | 4 |
| 2. Rango | Rango climatológico del sitio | t, pr, h, vv, vv_max, p, p1, p2, nivel | t 5 a 35 °C; pr 800 a 835 hPa; h 5 a 100 %; vv hasta 30 y vv_max hasta 40 m/s; lluvia hasta 5 mm por minuto; nivel hasta 100 cm | 3 |
| 2. Rango | Límite BSRN físicamente posible | radiación | Sa × 1,5 × μ0^1,2 + 100 W/m² | 4 |
| 2. Rango | Límite BSRN extremadamente raro | radiación | Sa × 1,2 × μ0^1,2 + 50 W/m² | 3 |
| 3. Coherencia temporal | Salto entre minutos consecutivos; marca los dos minutos y no compara a través de un hueco | t, h, pr, vv, radiación, nivel | 3 °C; 10 %; 0,5 hPa; 10 m/s; 800 W/m²; 20 cm | 3 |
| 3. Coherencia temporal | Salto grande entre minutos consecutivos | t, h, pr, vv, radiación | 10 °C; 15 %; 2 hPa; 20 m/s; 1000 W/m² | 4 |
| 3. Coherencia temporal | Persistencia: máximo menos mínimo de la ventana por debajo del umbral; marca toda la ventana | t, h, pr, vv, dv | En 60 min: 0,1 °C; 1 % (solo con h < 95 %); 0,1 hPa; 0,5 m/s y 10° (solo si la media de 10 min de vv pasa de 0,1 m/s en toda la ventana) | 3 |
| 3. Coherencia temporal | Persistencia con ventana propia | nivel, radiación | 0,1 cm en 360 min; 0,01 W/m² en 30 min con el sol a más de 10° de elevación | 3 |
| 4. Coherencia interna | Ráfaga menor que la velocidad media | vv_max frente a vv | vv_max < vv | 4 |
| 4. Coherencia interna | Dirección sin viento | dv frente a vv | vv = 0 y dv > 0 | 3 |
| 4. Coherencia interna | Anemómetro que no reporta (cuádruple cero) | vv, vv_max, dv y dv_max | Las cuatro en 0 en el mismo minuto | 4 en las cuatro |
| 4. Coherencia interna | Ráfaga trabada con la media (factor de ráfaga) | vv y vv_max | vv de 5 m/s o más y vv_max < 1,1 × vv | 3 en las dos |
| 4. Coherencia interna | Radiación de noche | radiación frente a la posición del sol | Más de 5 W/m² con el sol más de 3° bajo el horizonte | 3 |
| 4. Coherencia interna | Resolución del balancín | p1, p2 | Valor que no es múltiplo de 0,254 mm | 3 |
| 4. Coherencia interna | Los dos balancines de la 35 | p1 frente a p2 | Diferencia en la hora mayor que 0,508 mm (dos vueltas) y que el 10 % de la lluvia de la hora; se marcan los minutos con lluvia de esa hora | 3 |
| 5. Coherencia espacial | Lluvia no registrada en la 367 | p de la 367 frente a p1 y p2 de la 35 (mismo sitio) | Hora con 1 mm o más en p1 y en p2 y nada en la 367 | 3 |
| 5. Coherencia espacial | Lluvia sin respaldo | p de la 367 frente a p1 y p2 de la 35 | Hora con 0,08 mm o más en la 367 (una vuelta de la 35 a la escala de la 367) y nada en p1 ni en p2 | 3 |
| 5. Coherencia espacial | Subida del nivel sin lluvia | nivel de la 803 frente a la lluvia de la 35 (a unos 240 m) | Más de 15 cm sobre su línea base con menos de 1 mm en la 35 en las 3 h previas; más de 30 cm; sin 3 h de lluvia de la 35 o sin línea base del nivel para comparar | 3; 4; 2 |

Sa es la constante solar corregida por la distancia Tierra-Sol y μ0 el coseno del ángulo cenital. Las pruebas por hora y la persistencia exigen al menos 90 % de los minutos con dato.

### Justificación de los umbrales

Límites de la OMM. Los rangos físicos, el salto en dos niveles, la variabilidad mínima en 60 minutos con sus dos condiciones y la ráfaga mayor o igual que la media son los de la OMM para datos de 1 minuto (OMM No. 488, apéndice VI.2, pp. 202 y 203; la OMM No. 8, Vol. III, sección 1.5, remite a él). La temperatura se acotó a -20 a 50 °C en vez de -90 a 70 °C, como permite la nota de la OMM para ajustar los límites al clima de la región; el rango de la velocidad, que la OMM da para promedios de 2 y 10 minutos, y su salto, que da para el de 2 minutos, se aplican a vv de 1 minuto, y el límite fijo de radiación (0 a 1600 W/m²) se cambia por los de BSRN, que dependen de la altura del sol.

Viento. La OMM pide dirección 0 sin viento y distinta de 0 con viento (el norte como 360). Solo se aplica la primera mitad: el registrador de la 367 escribe el norte como 0 (dv va de 0 a 359), y la segunda marcaba 546 minutos de viento del norte real. Las dos reglas nuevas salen del notebook 01. El cuádruple cero se trata como un anemómetro que no reporta y no como una calma. Son 46 minutos, todos con el código 1567 de SIATA, que además marca 26 minutos vecinos del 5 de marzo con viento distinto de 0, 72 en total. Ese código no está en la tabla de la guía meteorológica; por su regla de combinación sería 156 + 157, magnitud y dirección dudosas (P-GAA-SIATA-108, pp. 5 y 6). El 5 de marzo de 2026, el tramo más largo de ese día (13 minutos, de 16:33 a 16:45) empieza justo después de un minuto con 7,9 m/s. El factor de ráfaga vv_max/vv tiene mediana 1,55 y percentil 1 de 1,14 con viento de 1 m/s o más; con 5 m/s o más, 21 de 90 minutos quedan bajo 1,1 y 20 de ellos están a 30 minutos o menos de un cuádruple cero. Ese 1,1 se calibró con estos datos y debe revisarse con más historia.

Radiación. No se usa la regla de que la global no supera la extraterrestre (OMM No. 100, 2.4.6), porque con nubes dispersas la global supera por pocos minutos el valor de cielo despejado, con registros de más de 1400 W/m² (Long y Shi, 2008, p. 24). En la 6004 hay 1162 minutos sobre la extraterrestre: 612 con el sol arriba, en episodios de máximo 13 minutos (realce por nubes), y 550 con el sol bajo el horizonte, donde la extraterrestre horizontal vale 0 y basta la luz del crepúsculo. Con BSRN, 5 minutos quedan en 3 y ninguno en 4. El umbral nocturno es propio; su margen de 3° evita el error del código 1582 de SIATA, que en el 79 % de sus 977 minutos tiene el sol sobre el horizonte.

Nivel (criterios propios). Una subida de más de 15 cm sin lluvia da 3, porque el máximo en datos con calidad 1 y sin lluvia fue 14 cm, y más de 30 cm da 4; la línea base es el percentil 25 de los 7 días previos, para que las mesetas no la arrastren. Más de 100 cm da solo 3, porque puede ser una creciente real; 100 cm es casi el triple del máximo con calidad 1 (36,2 cm) y los 5041 minutos que lo superan ya traen 151 o 251 de SIATA. El salto de 20 cm queda sobre la mayor subida en un minuto del mayor evento (16,7 cm el 3 de abril de 2026), pero no sobre su caída de 23,1 cm a las 16:32 (notebook 02), que deja en 3 los dos minutos del salto (16:31 y 16:32) para revisión humana. Los negativos no se marcan: el nivel es la distancia al fondo menos la distancia a la lámina de agua (P-GAA-SIATA-110, p. 3), así que un negativo indica una distancia al fondo desactualizada, un problema de configuración. El rango climatológico de las demás variables envuelve todo lo observado (por ejemplo, t de 13,45 a 28,6 °C) y no marcó nada; la OMM No. 100 (2.4.6) pide sacarlo de la serie histórica, y cinco meses no alcanzan.

Persistencia. Las condiciones son las de la OMM (p. 203, notas 2 y 3): la humedad solo bajo 95 %, porque con niebla se queda en 100 % por horas, y el viento solo con media de 10 minutos sobre 0,1 m/s, porque en calma casi no cambia. Aun así, con el viento débil de La Ladera marca 2258 minutos en vv y 1827 en h, y los 2 episodios de temperatura (125 minutos) son de noche, cuando puede quedarse quieta de verdad (inferido). Por eso da 3 y no 4. En un punto me aparté de la norma a propósito: la OMM marca si el valor "no varía más de" el umbral, y aquí se marca si varía menos. En la 367 la resolución real de la humedad (1 %) y de la temperatura (0,1 °C) es igual al umbral, y con la versión de la OMM la humedad pasaría de 1827 a 18 737 minutos marcados (8,6 % del periodo). Con valores en pasos de la resolución, la prueba equivale a "valor idéntico durante 60 minutos". Pero el 44,9 % de los valores de h no son enteros y el 39 % de los de t no son múltiplos de 0,1 (notebook 01), así que también se marca una ventana que varía menos de un paso sin ser constante: en t la racha más larga con el mismo valor es de 50 minutos (notebook 07) y aun así se marcan 125. Lo que se escapa es un sensor que oscile un solo paso; para eso la misma página de la OMM recomienda la desviación estándar horaria, que sería la siguiente prueba a agregar.

Balancines. La tolerancia es la mayor entre dos vueltas (0,508 mm) y el 10 % de la lluvia de la hora. El 10 % es una adaptación: la OMM da una incertidumbre alcanzable de 5 % para la lluvia diaria (OMM No. 8, Vol. I, anexo 1.A, fila 6.1), pero no una tolerancia horaria entre balancines, así que sumé el 5 % de cada uno y lo apliqué a la hora. Con 0,508 mm fijos se marcaban justo las horas de tormenta, porque la diferencia entre balancines crece con la intensidad (notebook 04); con la relativa, 173 minutos en p1 y 171 en p2. La 367 se compara con la 35 solo por presencia de lluvia, porque en el mismo sitio acumula 268,6 mm frente a 848,1 mm (32 % del total); por eso el umbral de lluvia sin respaldo es 0,08 mm, lo que equivale a una vuelta de la 35 si la 367 registra de 0,28 a 0,32 veces lo de la 35. La comparación marcó 2 horas de lluvia no registrada (120 minutos) y 67 horas de lluvia sin respaldo (738 minutos).

Una bandera 3 no borra el dato: el original queda en `minutal_<codigo>.parquet` con su bandera y cada falla en `fallas.parquet` con su prueba (OMM No. 100, 2.4.3; OMM No. 1269, 2.4). El producto horario agrega solo datos con bandera 1 (en la lluvia de la 35, p1 y p2, también el 3, porque el desacuerdo entre balancines no invalida la hora), y así un extremo real no se pierde.

El orden importa al principio: con el reloj de la 6004 sin corregir, 63 861 minutos de radiación quedarían sobre la extraterrestre, frente a 1162 con el reloj corregido (notebook 05); de la etapa 2 a la 5 no importa, porque gana la bandera más severa. La bandera 2 se usa en la 803: si faltan las 3 h previas de lluvia de la 35 o la historia del nivel para la línea base, el nivel queda "no evaluado" (170 minutos: los primeros del periodo, el 1 dic 2025 de 00:00 a 02:49). En la 367 la comparación con la 35 todavía deja el dato en 1 cuando falta la 35.

La cadena tiene 34 pruebas automáticas en `parte2/tests/test_calidad.py`, de 76 en todo `parte2/tests/` (todas pasan). El escenario de la sustentación, valores plausibles congelados, está en `test_congelado_48_horas_queda_sospechoso`: congela la temperatura 48 horas y verifica que todo el tramo quede en 3 solo por persistencia.

## Referencias

- OMM No. 488 (2010, act. 2017), Guide to the Global Observing System, apéndice VI.2, pp. 202 y 203.
- OMM No. 8 (2023), Vol. I, anexo 1.A, y Vol. III, sección 1.5. OMM No. 100 (2023), secciones 2.4.3 y 2.4.6. OMM No. 1269 (2021), sección 2.4. OMM No. 1192 (2019). OMM No. 1131 (2014), número, título y año verificados (no descargado).
- Long, C. N. y Shi, Y. (2008). The Open Atmospheric Science Journal, 2, 23-37. Long, C. N. y Dutton, E. G. BSRN recommended QC tests, V2.0.
- IOC/UNESCO (2013). Quality Flag Scheme, Manuals and Guides 54, Vol. 3. Wilkinson, M. D. et al. (2016). Scientific Data, 3, 160018.
- SIATA (2024). Generalidades Repositorio de Datos, guías P-GAA-SIATA-108 (pp. 5 y 6), 110 (pp. 3 y 5) y 111 (pp. 3 a 5), versión 01. SIATA (2026). Términos y condiciones de uso, V1 borrador, sección 8.
- ISO/IEC 25024:2015 e ISO 19157-1:2023: alcance verificado en las fichas de ISO e IEC. ISO 8000, ISO/IEC 25012, ISO 19115-1 y DAMA-DMBOK 2 no se consultaron en texto completo; las frases de la tabla no dependen de su detalle.
