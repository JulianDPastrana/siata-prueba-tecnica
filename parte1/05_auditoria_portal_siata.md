# 2.5 Auditoría del repositorio de datos de SIATA

## Pregunta 1.9. Auditoría del portal de datos

Revisé https://datos.siata.gov.co/ (Dataverse 6.10.1, 496 datasets) el 25 de octubre de 2026 sin iniciar sesión, como ciudadano (buscar una variable), investigador (descargar las estaciones 367, 35, 803 y 6004 y leer las guías "Generalidades") y desarrollador (API y exportaciones). En la evidencia, `B` = `https://datos.siata.gov.co` y `DS/x` = `B/api/datasets/:persistentId/?persistentId=doi:10.83041/x`; su historial agrega `versions` antes del `?`.

### (a) ¿Qué cambiaría?

a1. Sin licencia clara (investigador, desarrollador). Los términos (doi:10.83041/1CJGDM) son un borrador con "licencia XXXX" y los cuatro datasets no tienen licencia. La sección 8 parece CC BY 4.0, pero el 6.3 prohíbe el uso comercial sin autorización, modificar los datos y entrenar IA con fines comerciales. Evidencia: `curl DS/MWDZIZ` da `"license": null`; [captura](img/09_terminos_licencia_xxxx.png); términos, pp. 6 a 8. Estándar: FAIR R1.1; Ley 1712, art. 6 lit. j; MinTIC 2022, 4.13 c.

a2. Zona horaria (investigador, desarrollador). Solo la guía de piranómetros la da (UTC); los demás datos vienen en hora local (inferido del ciclo diario). En hora local, la 6004 tendría 63 861 minutos sobre la radiación extraterrestre; en UTC, 1162 (612 de realce por nubes y 550 de crepúsculo). Evidencia: guías doi:10.83041/BD6U2H p. 3 y NXHIKW p. 4, [captura](img/09_zona_horaria_generalidades.png); sello `2026-08-01 00:00:00` sin desfase. Estándar: MinTIC 2022, 4.6, p. 26 (fecha y hora en ISO 8601); FAIR R1.3.

a3. Código `calidad` mal documentado (investigador). Su diccionario está en un PDF de otro dataset y en nivel el 1504 repite el texto del 1502. Cambió su uso sin aviso: en la 803 marca 2987 de los 2988 negativos de diciembre de 2025 y ninguno de enero a abril. Las 16 versiones de los cuatro datasets no tienen nota de cambios. Evidencia: doi:10.83041/5ZOUUO p. 5, [captura](img/09_diccionario_nivel_1504.png); `versionNote` vacío en el historial de `DS/SXHWBW`. Estándar: WIGOS 8-04, p. 42; FAIR R1.2; OMM No. 1269, 3.3.3, p. 13.

a4. Estado engañoso (ciudadano). La ficha de la 6004 dice "Estado: Inactiva", pero agosto de 2026 trae 44 639 minutos. Las guías prometen datos "hasta dos meses previos" y la 367, la 35 y la 803 llegan a mayo de 2026. Evidencia: [captura](img/09_ficha_6004_inactiva.png); `publicationDate` en `curl DS/MWDZIZ`. Estándar: WIGOS 3-09, p. 25; MinTIC 2022, 4.3, pp. 21-22.

### (b) ¿Qué falta?

b1. Encontrar los datos (ciudadano, investigador). `robots.txt` bloquea a los buscadores y "SIATA" da 0 conjuntos en datos.gov.co. Las palabras clave nombran la precipitación (190 datasets) y el nivel (182), no las variables meteorológicas ni la radiación: "temperatura", "humedad" y "radiación" dan 0. Evidencia: `curl B/robots.txt`, [captura](img/09_robots_txt.png); `B/api/search?q=temperatura&type=dataset`, [captura](img/09_busqueda_temperatura.png); faceta de c1. Estándar: FAIR F4 y F2; MinTIC 2021, 4.2.3, p. 28; Ley 1712, art. 11 lit. k.

b2. Metadatos legibles por máquina (investigador, desarrollador). La descripción es una línea ("Histórico de la estación 367 - Joaquin Vallejo - Meteorologica"), sin variables, unidades, periodo ni instrumento, y schema.org sale sin `variableMeasured` ni `temporalCoverage`. Evidencia: [captura](img/09_ficha_dataset_367.png); `B/api/datasets/export?exporter=schema.org&persistentId=doi:10.83041/MWDZIZ`. Estándar: FAIR F2 y R1; WIGOS 1-02 (p. 20) y 3-07 (p. 24); MinTIC 2021, 4.2.1, p. 25.

b3. El cero del nivel (gestor del riesgo, investigador). La guía define el nivel como la distancia al fondo menos la distancia a la lámina, que no puede ser negativa, pero el 5,4 % de los minutos de la 803 lo es (mínimo -7,1 cm). Ese cero no se publica. Evidencia: `Generalidades_Nivel.pdf` p. 3; CSV de la 803. Estándar: WIGOS 7-11, p. 39.

### (c) ¿Qué sobra?

c1. Palabras clave que no distinguen (ciudadano). "Redes de Monitoreo" está en 486 de 496 datasets y "Gestión del Riesgo" en 478; la red pluviométrica aparece como "Pluvio", "Pluviómetrica", "Pluviómetro" y "Pluviométrica". Evidencia: faceta `keywordValue_ss` en `B/api/search?q=*&type=dataset&show_facets=true`. Estándar: FAIR I2 y F2.

### (d) ¿Cómo lo mejoraría?

Estimé impacto y esfuerzo; el esfuerzo fija el horizonte (matriz en [img/09_matriz_impacto_esfuerzo.png](img/09_matriz_impacto_esfuerzo.png)).

- P1 (30 días; impacto alto, esfuerzo bajo; a1). Resolver la contradicción entre el 6.3 y la sección 8 (CC BY 4.0 si el AMVA acepta uso comercial y obras derivadas; si no, otra licencia explícita) y aplicarla por API a los 496 datasets.
- P2 (30 días; impacto alto, esfuerzo bajo; a2). Declarar la zona horaria en los metadatos de cada dataset y en las guías, y publicar la 6004 en hora de Colombia.
- P3 (30 días; impacto alto, esfuerzo bajo; b1). Abrir el portal a los buscadores (`robots.txt` y sitemap, según la guía de Dataverse).
- P4 (30 días; impacto medio, esfuerzo bajo; a3, a4). Corregir el estado de la 6004, el plazo publicado y la descripción del 1504.
- P5 (90 días; impacto alto, esfuerzo medio; b1, b2, c1). Plantilla de metadatos por red (variables, unidades, periodo, instrumento) con una palabra clave por variable de un vocabulario controlado.
- P6 (90 días; impacto alto, esfuerzo medio; a3). Diccionario de calidad en los metadatos, algoritmo versionado con nota de versión y reproceso del histórico con una sola versión.
- P7 (90 días; impacto medio, esfuerzo medio; b1). Federar el catálogo en datos.gov.co.
- P8 (180 días; impacto alto, esfuerzo alto; a2). Sello con desfase (`2026-08-01T00:00:00-05:00`) en todas las redes, como nueva versión.
- P9 (180 días; impacto alto, esfuerzo alto; b3). Publicar el cero de cada estación de nivel y su historial.

## Referencias

Wilkinson et al. (2016); OMM No. 1192 (2019) y No. 1269 (2021); Ley 1712 de 2014; MinTIC (2021 y 2022); términos de uso (V1 borrador) y guías "Generalidades" de SIATA; Dataverse 6.10.1 Installation Guide.
