"""Catalogo de juegos con AUTODESCUBRIMIENTO.

Basta con dejar un fichero de juego en la carpeta correspondiente y aparece solo
(sin tocar codigo). El LLM solo ve id, nombre, motor y una descripcion breve,
nunca rutas del sistema.

Carpetas (dentro del contenedor, montadas desde ./docker/web/games):
  GAMES_ROOT/zmachine/  -> motor Frotz  (.z1 .. .z8, .zblorb, .zlb, .dat)
  GAMES_ROOT/quest/     -> motor Quest  (.quest)

Ademas hay un juego "incorporado" (quest_tutorial) por compatibilidad.
"""
from __future__ import annotations
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GameSpec:
    id: str
    name: str
    engine: str          # "quest" | "frotz"
    path: str
    description: str = ""


GAMES_ROOT = os.getenv("GAMES_ROOT", "/app/games")

# Extensiones reconocidas por carpeta/motor.
FROTZ_EXTS = {".z1", ".z2", ".z3", ".z4", ".z5", ".z6", ".z7", ".z8",
              ".zblorb", ".zlb", ".dat"}
QUEST_EXTS = {".quest"}

_SCAN = [("zmachine", "frotz", FROTZ_EXTS), ("quest", "quest", QUEST_EXTS)]

# Nombres bonitos para juegos conocidos (opcional; si no, se deriva del fichero).
_PRETTY = {
    "minizork": "MiniZork (demo)",
    "zork1": "Zork I", "zork2": "Zork II", "zork3": "Zork III",
    "advent": "Colossal Cave", "adventure": "Colossal Cave",
    "cave": "La Cueva (demo)",
}

# Juego de Quest incorporado: la ruta es la del fichero DENTRO del contenedor
# del Bridge (ver los volumenes de docker-compose.yaml).
_QUEST_DEFAULT = os.getenv("QUEST_FILE_PATH", "/data/game.quest")

_BUILTIN = {
    "quest_tutorial": GameSpec(
        "quest_tutorial", "Quest Tutorial", "quest", _QUEST_DEFAULT,
        "Tutorial de Quest Viva (motor Quest)."),
}


def _slug(stem: str) -> str:
    s = "".join(c.lower() if c.isalnum() else "_" for c in stem).strip("_")
    return s or "game"


def _pretty(stem: str) -> str:
    return _PRETTY.get(stem.lower(), stem.replace("_", " ").replace("-", " ").title())


def _discover() -> dict[str, GameSpec]:
    """Devuelve {id: GameSpec} combinando los incorporados y los descubiertos.
    Se vuelve a escanear en cada llamada para reflejar ficheros recien anadidos."""
    games: dict[str, GameSpec] = dict(_BUILTIN)
    for sub, engine, exts in _SCAN:
        folder = os.path.join(GAMES_ROOT, sub)
        if not os.path.isdir(folder):
            continue
        for fn in sorted(os.listdir(folder)):
            stem, ext = os.path.splitext(fn)
            if ext.lower() not in exts:
                continue
            gid = _slug(stem)
            if gid in games:        # no pisar incorporados (p.ej. quest_tutorial)
                continue
            games[gid] = GameSpec(
                gid, _pretty(stem), engine, os.path.join(folder, fn),
                f"{engine.title()} — {fn}")
    return games


def list_games() -> list[dict]:
    return [{"id": g.id, "name": g.name, "engine": g.engine, "description": g.description}
            for g in _discover().values()]


def get_game(game_id: str) -> GameSpec | None:
    return _discover().get(game_id)
