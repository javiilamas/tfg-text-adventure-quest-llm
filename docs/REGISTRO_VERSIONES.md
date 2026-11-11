# Registro de versiones — TFG: Aventuras conversacionales con LLM (multi-motor)

Documento de seguimiento para la **memoria**. Recoge la evolución del proyecto
desde la integración inicial con Quest hasta el sistema multi-motor con Frotz,
menú gestionado por IA, interfaz de videojuego y voz. Cada versión documenta:
**objetivo**, **cambios**, **decisiones técnicas** (con su justificación),
**verificación** y **archivos afectados**.

## Resumen de versiones

| Versión | Hito | Estado |
|---------|------|--------|
| Base (pre-Frotz) | Integración LLM ↔ Quest Viva (tool-calling manual) | Punto de partida |
| **Frotz v1** | Abstracción multi-motor + integración Frotz (Z-machine) | ✔ |
| **Frotz v2** | Robustez de la capa web + Quest funcionando en Docker | ✔ |
| **Frotz v3** | Interfaz de videojuego, voz, catálogo *drop-in*, tests | ✔ |
| **Frotz v4** | Narración en lenguaje natural + dictado por voz fiable | ✔ (actual, 2026-06-30) |

---

## Base — Punto de partida (Quest)
- **Objetivo:** que el usuario juegue a una aventura (Quest Viva) en lenguaje
  natural; el LLM decide acciones vía *tool calls*, el motor es la fuente de verdad.
- **Arquitectura:** `web-app` (Flask + OpenRouter) → Bridge (FastAPI + Playwright)
  → Quest Viva WebPlayer (Docker). Tools: `new_game`, `look`, `move`. Sesión fija `demo`.
- **Limitaciones detectadas:** ruta del `.quest` codificada (Windows), sesión única,
  bucle de tools incompleto (aparecía "🤖 None"), condicionales acoplados.

## Frotz v1 — Multi-motor + Frotz
- **Objetivo:** soportar varios motores y juegos sin condicionales dispersos, y
  añadir Zork/Z-machine mediante Frotz.
- **Cambios:** abstracción `GameEngine` con `QuestEngine` (reusa el Bridge) y
  `FrotzEngine` (`dfrotz` por subprocess); `catalog.py` y `SessionManager`
  (fin del `demo`); tools de menú `list_games`/`start_game`/`current_game`/
  `close_game` + `send_game_command` (+ atajos `look`/`move`); bucle multi-tool;
  Docker con `frotz`; juego demo original `minizork.z5`.
- **Decisiones técnicas (justificación):**
  - **`dfrotz` (interfaz dumb), no el `frotz` de curses:** escribe línea a línea por
    stdout/stdin → **no necesita pseudo-terminal (pty)**. Flags `-m` (sin prompts
    MORE, evita bloqueos), `-p` (ASCII), `-w` (ancho), `-R` (confina SAVE → seguridad).
  - **Lectura sin bloqueo:** un proceso por sesión + hilo lector + cola + idle-timeout
    + detección de prompt; lock por sesión (nada de variable global de proceso).
  - **ZILF no es necesario para *jugar*** (solo compila ZIL→Z-machine); queda fuera del runtime.
- **Verificación:** `minizork.z5` jugado de extremo a extremo; FrotzEngine probado
  con sesiones concurrentes aisladas y cierre correcto.
- **Archivos:** `engines/{base,quest_engine,frotz_engine}.py`, `catalog.py`,
  `sessions.py`, `tools.py`, `mcp_client.py`, `web_app/app.py`, Dockerfile, compose.

## Frotz v2 — Robustez web + Quest en Docker
- **Objetivo:** eliminar el error 400 del proveedor y hacer que Quest cargue dentro de Docker.
- **Cambios:**
  - **Lock por sesión** + **auto-reparación del historial**: corrige
    "*An assistant message with 'tool_calls' must be followed by tool messages*"
    ante dobles envíos / peticiones interrumpidas. Una sesión ya no queda inutilizada.
  - **Quest en Docker:** se monta el `.quest` en el contenedor del Bridge y la ruta
    pasa a Linux (`/data/game.quest`); el Bridge tolera el *autoload* del WebPlayer.
- **Decisión técnica:** la corrupción venía de un historial compartido mutado por
  peticiones concurrentes → la solución correcta es serializar por sesión y, además,
  sanear el historial antes de cada llamada (defensa en profundidad).
- **Verificación:** test de doble-envío concurrente (sin huérfanos) y de reparación idempotente.
- **Archivos:** `web_app/app.py`, `docker-compose.yaml`, `bridge_api/app.py`.

## Frotz v3 — Experiencia: interfaz, voz, catálogo y calidad
- **Objetivo:** experiencia tipo videojuego, añadir juegos sin tocar código y elevar la calidad.
- **Cambios:** interfaz **terminal CRT retro**; **autodescubrimiento** de juegos por
  carpeta/extensión (`docker/web/games/{zmachine,quest}`, volumen *drop-in*);
  **voz** TTS/STT (Web Speech API); botón **reiniciar** + juego activo en cabecera;
  **logging** (`DEBUG_LLM`); **suite de tests offline** (intérprete falso, sin red);
  **segundo juego original** "La Cueva" (`cave.z5`, puzzle linterna+llave); docs.
- **Decisión técnica:** voz 100% en el navegador (sin servicios ni claves);
  catálogo se reescanea en cada `list_games` para reflejar archivos recién añadidos.
- **Verificación:** 5 tests offline en verde; tool-calls probadas con varios juegos
  y sesiones simultáneas; descubrimiento por extensión validado.
- **Archivos:** `templates/index.html`, `catalog.py`, `src/tests/*`, `games/*`, compose, docs.

## Frotz v4 — Narración natural + voz fiable  *(versión actual, 2026-06-30)*
- **Objetivo:** que el LLM narre la situación en lenguaje natural (no liste comandos)
  y que el botón de micrófono funcione de forma fiable.
- **Cambios:**
  - **System prompt de NARRADOR**: prohíbe mostrar comandos/listas; traduce la salida
    técnica a prosa ("hay una linterna posada sobre la roca" en vez de "comando
    TAKE LANTERN disponible"); el motor sigue siendo la fuente de verdad.
  - **Intros de los juegos demo** reescritas sin listar comandos.
  - **Micrófono robusto:** máquina de estados (idle/starting/listening) que arregla
    el error "*recognition has already started*" (toggle + auto-reinicio), nunca se
    deshabilita y muestra siempre el motivo si falla (sin permiso, navegador, etc.).
- **Decisión técnica:** `SpeechRecognition.start()` lanza excepción si ya estaba
  activo; se gestiona con estado sincrónico + `abort()` + reintento en `onend`.
- **Verificación:** JS validado (parseo), 5 tests offline en verde, juegos recompilados
  y jugados. (El dictado depende del navegador: Chrome/Edge + permiso de micrófono.)
- **Archivos:** `web_app/app.py` (prompt), `templates/index.html` (voz),
  `games/zmachine/{minizork,cave}.{inf,z5}`.

---

### Próximas versiones candidatas (roadmap)
- **Frotz v5:** Zork I–III reales (script de compilación con ZILF) en la carpeta *drop-in*.
- Guardar/cargar partida (`save`/`restore`) como tools de Frotz.
- Puntuación y turnos reales (motor opcional con Jericho).
- Servicio `frotz-api` separado (simetría con el Bridge de Quest).
- Healthchecks en compose y maquetación móvil.

> Convención: la versión actual se indica arriba en "Resumen" y en el título de la
> última entrada. El historial breve y orientado a desarrollo está en `CHANGELOG.md`.
