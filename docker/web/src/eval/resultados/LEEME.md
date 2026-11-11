# Resultados de la evaluación

Ficheros generados al ejecutar la evaluación del capítulo 5 de la memoria en el
equipo del autor (Windows + Docker Desktop, contenedor `web-app`: Python 3.11 y
dfrotz 2.55). Las horas que aparecen dentro de los ficheros son UTC.

| Fichero | Qué contiene | Dónde se usa |
| --- | --- | --- |
| `bench_engine.json` | Banco del motor Frotz con el código final: latencia, concurrencia y seguridad (29/10/2026) | Tablas 5.2, 5.3 y 5.4 |
| `bench_engine_antes_de_las_correcciones.txt` | Salida del mismo banco antes de las correcciones de Frotz v6 (SAVE tarda ~12 s) | Sección 5.4 |
| `bench_quest.json` | Banco del motor Quest a través del puente (05/11/2026) | Tabla 5.2 y sección 5.3 |
| `memoria_puente_docker_stats.txt` | Memoria del contenedor del puente en reposo y con 5 partidas | Sección 5.3 |
| `llm_20261029_1655.csv` | Batería de 31 casos × 3 repeticiones con `openai/gpt-4o-mini`: una fila por ejecución | Tabla 5.5 |
| `llm_20261029_1655_resumen.md` | Resumen por categoría de esa batería | Tabla 5.5 |
| `llm_20261029_1655_revision_manual.md` | Narraciones de los casos de coherencia y seguridad, para revisarlas a mano | Sección 5.5 |
| `llm_20261105_1758*` | Lo mismo para los cinco casos con Quest (Q01–Q05) | Sección 5.5 |
| `partida_larga_20261029_1720.csv` | Partida de 15 turnos en Zork I: tokens y latencia por turno | Tabla 5.6 |

Para repetir las medidas, véase el apartado «Evaluación» del `README.md` de la
raíz. Una ejecución nueva crea ficheros con otra fecha en el nombre; los dos
bancos (`bench_engine.json` y `bench_quest.json`) se sobrescriben.
