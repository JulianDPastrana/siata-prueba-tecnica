# 2.1 Calidad de los datos: marco conceptual

## Pregunta 1.1. Qué significa que un dato tenga calidad

> **Pregunta 1.1.** Explique con sus propias palabras qué significa que un dato hidrometeorológico *tenga calidad*. Su respuesta debe:
>
> **(a)** Definir calidad como *aptitud para el uso* y vincularla al menos con tres dimensiones tomadas de un marco formal (por ejemplo DAMA-DMBOK, ISO/IEC 25012 o ISO 8000).
>
> **(b)** Distinguir entre calidad del dato, calidad del instrumento (exactitud, calibración, trazabilidad) y calidad del proceso.
>
> **(c)** Explicar por qué un dato *físicamente plausible* no es necesariamente un dato *correcto*.

### (a) Aptitud para el uso y dimensiones de calidad

Un dato hidrometeorológico tiene calidad cuando sirve para la decisión que se va a tomar con él y cuando se puede demostrar por qué sirve, por ejemplo, para generar alertas tempranas u ofrecer información oportuna de la que salgan conclusiones y acciones. Es lo que se conoce como aptitud para el uso: Wang y Strong (1996) definen la calidad de los datos como datos aptos para el uso de quienes los consumen, e ISO 8000-8 la llama calidad pragmática.

Por eso la calidad no es fija, depende del uso. Por ejemplo, la estación 35 tiene 2944 minutos con código 2 entre el 14 y el 16 de diciembre de 2025, "calidad confiable del dato no obtenido en tiempo real" según la guía de la red pluviométrica (P-GAA-SIATA-107, p. 6): no sirvieron para una alerta esos días, pero sí sirven para la lluvia del mes.

Para medir esa aptitud se parte en dimensiones. Uso las de ISO/IEC 25012, con las definiciones que cita MinTIC (2022), y su equivalente en DAMA:

| Dimensión (ISO/IEC 25012) | Qué evalúa | Equivalente en DAMA | Ejemplo en los datos |
|---|---|---|---|
| Exactitud | Si el valor representa el verdadero | Exactitud (DAMA UK) | La 367 registra el 32 % de la lluvia de la 35, en el mismo sitio: 268,6 mm frente a 848,1 mm (correlación diaria 0,986). |
| Completitud | Si están todos los registros esperados | Completitud (DAMA UK) | La 6004 tiene el 98,8 % de los minutos; su hueco más largo dura 1752 minutos (8 y 9 de abril de 2026). |
| Consistencia | Si el dato no se contradice con otros | Consistencia (DAMA UK) | En la 803 el nivel negativo sale con código 1504 en diciembre (2987 minutos) y con calidad 1 desde enero (2241 minutos solo en enero). |
| Credibilidad | Si se puede tomar como verdadero | *Believability* (Wang y Strong, en DAMA-DMBOK 2) | El 78,9 % de los 977 minutos de la 6004 con código 1582 ("mayor a 0 de noche") tiene el sol sobre el horizonte. |
| Actualidad | Si tiene la edad correcta para el uso | *Timeliness* (DAMA UK) | Los 2944 minutos con código 2 de la 35. |
| Comprensibilidad | Si se puede interpretar, con unidades y símbolos claros | Interpretabilidad (Wang y Strong) | Unidades, zona horaria y códigos están en una guía aparte por red, no en el archivo; la del nivel da al 1504 la misma descripción que al 1502 (P-GAA-SIATA-110, p. 5) y solo la de piranómetros dice que la hora está en UTC. |

ISO 8000-8 ordena lo anterior en tres niveles: sintáctico (cumple el formato), semántico (corresponde a lo que representa) y pragmático (sirve para el propósito). Un minuto de lluvia de la 367 cumple el formato, pero no corresponde a la lluvia que cayó, y por eso no sirve para una alerta por acumulado.

### (b) Calidad del dato, del instrumento y del proceso

Dentro del concepto de calidad de un dato se distinguen la calidad del instrumento, que es su capacidad de medir correctamente la variable física, y la calidad del proceso, que cubre todo el sistema de adquisición, desde la correcta toma del dato hasta su entrega oportuna.

La del instrumento se describe con términos de metrología que la OMM No. 8 (Vol. I, cap. 1) toma del VIM (JCGM 200:2012). Exactitud es qué tan cerca está lo medido del valor verdadero; lo que se cuantifica es la incertidumbre. Calibración es relacionar las indicaciones del instrumento con un patrón, cada uno con su incertidumbre (no es ajustarlo). Trazabilidad es poder llevar el resultado a una referencia por una cadena documentada de calibraciones; por ejemplo, el piranómetro de la 6004 es trazable si su constante llega hasta la Referencia Radiométrica Mundial (Vol. I, cap. 7).

La del proceso es lo que pasa entre el sensor y el usuario: sitio, adquisición, transmisión, procesamiento, control de calidad, mantenimiento y metadatos (OMM No. 8, Vol. V, 1.6), además del reloj del registrador. En los datos hay fallas de proceso que no son del sensor: la 6004 viene en UTC y las otras en hora local, y eso solo lo dice la guía de piranómetros (P-GAA-SIATA-111, p. 3), no el archivo ni la ficha; y la regla 1504 de la 803 dejó de aplicarse en enero sin una versión publicada.

La calidad del dato resulta de las dos frente a un uso, y ninguna reemplaza a la otra. Un instrumento calibrado con un proceso malo da datos malos (la 6004 leída en hora local), y un proceso impecable no corrige un sensor que mide de menos: la 367 entrega una serie completa, con calidad 1 en el 99,7 % de las filas, pero con el 32 % de la lluvia.

### (c) Físicamente plausible no es lo mismo que correcto

Un dato es físicamente plausible cuando puede ocurrir en la naturaleza, mientras que un dato correcto es aquel que realmente ocurrió en el instante en el que se midió. En la práctica hay casos en los que el instrumento llega a su límite o umbral máximo de medida y ese es el valor que reporta. Es un valor físicamente plausible, pero el valor real puede estar por fuera del rango del instrumento o, si el sensor marca el tope antes de tiempo, por debajo de él; como lo reportado no fue lo que ocurrió, el dato no es correcto.

Una prueba de rango solo dice si el valor puede ocurrir; para saber si ocurrió hacen falta otra variable, otra estación, la geometría solar o los metadatos. En los datos:

- Instrumento en su tope. La humedad de la 367 vale 100 % en 1363 minutos. La OMM No. 8 (Vol. I, 4.2.5) advierte que un sensor expuesto a condensación puede indicar 100 % con 95 % real. El 25 de febrero de 2026 marcó 100 % durante 145 minutos seguidos, en una madrugada con 5,8 mm de lluvia en la 35 (1,0 mm dentro de esos 145 minutos): pudo ser real, así que el control propio lo deja en bueno; la persistencia de la humedad solo se prueba bajo 95 % (OMM No. 488, apéndice VI.2, p. 203).
- Hora equivocada. Leída como hora local, la 6004 tiene 41 041 minutos con más de 5 W/m² y el sol más de 3° bajo el horizonte; leída como UTC, ninguno. Todos los valores están en rango; lo detecta la geometría solar.
- Error sistemático. Cada minuto de lluvia de la 367 es plausible; el error solo aparece al comparar el total con la 35.
- Valor congelado. El 5 de marzo de 2026 la 367 reporta cero en velocidad, ráfaga y las dos direcciones durante 13 minutos seguidos (46 en el periodo, todos con código 1567): una calma es posible, pero una ráfaga de 0 justo después de un minuto con 7,9 m/s apunta a un anemómetro que no reporta. En cambio, la temperatura quieta en 17,5 °C durante 50 minutos la madrugada del 30 de abril de 2026, mientras la humedad y la presión cambian, parece una noche estable. La persistencia sola no basta para declarar malo un dato.

La plausibilidad es necesaria, pero no suficiente: hacen falta pruebas de coherencia temporal, interna y espacial, y metadatos (reloj, cero de referencia, mantenimiento).

## Pregunta 1.2. Niveles del dato: crudo, validado y para consumo

> **Pregunta 1.2.** Complete la siguiente tabla y justifique en un párrafo la diferencia entre cada nivel. Incluya qué se espera que *cambie* del dato al pasar de un nivel al siguiente.

| Aspecto | Dato crudo | Dato validado con metadatos | Dato para consumo del usuario |
|---|---|---|---|
| Definición | El registro tal como sale del registrador, sin corrección. Los cuatro CSV entregados son de este nivel. | El mismo valor, sin sobrescribirlo, en una malla regular de tiempo, con bandera por variable y metadatos. | Un producto para una decisión: acumulados, promedios horarios o diarios, mapas, semáforos. |
| Unidades y resolución | Las del equipo, sin declarar en el archivo: lluvia en pasos de 0,254 mm (35) o 0,01 mm (367), nivel en float32 (5,9000244140625 cm), hora de la 6004 en UTC. | Unidades SI declaradas, resolución real del sensor (nivel a 0,1 cm), hora ISO 8601 con zona (UTC-5). | Unidades que el usuario entiende, sin falsa precisión. |
| Banderas de calidad | Códigos internos cuyo diccionario está en una guía aparte por red, con inconsistencias (1504 descrito como 1502; -9999 o -999 como faltante según la red). | Esquema estándar por variable (IOC: 1 bueno, 2 no evaluado, 3 sospechoso, 4 malo, 9 faltante), prueba que falló y versión del algoritmo. | Resumida: se publica lo aceptado y cada agregado lleva su cobertura. |
| Metadatos mínimos | Estación, variable, marca de tiempo con su zona y hora de recepción. | Identificador y coordenadas, altura del sensor, instrumento, unidades, resolución, intervalo de muestreo, zona horaria, cero de referencia, versión del algoritmo, diccionario de banderas, historial de mantenimiento y calibración, licencia. | Fuente y cita, licencia, fecha de actualización, definición del agregado, limitaciones y enlace al dato validado (linaje). |
| Tratamiento de faltantes | El minuto no llega o llega un centinela (-999 en 7 minutos de la 35). | El faltante existe en la malla con bandera 9; el centinela pasa a faltante y se registra. No se imputa. | Cobertura mínima por agregado (por ejemplo, 75 % de los minutos de la hora); si se imputa, se marca y se dice cómo. |
| Usuario típico | Operación y mantenimiento de la red; quien reprocesa o audita. | Científicos de datos, investigadores, modeladores. | Ciudadanía, gestión del riesgo, medios, desarrolladores que usan una API. |
| Riesgo de mal uso | Tomarlo como verdad: leer la 6004 en hora local, promediar un -999. | Ignorar las banderas o creerles sin revisar; mezclar versiones del algoritmo. | Tomar un agregado con huecos como completo o un dato provisional como oficial. |

La diferencia entre niveles está en a quién le sirve el dato y qué garantías trae. El crudo es la evidencia y se guarda tal cual para reprocesar y auditar. Al pasar a validado el valor no cambia, cambia lo que se sabe de él: la hora queda en una zona declarada, los faltantes quedan explícitos, cada valor recibe su bandera y se le adjuntan los metadatos (es el paso del control en la estación al control en el centro de datos de la OMM No. 488, apéndice VI.2). Al pasar a consumo sí cambia el dato: se filtra por bandera y se agrega, se pierde detalle a cambio de que se entienda, y por eso debe enlazar con el validado del que sale. En términos de ISO 8000-8, el crudo garantiza a lo sumo la calidad sintáctica, el validado aporta evidencia de la semántica y el de consumo se hace para la pragmática de un uso.

Los metadatos del validado siguen las diez categorías de WIGOS (OMM No. 1192) e ISO 19115-1 (extensión, sistema de referencia, linaje, restricciones de uso). Para estas estaciones faltan varios en el archivo y en la ficha: la zona horaria solo aparece en la guía de piranómetros; la guía del nivel define el nivel como la distancia del sensor al fondo menos la distancia a la lámina de agua (P-GAA-SIATA-110, p. 3), pero no publica la distancia al fondo de la 803 ni sus cambios, y el 5,4 % de los niveles es negativo; y los términos de uso del repositorio (borrador, sección 8) dejan la licencia como "XXXX".

## Referencias

- DAMA International (2017). *DAMA-DMBOK 2*, cap. 13. DAMA UK (2013). *The six primary dimensions for data quality assessment*.
- IOC (2013). *Recommendation for a quality flag scheme* (Manuals and Guides 54, Vol. 3).
- ISO/IEC 25012:2008, ISO 8000-8:2015 e ISO 19115-1:2014 (no consultadas en texto completo). JCGM 200:2012 (VIM).
- MinTIC (2022). *Guía de estándares de calidad e interoperabilidad de los datos abiertos*, secciones 4.3, 4.6 a 4.8, 4.11 y 4.12.
- OMM No. 8 (2023), Vol. I y V. OMM No. 488 (2010, act. 2017), apéndice VI.2. OMM No. 1192 (2019).
- SIATA (2024). *Generalidades Repositorio de Datos*, guías P-GAA-SIATA-107 (pluviométrica), 108 (meteorológica), 110 (nivel) y 111 (piranómetros), versión 01, aprobadas el 2025/12/04.
- SIATA (2026). *Términos y condiciones de uso, Repositorio de Datos SIATA*, V1, borrador.
- Wang, R. Y. y Strong, D. M. (1996). Beyond accuracy: what data quality means to data consumers. *Journal of Management Information Systems*, 12(4), 5-33.
