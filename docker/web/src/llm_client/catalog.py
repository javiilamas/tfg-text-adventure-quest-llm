"""Catalogo declarativo de juegos, independiente del codigo del LLM.

Anadir un juego = anadir una entrada aqui + colocar el fichero. Cero cambios en
las tools ni en Flask. El LLM solo ve id/name/engine, nunca rutas del sistema.
"""
from __future__ import annotations
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GameSpec:
    id: str
    name: str
    engine: str          # "quest" | "frotz"
    path: str            # ruta DENTRO del contenedor (o ruta que entiende el motor)
    description: str = ""


# Quest conserva su comportamiento actual: la ruta sale de QUEST_FILE_PATH, igual
# que el mcp_client original (no se cambia la integracion Quest existente).
_QUEST_DEFAULT = os.getenv(
    "QUEST_FILE_PATH",
    r"C:\Users\lecle\Desktop\TFG\tfg-text-adventure-with-tests\src\quest-juegos\juego_prueba.quest",
)
_MINIZORK_PATH = os.getenv("MINIZORK_PATH", "/app/games/zmachine/minizork.z5")
_ZORK1_PATH = os.getenv("ZORK1_PATH", "/app/games/zmachine/zork1.z3")

GAMES: dict[str, GameSpec] = {
    "quest_tutorial": GameSpec(
        "quest_tutorial", "Quest Tutorial", "quest", _QUEST_DEFAULT,
        "Tutorial de Quest Viva (motor Quest, via Bridge + Playwright)."),
    "minizork": GameSpec(
        "minizork", "MiniZork (demo)", "frotz", _MINIZORK_PATH,
        "Mundo Z-machine de demostracion, original y listo para jugar con Frotz."),
    "zork1": GameSpec(
        "zork1", "Zork I", "frotz", _ZORK1_PATH,
        "Zork I. Requiere anadir zork1.z3 (ver games/zmachine/README.md)."),
}


def list_games() -> list[dict]:
    return [{"id": g.id, "name": g.name, "engine": g.engine, "description": g.description}
            for g in GAMES.values()]


def get_game(game_id: str) -> GameSpec | None:
    return GAMES.get(game_id)
