# Soporte multi-motor (Quest + Frotz) y menu de juegos por IA

Evolucion incremental del TFG sobre la version funcional de Quest. **No se
elimina nada de la integracion Quest**: pasa a ser "un motor mas" detras de una
abstraccion comun. Se anade **Frotz** (Zork y otros juegos Z-machine) y un
**menu de juegos gestionado por la IA** en lenguaje natural.

## Arranque

```bash
docker compose up --build
# Web:    http://localhost:8100
# Quest:  http://localhost:8080   (sin cambios)
# Bridge: http://localhost:8787   (sin cambios)
```

Prueba en la web (lenguaje natural):
- "¿a que juegos puedo jugar?"  -> list_games
- "juega a minizork"            -> start_game(minizork)  [motor Frotz, incluido]
- "abre el buzon" / "lee el folleto" / "ve al norte"
- "ahora quiero el juego de Quest" -> start_game(quest_tutorial) [motor Quest]

> `minizork` funciona sin pasos extra. Para Zork I ver
> `docker/web/games/zmachine/README.md`.

## Arquitectura

```
Usuario -> Flask (web-app) -> LLM (OpenRouter) -> tool call controlada
        -> SessionManager -> GameEngine (Quest | Frotz) -> resultado real
        -> role="tool" (tool_call_id) -> LLM -> respuesta final
```

- **`GameEngine`** (interfaz comun): `start_game / send_command / get_state /
  move / close_game`.
  - **`QuestEngine`**: reutiliza el Bridge FastAPI+Playwright actual (HTTP).
  - **`FrotzEngine`**: lanza `dfrotz` (dumb) por subprocess; un proceso por
    sesion, hilo lector + cola + idle-timeout + deteccion de prompt, lock por
    sesion. Sin pseudo-terminal. Flags `-m -p -w 80 -R <dir>`.
- **`catalog.py`**: catalogo declarativo de juegos (id, nombre, motor, ruta).
- **`sessions.py`**: `SessionManager` por usuario; sustituye al `demo` global.
- **Tools**: menu (`list_games`, `start_game`, `current_game`, `close_game`) +
  `send_game_command` (workhorse) + atajos `look`/`move`/`new_game`.
- **Flask**: bucle multi-tool `run_llm_tool_loop(max_steps)` con sesion por
  navegador (arregla el caso en que tras una tool el modelo pedia otra y se
  quedaba sin respuesta).

## Seguridad

`send_game_command` SOLO escribe en la entrada del proceso del juego. Nunca hay
shell (`Popen` con lista de argumentos, sin `shell=True`); `dfrotz -R` confina
las lecturas/escrituras de SAVE/RESTORE a un directorio. Un texto tipo
`"; rm -rf /"` lo interpreta el parser del juego como comando de juego, no el SO.

## Ficheros nuevos / modificados

Nuevos (en `docker/web/src/llm_client/`):
- `engines/base.py`, `engines/quest_engine.py`, `engines/frotz_engine.py`,
  `engines/__init__.py`
- `catalog.py`, `sessions.py`
Nuevos (datos): `docker/web/games/zmachine/minizork.z5` (+ `.inf` fuente, README)
Modificados:
- `tools.py` (tools de menu + send_game_command)
- `mcp_client.py` (router -> SessionManager -> motor; fin del `demo` y de la ruta Windows)
- `web_app/app.py` (bucle multi-tool + sesiones por usuario)
- `web_app/templates/index.html` (UI minima mejorada)
- `docker/web/Dockerfile` (instala `frotz`; fija `FROTZ_BIN=/usr/games/dfrotz`)
- `docker-compose.yaml` (env del web-app; quest-webplayer y bridge-api intactos)

Conservado intacto: `docker/bridge/**` (Bridge Playwright), `docker/quest-webplayer/**`.
Legado V1 (no se ejecuta, se conserva): `docker/bridge/src/mcp_server/**`,
`docker/bridge/src/engine/**`, `worlds/**`.

## Verificacion realizada

- `minizork.z5` compilado y jugado de extremo a extremo.
- `FrotzEngine` probado contra un interprete real-equivalente: start, look,
  open mailbox, read leaflet, move; **dos sesiones concurrentes aisladas**;
  stress de 8 hilos sobre una sesion sin errores; cierre correcto.
- Router (list_games/start_game/current_game/send_game_command/move) y bucle
  multi-tool de Flask validados (cada tool_call_id recibe su respuesta).
- QuestEngine degrada con error claro si el Bridge no responde.
- El Bridge y el resto de Quest no se han tocado.

## Git sugerido

```bash
git add . && git commit -m "Version funcional de Quest con new_game look y move"
git checkout -b feature/frotz-multigame
git add . && git commit -m "Multi-motor GameEngine + Frotz (minizork) + menu de juegos por IA"
```
