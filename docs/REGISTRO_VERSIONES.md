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
| **Frotz v4** | Narración en lenguaje natural + dictado por voz fiable | ✔ (2026-06-30) |
| **Frotz v5** | Zork I compilado con ZILF | ✔ (entrega de julio de 2026) |
| **Frotz v6** | Evaluación (pruebas, bancos, batería con el modelo) y correcciones | ✔ (versión entregada, 2026-11-11) |

Cada versión está en el repositorio como un commit con su etiqueta (`quest-v4`,
`frotz-v1`, `frotz-v3`, `frotz-v4`, `frotz-v5`, `frotz-v6` y `v1.0`); véase la
tabla «Versiones» del `README.md`.

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
- **Decisión técnica:** voz con la Web Speech API del navegador (sin instalación ni
  claves; en Chrome, el dictado se resuelve en un servidor del fabricante);
  catálogo se reescanea en cada `list_games` para reflejar archivos recién añadidos.
- **Verificación:** 5 tests offline en verde; tool-calls probadas con varios juegos
  y sesiones simultáneas; descubrimiento por extensión validado.
- **Archivos:** `templates/index.html`, `catalog.py`, `src/tests/*`, `games/*`, compose, docs.

## Frotz v4 — Narración natural + voz fiable  *(2026-06-30)*
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

## Frotz v5 — Zork I  *(entrega de julio de 2026)*
- **Objetivo:** jugar al Zork original.
- **Cambios:** se añade `zork1.z3` a la carpeta de juegos. No hubo cambios de código:
  el catálogo lo detecta por su extensión.
- **Decisión técnica:** en noviembre de 2025 Microsoft publicó el código fuente ZIL
  de Zork I, II y III con licencia MIT, así que el fichero de historia se compiló con
  ZILF 1.9.0 (`zilf zork1.zil` y `zapf zork1.zap`) en lugar de usar una copia de
  origen dudoso. La licencia se incluye junto al fichero.
- **Verificación:** partida jugada de extremo a extremo desde la web.
- **Archivos:** `games/zmachine/zork1.z3`.

## Frotz v6 — Evaluación y correcciones  *(versión entregada, 2026-11-11)*
- **Objetivo:** sustituir las afirmaciones cualitativas por medidas y cubrir con
  pruebas los requisitos no funcionales. No añade funcionalidad.
- **Cambios:**
  - **Pruebas (de 5 a 16):** cuatro de la capa web con un modelo simulado (doble
    envío concurrente, límite de pasos, error del proveedor, argumentos no válidos)
    y siete de seguridad (rutas, herramientas inexistentes, metacaracteres de shell
    y SAVE con el `dfrotz` real).
  - **Bancos de pruebas:** `bench_engine.py` (latencia, concurrencia, memoria y
    seguridad de Frotz) y `bench_quest.py` (latencia, concurrencia y memoria del
    puente de Quest).
  - **Batería de extremo a extremo:** `eval_llm.py` ejecuta 31 casos en lenguaje
    natural (más cinco con Quest) con el modelo real, tres veces cada uno, y
    comprueba el resultado contra el estado del motor.
- **Defectos encontrados al medir y su corrección:**
  1. SAVE, RESTORE y SCRIPT tardaban 12 s porque el indicador del intérprete no
     termina en «>» → el lector reconoce también esos indicadores (12 s → 0,12 s).
  2. Una orden de más de unos 100 caracteres hace que `dfrotz` redibuje la pantalla
     → se eliminan los caracteres de control y se limita la longitud.
  3. El hilo lector podía lanzar una excepción al cerrar la partida → se captura el
     cierre del canal.
  4. La web arrancaba con el depurador de Flask y la llamada al modelo no tenía
     tiempo máximo → depurador solo con `FLASK_DEBUG=1` y límite de 60 s.
  5. El puente de Quest esperaba 1,5 s fijos a que cargara el reproductor y, en
     frío, no arrancaba → espera a que aparezca la caja de texto (máximo 30 s).
- **Resultados principales:** 89 de 93 ejecuciones de la batería superadas (96 %);
  2,79 s de media por turno; 121 ms por orden en Frotz y 832 ms en Quest; 20
  sesiones simultáneas sin errores de aislamiento; 22 de 27 narraciones fieles a la
  salida del motor. Los ficheros están en `docker/web/src/eval/resultados`.
- **Revisión final (etiqueta `v1.0`):** `move` valida la dirección contra su esquema;
  la clave de las cookies se genera al arrancar si no se configura; el puente no
  expone los identificadores de sesión y su puerto solo se publica en el propio
  equipo; `playwright` fijado a la versión de la imagen base; catálogo sin ruta por
  defecto de Windows ni extensiones de Glulx; documentación y licencias.
- **Archivos:** `src/tests/*`, `src/eval/*`, `engines/frotz_engine.py`,
  `mcp_client.py`, `llm.py`, `web_app/app.py`, `bridge_api/app.py`, compose, docs.

---

### Líneas futuras
- Generar juegos con IA (la tercera línea del enunciado, no abordada).
- Integrar el núcleo de Quest Viva en un servicio propio, sin automatizar el navegador.
- Contexto casi sin estado en lugar del historial completo.
- Guardar y cargar partida como herramientas; puntuación y turnos reales (Jericho).
- Servicio `frotz-api` separado, comprobaciones de salud en compose y maquetación móvil.

> El historial breve está en `CHANGELOG.md`. El análisis completo de la evaluación
> y de las limitaciones está en los capítulos 5 y 6 de la memoria.
