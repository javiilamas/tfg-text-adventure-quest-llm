# Diseño: soporte multi-motor (Quest + Frotz) y menú de juegos por IA

**TFG — Integración de LLM con motores de aventura conversacional mediante tool-calling**
Documento de diseño previo a la implementación. No sustituye nada del código actual; describe cómo evolucionarlo de forma incremental conservando la integración Quest Viva.

---

## 0. Aclaración importante antes de empezar

He revisado el código real del ZIP, no solo la descripción. Hay **diferencias entre lo que describes y lo que está commiteado**. Las señalo porque afectan al diseño y porque tú mismo pediste "confirmar qué hay realmente":

1. Las tools **no están declaradas en `llm.py`**, sino en `docker/web/src/llm_client/tools.py`. `llm.py` solo hace el POST a OpenRouter e **importa** `tools` desde `tools.py`.
2. El `web_app/app.py` commiteado **no implementa el bucle multi-tool**. Ejecuta **una sola** tool (`msg["tool_calls"][0]`) y hace **una** segunda llamada. El bucle `run_llm_tool_loop(max_steps=5)` que describes está **solo en `PROMPT1.0.txt`**, no en el `app.py` del ZIP. De hecho el log `JugandoEnElTerminal.txt` muestra el síntoma de esto: tras `look` aparece `🤖 None` porque el segundo tool-call se quedó sin respuesta.
3. Existe un **segundo árbol de "tools" heredado** en `docker/bridge/src/mcp_server/server.py` (servidor `FastMCP` para Claude Desktop, con 7 tools) y un **motor propio en JSON** en `docker/bridge/src/engine/`. **Ninguno de los dos se ejecuta** en el `docker-compose` actual (compose solo arranca `uvicorn ...bridge_api.app:app`). Son la V1 del proyecto, conviven en el repo pero están desconectados del flujo web.

Conclusión: el flujo realmente activo es **Flask `app.py` → `llm.py` (+`tools.py`) → `mcp_client.py` → Bridge FastAPI/Playwright → Quest**. Todo lo demás (`mcp_server`, `engine/`, `worlds/`) es legado.

---

## 1. Resumen de la arquitectura real actual

Tres servicios en `docker-compose.yaml`, exactamente como describes, con un matiz en rutas:

| Servicio | Imagen / build | Puerto host | Rol real |
|---|---|---|---|
| `quest-webplayer` | `ghcr.io/textadventures/quest-viva-webplayer:latest` | 8080 | Sirve Quest Viva WebPlayer. Autocarga `/data/game.quest` (`Home__File`). Volumen `:ro`. |
| `bridge-api` | build `docker/bridge` (imagen Playwright) | 8787 | FastAPI + Playwright/Chromium headless. Carga el `.quest`, escribe comandos en el DOM, lee `body`. |
| `web-app` | build `docker/web` (python:3.11-slim) | 8100→5000 | Flask + cliente OpenRouter + gestión manual de tool-calling. |

**Flujo de una jugada (real):**

```
Usuario → form HTML (Flask)
       → messages[] (global) → call_llm() → OpenRouter (gpt-4o-mini) con tools
       → si hay tool_calls: call_tool(name,args) → HTTP POST al Bridge
       → Bridge: Playwright escribe en el input de Quest, lee el DOM (page.inner_text("body"))
       → role="tool" (con tool_call_id) → call_llm() de nuevo → texto final → chat_history
```

**Puntos clave del Bridge (`quest_bridge/bridge_api/app.py`):**

- Endpoints: `GET /health`, `POST /session/new {sessionId, questFilePath}`, `POST /session/command {sessionId, text}`, `POST /session/close {sessionId}`.
- **Ya es multi-sesión**: `SESSIONS: Dict[str, ...]` (un browser/context/page por `sessionId`) y `LOCKS: Dict[str, asyncio.Lock]` (un lock por sesión). Esto es un buen diseño que conviene **reaprovechar**.
- Lectura de resultado: devuelve `page.inner_text("body")` **completo** + flag `changed` (compara antes/después). No aísla la "última respuesta"; el LLM recibe toda la pantalla (se ve en los logs: menús, signos, score…).
- Espera fija `wait_for_timeout(600)` tras Enter (frágil, pero funcional).

**Limitaciones estructurales actuales:**

- `mcp_client.py` **fija `sessionId="demo"`** y una **ruta Windows hardcodeada** (`C:\Users\lecle\...juego_prueba.quest`) en `new_game`. En el contenedor Linux esa ruta no existe; funciona porque Quest autocarga el juego por `Home__File` y/o porque el navegador ya tiene el juego cargado, pero es frágil y hay que eliminarlo.
- Flask usa `messages` y `chat_history` **globales de módulo** → una sola conversación para todo el proceso (no hay multiusuario real).
- No existe ningún concepto de "motor" ni de "juego seleccionable": el juego está implícito.

---

## 2. Lista de tools realmente disponibles

**Tools activas en el flujo web** — declaradas en `tools.py`, implementadas en `mcp_client.py`:

| Tool | Args | Implementación real |
|---|---|---|
| `new_game` | `{}` | `POST /session/new` con `sessionId="demo"` y ruta Windows hardcodeada |
| `look` | `{}` | `POST /session/command` `text="look"` |
| `move` | `{direction: north\|south\|east\|west}` | `POST /session/command` `text="go {direction}"` |

Es decir: **3 tools reales**, todas con sesión `"demo"`.

**Tools heredadas (NO activas)** — en `mcp_server/server.py` (FastMCP, Claude Desktop, no arranca en compose): `new_game`, `look`, `move`, `take`, `drop`, `use`, `state`. Importan el motor JSON (`engine/`) pero sus cuerpos en realidad llaman al Bridge. Sirven como referencia de hacia dónde ibas, pero no son parte del sistema en ejecución.

---

## 3. Propuesta de arquitectura para soportar Quest y Frotz

La idea central: introducir una **abstracción `GameEngine`** y mover toda la lógica específica de cada motor detrás de ella, de modo que el resto de la app (Flask, cliente LLM, tools) no sepa nunca si está hablando con Quest o con Frotz.

```
web-app (Flask)
  └─ llm_client/
       ├─ catalog.py        # GAMES: catálogo declarativo (id→nombre,motor,ruta)
       ├─ sessions.py       # SessionManager: session_id → {game_id, engine, engine_session}
       ├─ tool_router.py    # (antes mcp_client.py) despacha tool → SessionManager → engine
       └─ engines/
            ├─ base.py       # GameEngine (ABC) + EngineResult
            ├─ quest_engine.py   # reusa el Bridge HTTP actual
            └─ frotz_engine.py   # dfrotz por subprocess  (o Jericho)
```

**Interfaz común (contrato único para todos los motores):**

```python
# engines/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class EngineResult:
    ok: bool
    output: str          # texto que devuelve el motor (la verdad del juego)
    changed: bool = True
    meta: dict | None = None   # score, done, room, etc. si el motor lo da

class GameEngine(ABC):
    @abstractmethod
    def start_game(self, session_id: str, game: "GameSpec") -> EngineResult: ...
    @abstractmethod
    def send_command(self, session_id: str, command: str) -> EngineResult: ...
    @abstractmethod
    def get_state(self, session_id: str) -> EngineResult: ...
    @abstractmethod
    def close_game(self, session_id: str) -> None: ...
```

- **`QuestEngine`**: implementa el contrato **reusando el Bridge actual** (`start_game`→`POST /session/new` con la ruta del catálogo; `send_command`→`/session/command`; `close_game`→`/session/close`; `get_state`→`/session/command "look"`). **No se toca el Bridge ni Playwright.**
- **`FrotzEngine`**: gestiona procesos `dfrotz` por pipes (ver §10 y §11) o, alternativamente, usa la librería **Jericho** (recomendado por fiabilidad, ver §3.1).

`look` y `move` se mantienen como **capa semántica fina** por encima de `send_command`, traduciendo a comando de motor:

```
look            → engine.send_command(sid, "look")
move(east)      → Quest: "go east"   |  Frotz: "east"
```

Esa traducción vive en el `tool_router`/engine, no en el código de Flask.

### 3.1. Dos formas de implementar `FrotzEngine` (decisión clave)

| | **A) `subprocess` + `dfrotz` (propuesta del profesor)** | **B) Jericho (`pip install jericho`)** |
|---|---|---|
| Mecanismo | Lanza `dfrotz` como proceso hijo, habla por stdin/stdout | Frotz compilado como **librería C** embebida; `FrotzEnv(path)` |
| Lectura | Hay que detectar fin de salida (prompt/idle) por pipes | `obs, reward, done, info = env.step(cmd)` — determinista |
| pty / buffering | Riesgos reales (ver §10) | **No hay pipes**: desaparecen los riesgos |
| Concurrencia | Un proceso + hilo lector + lock por sesión | Un objeto `FrotzEnv` por sesión (objetos Python) |
| Score / fin de partida | Hay que parsear texto | `reward` y `done` ya vienen dados |
| Valor para el TFG | Enseña el problema clásico de IPC con un proceso de terminal | Es el estándar de facto en investigación IF (Microsoft) |
| Licencia | GPL-2 (dfrotz) | GPL (incluye frotz) |

**Recomendación:** como la abstracción `FrotzEngine` aísla los detalles, **se puede empezar por A** (es lo que pidió el profesor y demuestra el manejo de procesos de terminal, que es parte del interés académico) y **dejar B como plan de robustez**: si el scraping de stdout da problemas, se cambia el *interior* de `FrotzEngine` a Jericho **sin tocar nada más**. Esa intercambiabilidad es justo lo que justifica la abstracción en la memoria del TFG.

---

## 4. Comparación: ¿dónde ejecutar Frotz?

| Opción | Cómo | Ventajas | Inconvenientes |
|---|---|---|---|
| **1. Dentro de `web-app`** | `apt-get install frotz` en el Dockerfile de web; `FrotzEngine` hace `Popen` como hijo de Flask | Mínima infraestructura; sin salto de red extra; control directo del `Popen`; es lo que sugiere el profesor; demo funcionando rápido | Acopla el ciclo de vida del intérprete al proceso Flask; si web reinicia mueren todas las partidas; la concurrencia queda atada al servidor Flask |
| **2. Servicio Docker separado `frotz-api`** | FastAPI igual que el Bridge, expone `/session/new`, `/session/command`, `/session/close` | **Simetría total** con el Bridge de Quest (ambos motores pasan a ser "servicios HTTP" detrás de `GameEngine`); aislamiento; reinicio independiente; frontera de seguridad clara; permite varios workers | Más infraestructura; otro servicio que mantener; overhead de IPC HTTP |
| **3. Servicio genérico "terminal-engine"** | Un servicio que aloje cualquier intérprete de terminal (frotz, glulxe…) | Preparado para el futuro (más motores Z-machine/Glulx) | Prematuro ahora; sobre-ingeniería para un TFG en su fase actual |

**Recomendación:** para el **primer prototipo en la rama**, **opción 1** (dfrotz dentro de `web-app`), porque es el camino más corto a un Zork jugable y es lo que propuso el profesor. **Condición innegociable:** toda la lógica del motor vive en `engines/frotz_engine.py`, **nunca** mezclada en `app.py` (tú mismo lo pides: "la lógica del motor separada del código Flask"). Así, **promover Frotz a la opción 2 más adelante es un cambio mecánico** (cambiar la implementación de `FrotzEngine` de `Popen` a llamadas HTTP), porque la interfaz `GameEngine` no cambia. A medio plazo, la opción 2 es la más coherente con el diseño (Quest ya vive en un servicio aparte; Frotz acabaría igual).

---

## 5. Diseño del catálogo / menú de juegos

Catálogo **declarativo e independiente del código del LLM** (un único sitio donde se añaden juegos):

```python
# llm_client/catalog.py
from dataclasses import dataclass

@dataclass(frozen=True)
class GameSpec:
    id: str
    name: str
    engine: str       # "quest" | "frotz"
    path: str         # ruta DENTRO del contenedor

GAMES = {
    "quest_tutorial": GameSpec("quest_tutorial", "Quest Tutorial", "quest",
                               "/app/games/quest/game.quest"),
    "zork1":          GameSpec("zork1", "Zork I", "frotz",
                               "/app/games/zmachine/zork1.z3"),
}

def list_games() -> list[dict]:
    return [{"id": g.id, "name": g.name, "engine": g.engine} for g in GAMES.values()]
```

- El LLM **nunca** ve rutas del sistema: solo `id`, `name`, `engine`. Las rutas reales se resuelven en el servidor a partir del `id`.
- Añadir un juego = añadir una entrada al dict + colocar el fichero. Cero cambios en tools ni en Flask.
- Un registro `ENGINES = {"quest": QuestEngine(...), "frotz": FrotzEngine(...)}` mapea el campo `engine` a la instancia concreta.

---

## 6. Diseño de sesiones

Reemplazar el `"demo"` fijo por un **`SessionManager`**. Cada sesión guarda como mínimo lo que tú indicas, más el handle opaco del motor:

```python
# llm_client/sessions.py
{
  "session_id": "u-ab12...",
  "game_id":    "zork1",
  "engine":     "frotz",          # cuál de ENGINES
  "engine_session": <handle>      # opaco: lo entiende SOLO ese motor
}
```

- **Quest**: `engine_session` puede ser simplemente el `sessionId` que ya usa el Bridge (el Bridge guarda el browser/page).
- **Frotz (subprocess)**: `engine_session` es un objeto `FrotzProcess` con: `proc` (`Popen`), `stdin`, **hilo lector** de `stdout`, **cola/buffer** de salida, **lock** (evita comandos simultáneos), **flag `alive`**, y drenaje de `stderr`. **Nunca una única variable global de proceso** (rompería el multi-partida/multi-usuario, justo lo que pides evitar).
- **Frotz (Jericho)**: `engine_session` es el objeto `FrotzEnv`.

El `session_id` debe pasar a ser **por usuario/navegador** (cookie de sesión Flask), no global de módulo. Esto a la vez arregla la limitación actual de "una sola conversación global": `messages` y `chat_history` pasan a vivir dentro del `SessionManager`, indexados por `session_id`.

---

## 7. Diseño de las tools de selección de juego

Recomiendo la **estrategia combinada (opción 3 de tu lista)**: tools de menú de **nivel general** + **una** tool genérica de juego, y mantener `look`/`move` como atajos opcionales.

**Tools de gestión (menú, gestionadas por la IA):**

| Tool | Args | Resultado |
|---|---|---|
| `list_games` | `{}` | `{games:[{id,name,engine}, ...]}` (desde el catálogo) |
| `start_game` | `{game_id}` | Resuelve `engine` por catálogo → `engine.start_game()` → texto inicial |
| `current_game` | `{}` | `{game_id, name, engine}` activos en la sesión |
| `close_game` | `{}` | `engine.close_game()` y libera recursos |

**Tool de juego (workhorse):**

| Tool | Args | Resultado |
|---|---|---|
| `send_game_command` | `{command}` | Enruta el texto al motor activo de la sesión → salida real |

**Capa semántica (opcional, secundaria):** `look` y `move(direction)` se conservan como azúcar: internamente llaman a `send_game_command` traduciendo al dialecto del motor. Útiles para modelos pequeños y para validar argumentos (enum de direcciones), pero **no imprescindibles**: con `send_game_command` + un buen *system prompt* basta.

**Por qué la combinación y no solo verbos específicos (`take`, `open`, `use`…):**
- Reimplementar un verbo-tool por cada acción del juego es inviable (Zork tiene decenas) y duplica el parser que el propio motor ya tiene.
- `send_game_command` deja que el **parser del juego** (la fuente de verdad) interprete; el LLM solo decide *qué texto* mandar en lenguaje de juego.
- Las tools de menú sí merecen ser explícitas porque cambian de **estado de sesión** (qué motor/juego está activo), algo que no debe ir mezclado con comandos de juego.

**Seguridad (requisito que marcas como prioritario):** `send_game_command` **solo escribe en la entrada del proceso/juego**, nunca en una shell. Garantías concretas:
- `subprocess.Popen` con **lista de argumentos** (`["dfrotz", ...]`), **nunca** `shell=True`, nunca `os.system`.
- El `command` se valida como texto plano y se envía como **una sola línea** (`cmd.strip() + "\n"`); se eliminan saltos/control chars intermedios.
- `dfrotz -R <dir_saves>` **confina** lecturas/escrituras de fichero del intérprete a un único directorio (los comandos `SAVE`/`SCRIPT`/`RESTORE` no podrán tocar el resto del FS).
- El proceso corre sin privilegios y sin red. Un comando como `"; rm -rf /"` simplemente se lo come el parser de Zork como texto de juego ("I don't understand that").

---

## 8. Plan incremental de implementación

**Paso 0 — Control de versiones (antes de tocar nada):**
```bash
git add . && git commit -m "Version funcional de Quest con new_game look y move"
git push
git checkout -b feature/frotz-multigame
```
(Opcional pero recomendable: incorporar primero el `run_llm_tool_loop(max_steps=5)` de `PROMPT1.0.txt` en `app.py`, porque el ZIP no lo tiene y es la base para encadenar tools del menú.)

**Paso 1 — Refactor sin cambio de comportamiento (Quest sigue igual):**
- Crear `engines/base.py`, `engines/quest_engine.py` (envuelve las llamadas HTTP al Bridge que hoy hace `mcp_client.py`).
- Crear `catalog.py` (solo `quest_tutorial`) y `sessions.py` (`SessionManager`).
- Reescribir `mcp_client.py` → `tool_router.py`: las 3 tools actuales pasan a ir por `SessionManager → engine`. **Eliminar el `"demo"` y la ruta Windows**; la ruta sale del catálogo.
- **Verificación:** la web juega a Quest exactamente como ahora (`new_game`/`look`/`move`).

**Paso 2 — Tools de menú (todavía solo Quest):**
- Añadir `list_games`, `start_game`, `current_game`, `close_game`, `send_game_command` en `tools.py` y en el router.
- Ajustar el *system prompt* para que el modelo sepa que puede listar/elegir juego.
- **Verificación:** "quiero jugar al de Quest" → `start_game(quest_tutorial)`; "mira la sala" → `send_game_command("look")`.

**Paso 3 — `FrotzEngine` (dfrotz por subprocess, dentro de web-app):**
- Dockerfile de web: `apt-get install -y frotz` (trae `dfrotz`, ver §11).
- Añadir `games/zmachine/zork1.z3` (compilado con ZILF offline, §9). **Validar primero el "plumbing" con `hello.z3`** antes que con Zork.
- Implementar `frotz_engine.py` con `FrotzProcess` (Popen + hilo lector + cola + lock + alive).
- Registrar `engine="frotz"` y la entrada `zork1` en el catálogo.
- **Verificación:** `start_game(zork1)` → banner de Zork; `send_game_command("open mailbox")` → "Opening the small mailbox reveals a leaflet."

**Paso 4 — Robustez y multiusuario:**
- Detección de fin de salida (idle-timeout + prompt), drenaje de `stderr`, `close` al terminar/timeout, `max_steps`, estado por `session_id`.
- (Opcional) intercambiar el interior de `FrotzEngine` por **Jericho** si el scraping da guerra.

**Paso 5 — (Futuro, fuera de runtime) ZILF:** solo como paso de *build*/autoría (§9). No entra en la arquitectura de ejecución.

---

## 9. Papel de ZILF (¿hace falta en esta fase?)

**No, para jugar a Zork no hace falta ZILF.** Lo confirma la documentación oficial y el propio tutorial del PDF, que separan claramente las dos herramientas:

- **ZILF** = *compilador*. Convierte fuente **ZIL** → `.zap` (ZAPF) → fichero **Z-machine** (`.z3`/`.z5`…). Es herramienta de **desarrollo**.
- **Frotz** = *intérprete*. **Ejecuta** un fichero Z-machine **ya compilado**. Es herramienta de **jugador**.

Para reproducir un `.z3`/`.z5` existente, **solo se necesita Frotz**. ZILF entraría únicamente para: (1) **compilar Zork desde su fuente ZIL** y obtener `zork1.z3` de forma limpia y legal (Zork I–III se liberaron como **open source** en noviembre de 2025, así que compilar desde fuente es la vía legítima), o (2) **autoría/generación de juegos nuevos** (la línea "generar aventuras con IA" de tu TFG). En ambos casos es un **paso offline de build**, no parte del servicio en ejecución. Recomendación: mantener ZILF **fuera** de `docker-compose`; si acaso, como script de build que produce los `.z3` que luego sirve Frotz.

### Conclusiones técnicas sobre Frotz (responde a tus puntos 6–11)

- **Comando para ejecutar Z-machine sin GUI:** usar el binario **dumb**, `dfrotz`, con MORE desactivado:
  `dfrotz -m -p -w 80 /app/games/zmachine/zork1.z3`
  - `-m` = **desactiva los prompts MORE** (crítico; sin esto la salida se queda en `[MORE]` esperando una tecla y el lector se bloquea).
  - `-p` = salida ASCII plana (parseo más limpio).
  - `-w 80` = ancho fijo del texto.
  - `-R <dir>` = (recomendado) confina lecturas/escrituras a un directorio (seguridad).
- **¿Funciona por pipes sin pseudo-terminal?** **Sí, `dfrotz` sí.** La interfaz "dumb" no usa curses ni control de pantalla: "todo se imprime línea a línea". El propio `DUMB` del repo dice que está pensada para envolverla en CGI/PHP o "convertirla en un chatbot" → exactamente nuestro caso. El `frotz` **curses** normal **sí** necesitaría tty: **no usar ese**.
- **¿Hace falta pty en Linux?** **No con `dfrotz`.** Solo se necesitaría pty si te empeñaras en manejar el `frotz` de curses. Con dumb, pipes normales bastan (con el matiz de buffering del §10).
- **Detección fiable de fin de respuesta:** tres mecanismos, de más simple a más robusto:
  1. **Hilo lector + idle-timeout**: un hilo vuelca stdout a una cola; consideras "terminado" cuando no llegan bytes nuevos durante ~50–150 ms tras el prompt.
  2. **Identificadores de tipo de línea** de dumb frotz (runtime `\lt`): marca cada línea de salida con un char de tipo; el char de "se solicita entrada de línea" (`>`) señala de forma **determinista** que el juego espera el siguiente comando.
  3. **Comando centinela**: tras el comando real, enviar un comando inocuo de salida conocida y leer hasta verla.
  (Si esto resulta frágil, **Jericho** elimina el problema: `step()` devuelve la observación completa sin scraping.)

---

## 10. Riesgos técnicos (lectura de stdout, buffering, procesos bloqueados, concurrencia)

| Riesgo | Causa | Mitigación |
|---|---|---|
| **`readline()` bloqueante** | dumb frotz imprime el prompt `>` **sin salto de línea final**; un `readline()` espera un `\n` que no llega | Hilo lector no bloqueante + cola; cortar por prompt o por idle-timeout. Nunca `readline()` síncrono en el hilo principal |
| **Buffering del hijo (el gran clásico)** | Cuando stdout va a un **pipe** (no a un tty), libc pasa a **full-buffering**: la salida se queda atascada y el lector cuelga | `stdbuf -o0 -i0 dfrotz ...` (fuerza unbuffered) **o** ejecutar bajo pty **o** usar Jericho. **Aviso:** `bufsize=1, text=True` del ejemplo del profesor afecta al lado **padre**, **no** obliga a flush al hijo |
| **Prompts MORE** | Sin `-m`, dfrotz pausa con `[MORE]` esperando tecla → el lector cuelga | Pasar **siempre `-m`** |
| **`>` ambiguo** | Algún texto de juego contiene `>` que no es prompt | Usar identificadores de tipo de línea (`\lt`) o centinela, no un simple "contiene `>`" |
| **Proceso bloqueado / zombi** | Si no se drena `stderr`, su buffer de pipe se llena y el hijo se **bloquea al escribir**; o el juego crashea | Drenar **stdout y stderr** (dos hilos o `selectors`); timeouts; `proc.poll()`/flag `alive`; reaping en `close_game` |
| **Concurrencia** | Una sola variable global de proceso no soporta varias partidas/usuarios; comandos simultáneos en la misma sesión se entrelazan | `FrotzProcess` por `session_id` + **lock por sesión** (igual que el Bridge ya hace con `asyncio.Lock`). En Flask con hilos, usar `threading.Lock` |
| **Estado global de Flask** | `messages`/`chat_history` globales = una conversación para todos | Mover el historial al `SessionManager` indexado por `session_id` (cookie de sesión) |
| **Seguridad** | Que un comando "escape" a la shell | `Popen` con lista de args, sin `shell=True`; validar texto plano; `dfrotz -R`; sin privilegios ni red |
| **pty vs pipe** | Usar el frotz curses por error | Usar **`dfrotz`** (dumb); el curses necesita tty y rompe el diseño |
| **Disponibilidad del `.z3`** | Hace falta un Zork legal y compatible | Compilar `zork1.z3` con ZILF desde la fuente open-source; validar antes con `hello.z3` |
| **Ruta Windows hardcodeada** | `mcp_client.py` lleva `C:\Users\...` | Sustituir por rutas del catálogo (contenedor Linux) en el Paso 1 |

---

## 11. Archivos concretos a crear / modificar

**Crear (en `docker/web/src/llm_client/`):**
- `engines/__init__.py`
- `engines/base.py` — `GameEngine` (ABC) + `EngineResult`
- `engines/quest_engine.py` — envuelve el Bridge HTTP actual (reusa `/session/*`)
- `engines/frotz_engine.py` — `FrotzProcess` (dfrotz subprocess) **o** wrapper Jericho
- `catalog.py` — `GameSpec` + `GAMES` + `list_games()`
- `sessions.py` — `SessionManager` (session_id → game_id/engine/engine_session + historial)
- `docker/web/games/zmachine/zork1.z3` (compilado con ZILF) y `docker/web/games/quest/game.quest` (o reutilizar `quest-webplayer/data/game.quest`)

**Modificar:**
- `docker/web/src/llm_client/tools.py` — añadir `list_games`, `start_game`, `current_game`, `close_game`, `send_game_command`; `look`/`move` opcionales
- `docker/web/src/llm_client/mcp_client.py` → renombrar a `tool_router.py`: dispatcher fino a `SessionManager`/engines (fin del `"demo"` y de la ruta Windows)
- `docker/web/src/web_app/app.py` — `run_llm_tool_loop(max_steps)`; `session_id` por usuario; system prompt con tools de menú
- `docker/web/Dockerfile` — `apt-get install -y frotz`; `COPY games/`
- `docker/web/requirements.txt` — añadir `jericho` solo si se elige esa vía
- `docker-compose.yaml` — montar volumen `games/`; (más adelante) opcional servicio `frotz-api`; **dejar intactos** `quest-webplayer` y `bridge-api`
- `.env` — sin cambios

**No tocar (preservar Quest):** todo `docker/bridge/src/quest_bridge/**` (Bridge Playwright), `docker/quest-webplayer/**`. El legado `mcp_server/**`, `engine/**`, `worlds/**` puede ignorarse (o documentarse como V1) sin borrarlo.

---

## Resumen de decisiones recomendadas

1. **Abstracción `GameEngine`** + `QuestEngine`(reusa Bridge) + `FrotzEngine`. Catálogo declarativo. `SessionManager` por usuario.
2. **Tools**: menú general (`list_games`/`start_game`/`current_game`/`close_game`) + `send_game_command` genérica; `look`/`move` como atajos opcionales.
3. **Frotz**: `dfrotz` (dumb, `-m -p -w 80 -R`), **sin pty**, primero **dentro de `web-app`** pero con la lógica aislada para poder migrar a un servicio `frotz-api` después.
4. **Lectura**: hilo lector + idle-timeout (o Jericho como plan B robusto). `stbuf -o0` o pty para el buffering. Lock por sesión.
5. **ZILF**: fuera del runtime; solo build/autoría.
6. **Git**: commit del estado Quest en `main`, todo lo nuevo en `feature/frotz-multigame`.

> Siguiente acción sugerida: si te parece bien este diseño, empiezo por el **Paso 1** (refactor a `GameEngine` + `QuestEngine` + catálogo + `SessionManager`) **sin cambiar el comportamiento de Quest**, y lo dejo verificado antes de tocar Frotz.
