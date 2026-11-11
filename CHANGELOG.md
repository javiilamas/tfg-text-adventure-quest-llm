# CHANGELOG

## v2.4 — Narracion natural y voz robusta
- 🗣️ El LLM ahora NARRA en lenguaje natural (system prompt reforzado): nunca
  lista comandos; traduce la salida del motor a prosa ("hay una linterna posada
  sobre la mesa" en vez de "comando TAKE LANTERN disponible").
- 🎤 Boton de microfono **siempre reactivo**: ya no se desactiva nunca y muestra
  el motivo exacto si falla (sin permiso, navegador sin soporte, etc.). Creacion
  perezosa del reconocedor (evita que un error lo deje "muerto").
- 🎮 Juegos demo con intro inmersiva (sin listar comandos): minizork, cave.


## v2.3 — Voz, segundo juego y calidad
- 🎤🔊 **Voz**: text-to-speech (leer respuestas) y speech-to-text (hablar comandos)
  con la Web Speech API del navegador (sin servicios externos ni claves).
- 🕹️ Botón **Reiniciar** (`/reset`) y juego activo mostrado en la cabecera.
- 🪵 **Logging** opcional (`DEBUG_LLM=1`): traza cada tool-call y su resultado.
- 🗺️ Segundo juego original incluido: **La Cueva** (`cave.z5`, puzzle linterna+llave).
- ✅ **Suite de tests offline** (`src/tests/`) con un interprete falso (sin frotz/red).
- 📄 Docs: este CHANGELOG, `.env.example`, README actualizado.

## v2.2 — Interfaz y catalogo
- 🖥️ **Interfaz tipo videojuego**: terminal CRT retro (fosforo verde, scanlines,
  brillo, cursor parpadeante).
- 📂 **Autodescubrimiento de juegos**: deja un fichero en `docker/web/games/{zmachine,quest}`
  y aparece solo en el menu segun su extension (.z3/.z5/... o .quest). Volumen
  montado: no hace falta reconstruir la imagen.

## v2.1 — Robustez y arreglo de Quest
- 🔒 **Lock por sesion** + **auto-reparacion del historial**: corrige el 400
  "tool_calls must be followed by tool messages" ante dobles envios/peticiones
  interrumpidas. Una sesion ya no queda "envenenada".
- 🧩 **Quest en Docker**: el `.quest` se monta en el contenedor del Bridge y la
  ruta pasa a ser Linux (`/data/game.quest`); el Bridge tolera el autoload.

## v2.0 — Multi-motor + Frotz + menu por IA
- 🧱 Abstraccion **GameEngine** con **QuestEngine** (reusa el Bridge actual) y
  **FrotzEngine** (`dfrotz` dumb por subprocess, un proceso por sesion, hilo
  lector + idle-timeout + lock; sin pty).
- 🗂️ Catalogo de juegos + **SessionManager** (fin del `sessionId="demo"`).
- 🛠️ Tools de menu: `list_games`, `start_game`, `current_game`, `close_game` +
  `send_game_command` + atajos `look`/`move`. Bucle multi-tool en Flask.
- 🐳 Docker: `frotz` en el web-app; juego demo original `minizork.z5`.

## v1.0 — Base Quest (punto de partida)
- Integracion LLM ↔ Quest Viva via Bridge (FastAPI + Playwright). Tools
  `new_game`, `look`, `move`. Flujo de tool-calling manual sobre OpenRouter.
