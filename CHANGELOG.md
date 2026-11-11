# CHANGELOG (resumen)

Historial breve de desarrollo. El registro detallado para la memoria está en
`docs/REGISTRO_VERSIONES.md`.

## Frotz v4 — Narración natural + voz fiable  (actual)
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
