# CHANGELOG (resumen)

Historial breve de desarrollo. El registro detallado para la memoria está en
`docs/REGISTRO_VERSIONES.md`.

## Frotz v6 — Evaluación y correcciones  (versión entregada, noviembre de 2026)
- ✅ 11 pruebas nuevas (16 en total): capa web con un modelo simulado y seguridad
  con el `dfrotz` real.
- 📏 Bancos de pruebas de los motores (`bench_engine.py`, `bench_quest.py`) y
  batería de extremo a extremo con el modelo real (`eval_llm.py`, 31 + 5 casos).
  Resultados en `docker/web/src/eval/resultados`.
- 🐛 Defectos que destapó la evaluación, ya corregidos:
  - SAVE, RESTORE y SCRIPT tardaban 12 s: el lector no reconocía los indicadores
    del propio intérprete («Please enter a filename», «Overwrite existing file?»).
  - Las órdenes largas ensuciaban la salida: ahora se eliminan los caracteres de
    control y se limita la longitud.
  - El hilo lector podía fallar al cerrar una partida.
  - La web arrancaba con el depurador de Flask activado y la llamada al modelo no
    tenía tiempo máximo.
  - El puente de Quest esperaba 1,5 s fijos a que cargara el reproductor y, en
    frío, no arrancaba: ahora espera a que aparezca la caja de texto del juego.
- 🔎 Revisión final (etiqueta `v1.0`):
  - `move` solo acepta las seis direcciones de su esquema; antes el enrutador
    pasaba al motor cualquier texto.
  - La clave de las cookies ya no tiene un valor por defecto: si no se define
    `FLASK_SECRET`, se genera una aleatoria en cada arranque.
  - El puente no devuelve los identificadores de sesión en `/health` y su puerto
    solo se publica en el propio equipo.
  - `playwright` fijado a la versión de la imagen base (1.59.0): sin fijar, una
    instalación nueva no encontraba Chromium.
  - Catálogo: fuera la ruta de Windows por defecto y las extensiones de Glulx,
    que Frotz no ejecuta.
  - El intérprete falso de las pruebas conserva el permiso de ejecución.
  - `README.md` nuevo, licencia de Zork I, `.gitignore` y `.gitattributes`.

## Frotz v5 — Zork I  (entrega de julio de 2026)
- 🏛️ `zork1.z3`, compilado con ZILF a partir del código fuente que Microsoft
  publicó con licencia MIT. Sin cambios de código: lo detecta la carpeta de juegos.

## Frotz v4 — Narración natural + voz fiable
- 🗣️ System prompt de NARRADOR: el LLM nunca lista comandos; traduce la salida del
  motor a lenguaje natural ("hay una linterna posada sobre la roca").
- 🎤 Micrófono robusto: máquina de estados que arregla "recognition has already
  started"; nunca se deshabilita y siempre explica el motivo si falla.
- 🎮 Intros de los juegos demo reescritas sin listar comandos.

## Frotz v3 — Interfaz, voz, catálogo y calidad
- 🖥️ Interfaz terminal CRT retro (videojuego).
- 📂 Autodescubrimiento de juegos por carpeta/extensión (drop-in, volumen).
- 🎤🔊 Voz: TTS (leer) y STT (hablar) con la Web Speech API.
- 🕹️ Botón reiniciar + juego activo en cabecera. 🪵 Logging (DEBUG_LLM).
- ✅ Suite de tests offline (intérprete falso). 🗺️ Segundo juego original: La Cueva.

## Frotz v2 — Robustez web + Quest en Docker
- 🔒 Lock por sesión + auto-reparación del historial (fin del error 400).
- 🧩 .quest montado en el Bridge + ruta Linux; Bridge tolerante al autoload.

## Frotz v1 — Multi-motor + Frotz
- 🧱 GameEngine + QuestEngine (reusa el Bridge) + FrotzEngine (dfrotz, sin pty).
- 🗂️ Catálogo + SessionManager; tools de menú + send_game_command; bucle multi-tool.
- 🐳 Docker con frotz; juego demo original minizork.

## Base (pre-Frotz)
- Integración LLM ↔ Quest Viva (Bridge FastAPI + Playwright). Tools new_game/look/move.
