# Mejorando juegos conversacionales con Inteligencia Artificial

Trabajo de Fin de Grado · Grado en Ingeniería Informática · Universidad de Cantabria (2026)
Autor: Javier Lamas Tabuenca · Director: Esteban Stafford

Sistema para jugar a aventuras conversacionales —Zork y otros juegos de la
Z-machine, y juegos de Quest— **en lenguaje natural, escribiendo o hablando**.
Un modelo de lenguaje interpreta lo que quiere hacer el jugador y lo traduce a
órdenes del juego, pero solo puede actuar a través de un conjunto cerrado de
herramientas (*tool calling*). **El motor del juego es la única fuente de
verdad**: el modelo no puede cambiar el estado de la partida por su cuenta.

## Arquitectura

```
Navegador (chat y voz, Web Speech API)
      │  HTTP
      ▼
web-app (Flask) ── bucle de tool calling ──►  OpenRouter (modelo de lenguaje)
      │  call_tool(nombre, argumentos)
      ▼
Enrutador ─► SessionManager ─► GameEngine
                               ├─ FrotzEngine ─► dfrotz, un proceso por sesión ─► juegos .z3/.z5
                               └─ QuestEngine ─► bridge-api (FastAPI + Playwright) ─► quest-webplayer
```

Son tres servicios de Docker Compose:

| Servicio | Qué es | Puerto |
| --- | --- | --- |
| `web-app` | Aplicación Flask: interfaz, bucle con el modelo, enrutador de herramientas y procesos `dfrotz` | 8100 |
| `bridge-api` | Puente hacia Quest: maneja el reproductor con un Chromium sin interfaz | 8787 (solo desde el propio equipo) |
| `quest-webplayer` | Reproductor de Quest Viva con el juego tutorial | 8080 |

El modelo solo ve ocho herramientas: `list_games`, `start_game`, `current_game`,
`close_game`, `new_game`, `send_game_command`, `look` y `move`. Ninguna ejecuta
órdenes del sistema ni recibe rutas de ficheros.

## Puesta en marcha

Requisitos: Docker (con Docker Compose) y una clave de [OpenRouter](https://openrouter.ai/keys).

```bash
git clone https://github.com/javiilamas/tfg-text-adventure-quest-llm.git
cd tfg-text-adventure-quest-llm
cp .env.example .env          # en PowerShell: copy .env.example .env
# edita .env y pon tu clave en OPENROUTER_API_KEY
docker compose up --build
```

La interfaz queda en <http://localhost:8100>. El fichero `.env` contiene una
clave privada: está en `.gitignore` y nunca debe subirse al repositorio.

Ejemplos de lo que se puede escribir o dictar (el micrófono funciona en Chrome y
Edge, y solo desde `localhost`): «¿a qué juegos puedo jugar?», «quiero jugar a
Zork», «abre el buzón y lee lo que haya dentro», «ve al norte», «cambia al
tutorial de Quest». La primera partida de Quest tarda entre 15 y 30 segundos en
arrancar.

Para ver en los registros qué herramientas pide el modelo en cada turno, añade
`DEBUG_LLM=1` al `.env` y ejecuta `docker compose logs -f web-app`.

## Añadir juegos

Basta con copiar el fichero en la carpeta de juegos, que está montada como
volumen; no hay que tocar código ni reconstruir la imagen (véase
[`docker/web/games/README.md`](docker/web/games/README.md)).

| Carpeta | Motor | Extensiones |
| --- | --- | --- |
| `docker/web/games/zmachine/` | Frotz | `.z1`–`.z8`, `.zblorb`, `.zlb`, `.dat` |
| `docker/web/games/quest/` | Quest | `.quest` (limitado: véase «Limitaciones») |

## Pruebas

```bash
docker compose run --rm web-app python -m unittest discover -s src/tests -v
```

Son 16 pruebas que se ejecutan en unos segundos, sin red ni modelo: usan un
intérprete falso (`fake_frotz.py`), un modelo simulado y, las de seguridad, el
`dfrotz` real del contenedor.

## Evaluación

Los scripts están en `docker/web/src/eval` y sus resultados, en
[`docker/web/src/eval/resultados`](docker/web/src/eval/resultados/LEEME.md).
Desde la raíz del repositorio (en PowerShell, sustituye `$PWD` por `${PWD}`):

```bash
V="$PWD/docker/web/src/eval/resultados:/app/src/eval/resultados"

# Banco del motor Frotz: latencia, concurrencia y seguridad
docker compose run --rm -v "$V" web-app python -m src.eval.bench_engine --repeticiones 10

# Banco del motor Quest (con los tres servicios en marcha)
docker compose run --rm -v "$V" web-app python -m src.eval.bench_quest

# Batería de extremo a extremo con el modelo real (usa la clave del .env)
docker compose run --rm -v "$V" web-app python -m src.eval.eval_llm --repeticiones 3
docker compose run --rm -v "$V" web-app python -m src.eval.eval_llm --casos src/eval/casos_quest.json --repeticiones 3
docker compose run --rm -v "$V" web-app python -m src.eval.eval_llm --partida-larga
```

Con `--simulado`, la batería usa un modelo de reglas, sin red ni coste; solo
sirve para comprobar que el arnés funciona.

Resultados medidos (octubre y noviembre de 2026, `openai/gpt-4o-mini`):

| Medida | Resultado |
| --- | --- |
| Batería de 31 casos × 3 repeticiones | 89 de 93 ejecuciones superadas (96 %) |
| Tiempo por turno, con el modelo | 2,79 s de media; 4,99 s en el percentil 95 |
| Coste por turno | 0,00034 USD |
| Narraciones fieles a la salida del motor | 22 de 27 revisadas |
| Motor Frotz | 121 ms por orden; 20 sesiones simultáneas sin errores de aislamiento; 1,1 MB por partida |
| Motor Quest | 832 ms por orden; 17 s de arranque; unos 63 MB por partida |

## Estructura del repositorio

```
docker-compose.yaml            los tres servicios
.env.example                   plantilla de configuración (el .env no se sube)
docker/
  web/                         servicio web-app
    Dockerfile                 Python 3.11 + Frotz
    games/                     carpeta de juegos (zmachine/ y quest/)
    src/
      web_app/                 Flask: bucle de tool calling, cerrojo por sesión, interfaz y voz
      llm_client/
        llm.py, tools.py       llamada al modelo y esquemas de las herramientas
        mcp_client.py          enrutador de herramientas (conserva el nombre por razones históricas)
        sessions.py, catalog.py
        engines/               GameEngine, FrotzEngine y QuestEngine
        main.py                cliente de consola de la versión 3 (sin uso)
      tests/                   pruebas automatizadas
      eval/                    bancos de pruebas, batería y resultados
  bridge/                      servicio bridge-api
    src/quest_bridge/          puente FastAPI + Playwright
    src/mcp_server/, engine/, cli/, worlds/, tests/
                               servidor MCP y motor propio de la versión 1 (no se despliegan)
  quest-webplayer/data/        juego de Quest que carga el reproductor
docs/
  REGISTRO_VERSIONES.md        objetivo, cambios y decisiones de cada versión
  DISENO_frotz_multimotor.md   documento de diseño de la integración de Frotz (junio de 2026)
```

## Versiones

Cada versión descrita en la memoria (sección 4.2) está en el historial como un
commit con su etiqueta. `git checkout <etiqueta>` recupera el proyecto tal como
estaba.

| Etiqueta | Versión | Fecha de la copia | Contenido |
| --- | --- | --- | --- |
| `quest-v4` | Versiones 1 a 4 | 13/05/2026 | Etapa de Quest: motor propio y servidor MCP (V1), puente con Playwright (V2), bucle de herramientas (V3) e interfaz web (V4) |
| `frotz-v1` | Frotz v1 | 29/06/2026 | Abstracción `GameEngine`, `FrotzEngine`, catálogo, sesiones y MiniZork |
| `frotz-v3` | Frotz v2 y v3 | 30/06/2026 | Cerrojo por sesión y reparación del historial; Quest en contenedores; interfaz retro, voz, carpeta de juegos, pruebas y La Cueva |
| `frotz-v4` | Frotz v4 | 30/06/2026 | Prompt de narrador y dictado por voz fiable |
| `frotz-v5` | Frotz v5 | 30/06/2026 | Zork I compilado con ZILF; es la versión entregada en julio de 2026 |
| `frotz-v6` | Frotz v6 | 05/11/2026 | Evaluación: pruebas, bancos, batería con el modelo y correcciones; código con el que se midió |
| `v1.0` | Versión entregada | 11/11/2026 | Revisión final del código y de la documentación |

Durante el desarrollo se conservó una copia del proyecto por versión. En
noviembre de 2026 esas copias se incorporaron a este repositorio como commits
sucesivos, por lo que la fecha de cada commit no es la de su desarrollo: la
fecha original figura en el mensaje del commit y en la tabla. De cada copia se
excluyeron el fichero `.env`, las cachés y las copias de seguridad, y los
finales de línea se unificaron a LF. El primer commit, del 12 de mayo de 2026,
es el original. Los demás se crearon con ayuda de Claude, y por eso llevan la
línea `Co-Authored-By`.

## Limitaciones

La memoria las analiza en su capítulo 6. Las principales:

- El diseño garantiza la coherencia del estado, no la de la narración: el modelo
  puede contar algo que el motor no ha dicho.
- La integración con Quest automatiza un navegador: espera fija de 600 ms tras
  cada orden, un Chromium por partida y dependencia de la estructura de la
  página. Un `.quest` añadido a la carpeta aparece en el catálogo, pero el
  reproductor solo carga el juego configurado.
- El historial completo se reenvía al modelo en cada turno, de modo que el coste
  crece con la duración de la partida.
- Es un prototipo para uso local: servidor de desarrollo de Flask, puente sin
  autenticación y estado en memoria.
- La imagen del reproductor de Quest se usa con la etiqueta `latest` y la mayoría
  de las dependencias de Python no fijan versión.

## Créditos y licencias de terceros

- **Zork I** — © 2025 Microsoft, licencia MIT. `zork1.z3` se compiló con
  [ZILF](https://zilf.io) 1.9.0 a partir del código fuente publicado por
  Microsoft en noviembre de 2025. La licencia está en
  [`docker/web/games/zmachine/LICENSE-zork1.txt`](docker/web/games/zmachine/LICENSE-zork1.txt).
- **MiniZork** y **La Cueva** — juegos de demostración propios, escritos en
  Inform 6; sus fuentes (`.inf`) están junto a los ficheros compilados.
- **Quest Viva** — motor y reproductor de código abierto (licencia MIT), usados
  mediante la imagen `ghcr.io/textadventures/quest-viva-webplayer`.
- **`docker/quest-webplayer/data/game.quest`** — «Quest Text Adventure Tutorials
  and Templates», de XanMag, un juego tutorial de la comunidad de Quest. Se
  incluye únicamente como juego de demostración.
- **Frotz** — intérprete de la Z-machine (GPL). Se instala en la imagen desde el
  paquete de Debian; no se redistribuye en este repositorio.

## Uso de inteligencia artificial

El proyecto se desarrolló con ayuda de asistentes de IA generativa: ChatGPT en
la etapa de Quest y Claude desde la incorporación de Frotz, incluidas la
evaluación y la revisión final. El detalle está en la sección 4.1 de la memoria.
