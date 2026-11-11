# TFG · Aventuras conversacionales con LLM (Quest + Frotz)

Juega a aventuras conversacionales en **lenguaje natural** (o por **voz**): el LLM
traduce lo que dices a *tool calls* controladas; cada **motor** de juego es la
fuente de verdad. Conserva la integracion **Quest** y anade **Frotz** (Zork y
otros juegos Z-machine) con un **menu de juegos gestionado por la IA**.

## Arranque

```bash
cp .env.example .env     # y pon tu OPENROUTER_API_KEY  (si ya tienes .env, omite)
docker compose up --build
#  Web:    http://localhost:8100
#  Quest:  http://localhost:8080   ·   Bridge: http://localhost:8787
```

En la web (escribe o pulsa 🎤): "¿qué juegos hay?", "juega a minizork",
"abre el buzón", "ve al norte", "ahora juega a cave", "enciende la linterna".

## Funciones

- **Multi-motor** detras de una interfaz comun `GameEngine`:
  - `QuestEngine` → reutiliza el Bridge (FastAPI + Playwright) existente.
  - `FrotzEngine` → `dfrotz` (dumb) por subprocess; 1 proceso por sesion, hilo
    lector + idle-timeout + lock; **sin pseudo-terminal**.
- **Menu por IA**: `list_games`, `start_game`, `current_game`, `close_game` y
  `send_game_command` (+ atajos `look`/`move`).
- **Carpeta drop-in**: deja un `.z3/.z5/...` en `docker/web/games/zmachine/` o un
  `.quest` en `docker/web/games/quest/` y aparece solo (ver `docker/web/games/README.md`).
- **Interfaz tipo videojuego**: terminal CRT retro.
- **Voz**: 🔊 leer respuestas (TTS) y 🎤 hablar comandos (STT) — Web Speech API
  (Chrome/Edge), sin servicios externos.
- **Reiniciar** partida/conversacion con el boton ⟲.
- **Robustez**: lock por sesion + auto-reparacion del historial (sin errores 400).
- **Juegos incluidos** (originales, sin copyright): `minizork.z5`, `cave.z5`.

## Tests

```bash
docker compose run --rm web-app python -m unittest discover -s src/tests
```
Usan un interprete falso (`fake_frotz.py`): no necesitan frotz real ni red.

## Anadir Zork I–III

No necesitas ZILF para *jugar*, solo el `.z3/.z5`. Para generarlos legalmente,
compila su codigo fuente abierto con ZILF/ZAPF y copia `zork1.z3` en
`docker/web/games/zmachine/` (ver `docker/web/games/zmachine/README.md`).

## Seguridad

`send_game_command` solo escribe en la entrada del proceso del juego (sin shell,
`Popen` con lista de args, `dfrotz -R` confina los SAVE). El LLM nunca ejecuta
comandos del sistema.

## Estructura (lo nuevo)

```
docker/web/
├── games/                      # carpeta drop-in (volumen)
│   ├── zmachine/ (minizork.z5, cave.z5, +tus .z3/.z5)
│   └── quest/    (+tus .quest)
└── src/
    ├── llm_client/
    │   ├── engines/ (base, quest_engine, frotz_engine)
    │   ├── catalog.py   sessions.py   tools.py   mcp_client.py(router)
    │   └── ...
    ├── web_app/ (app.py: bucle+lock+reset+logging; templates/index.html: UI+voz)
    └── tests/ (fake_frotz.py, test_engine.py)
```

Conservado intacto: Quest Viva, `quest-webplayer`, integracion Playwright.
Ver `CHANGELOG.md` para el historial de versiones.
